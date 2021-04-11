"""Author: Mark Hanegraaff -- 2020

This module is a value add to the Intrinio SDK and implements a 
number of functions to read current and historical financial statements, 
pricing data and company historical data.

It also converts Intrinio raw responses into easier to digest dictionaries
that are easier to consume by the application.
"""

import intrinio_sdk
import atexit
import requests
import logging
import datetime
import os
import time
from intrinio_sdk.rest import ApiException
from exception.exceptions import DataError, ValidationError
from connectors import intrinio_util
from support.financial_cache import cache
from datetime import timedelta

log = logging.getLogger()

try:
    API_KEY = os.environ['INTRINIO_API_KEY']
except KeyError as ke:
    raise ValidationError("INTRINIO_API_KEY was not set", None)

intrinio_sdk.ApiClient().configuration.api_key['api_key'] = API_KEY


FUNDAMENTALS_API = intrinio_sdk.FundamentalsApi()
COMPANY_API = intrinio_sdk.CompanyApi()
SECURITY_API = intrinio_sdk.SecurityApi()


INTRINIO_CACHE_PREFIX = 'intrinio'

'''
  Testing APIs using requests package
'''


def retry_server_errors(func):
    '''
        decorator that will retry intrinio server side errors, and let
        others pass through.

        Retries the error up to 5 times and sleeps 2 seconds between retries
    '''
    def wrapper(*args, **kwargs):
        latest_exception = None
        num_retries = 5
        for attempt in range(1, num_retries + 1):
            try:
                return func(*args, **kwargs)
            except DataError as de:
                latest_exception = de
                cause = de.cause
                if cause == None or not hasattr(cause, 'status') or not isinstance(cause.status, int):
                    raise de

                status = int(cause.status)
                if status >= 500:
                    log.info("Retring Intrinio Server side error after a pause: [%d]. Attempt %d of %d" % (
                        status, attempt, num_retries))
                    time.sleep(2)
                else:
                    break

        raise latest_exception

    return wrapper


def test_api_endpoint():
    """
      Tests the API endpoint directly and throws a DataError if
      anything goes wrong. 
      This is used to validate that the API key works
    """

    url = 'https://api-v2.intrinio.com/companies/AAPL'

    try:
        response = requests.request('GET', url, params={
            'api_key': API_KEY
        }, timeout=10)
    except Exception as e:
        raise DataError("Could not execute GET to %s" % url, e)

    if not response.ok:
        raise DataError(
            "Invalid response from Intrinio Endpoint", Exception(response.text))


'''
  Pricing statement APIs using the SECURITY_API client
'''


def get_zacks_target_price_std_dev(ticker: str, start_date: datetime, end_date: datetime):
    """
      retrieves the 'zacks_target_price_std_dev' data point for the supplied date 
      range. see the '_get_company_historical_data()' pydoc for specific information
      or parameters, return types and exceptions.
    """
    return _aggregate_by_year_month(
        _get_company_historical_data(ticker, intrinio_util.date_to_string(
            start_date), intrinio_util.date_to_string(end_date), 'zacks_target_price_std_dev')
    )


def get_zacks_target_price_mean(ticker: str, start_date: datetime, end_date: datetime):
    """
      retrieves the 'zacks_target_price_mean' data point for the supplied date 
      range. see the '_get_company_historical_data()' pydoc for specific information
      or parameters, return types and exceptions.
    """
    return _aggregate_by_year_month(
        _get_company_historical_data(ticker, intrinio_util.date_to_string(
            start_date), intrinio_util.date_to_string(end_date), 'zacks_target_price_mean')
    )


def get_zacks_target_price_cnt(ticker: str, start_date: datetime, end_date: datetime):
    """
      retrieves the 'zacks_target_price_cnt' data point for the supplied date 
      range. see the '_get_company_historical_data()' pydoc for specific information
      or parameters, return types and exceptions.
    """
    return _aggregate_by_year_month(
        _get_company_historical_data(ticker, intrinio_util.date_to_string(
            start_date), intrinio_util.date_to_string(end_date), 'zacks_target_price_cnt')
    )


@retry_server_errors
def get_daily_stock_close_prices(ticker: str, start_date: datetime, end_date: datetime):
    '''
      Returns a list of historical daily stock prices given a ticker symbol and
      a range of dates.  Currently only returns one page of 100 results

      Parameters
      ----------
      ticker : str
        Ticker Symbol
      start_date : object
        The beginning price date as python date object
      end_date : object
        The end price date as python date object

      Returns
      -----------
      a dictionary of date->price like this
      {
        '2019-10-01': 100,
        '2019-10-02': 101,
        '2019-10-03': 102,
        '2019-10-04': 103,
      }
    '''

    start_date_str = intrinio_util.date_to_string(start_date).replace('-', '')
    end_date_str = intrinio_util.date_to_string(end_date).replace('-', '')

    price_dict = {}

    cache_key = "%s-%s-%s-%s-%s" % (INTRINIO_CACHE_PREFIX,
                                    ticker, start_date_str, end_date_str, "closing-prices")
    api_response = cache.read(cache_key)

    if api_response is None:
        try:
            api_response = SECURITY_API.get_security_stock_prices(
                ticker, start_date=start_date_str, end_date=end_date_str, frequency='daily', page_size=100)
            cache.write(cache_key, api_response)
        except ApiException as ae:
            raise DataError("API Error while reading price data from Intrinio Security API: ('%s', %s - %s)" %
                            (ticker, start_date_str, end_date_str), ae)
        except Exception as e:
            raise ValidationError("Unknown Error while reading price data from Intrinio Security API: ('%s', %s - %s)" %
                                  (ticker, start_date_str, end_date_str), e)

    price_list = api_response.stock_prices

    if len(price_list) == 0:
        raise DataError("No prices returned from Intrinio Security API: ('%s', %s - %s)" %
                        (ticker, start_date_str, end_date_str), None)

    for price in price_list:
        price_dict[intrinio_util.date_to_string(price.date)] = price.close

    return price_dict


def get_latest_close_price(ticker, price_date: datetime, max_looback: int):
    """
      Retrieves the most recent close price given a price_date and a lookback window

      Returns
      -----------
      a tuple of date, float with the latest price date and price value
    """

    if max_looback not in range(1, 10):
        raise ValidationError(
            "Invalid 'max_looback'. Allowed values are [1..10]", None)

    looback_date = price_date - timedelta(days=max_looback)

    price_dict = get_daily_stock_close_prices(ticker, looback_date, price_date)

    price_date = sorted(list(price_dict.keys()), reverse=True)[0]

    return (price_date, price_dict[price_date])

'''
  Price indicator APIs using the SECURITY_API client
'''


@retry_server_errors
def get_macd_indicator(ticker: str, start_date: datetime, end_date: datetime,
                       fast_period: int, slow_period: int, signal_period: int):
    '''
      Returns a dictionary of MACD indicators given a ticker symbol,
      a date range and necessary MACD parameters.  
      Currently only returns one page of 100 results

      Parameters
      ----------
      ticker : str
        Ticker Symbol
      start_date : object
        The beginning price date as python date object
      end_date : object
        The end price date as python date object
      fast_period: int
        the MACD fast period parameter
      slow_perdiod: int
        the MACD slow period parameter
      signal_period:
        the MACD signal period parameter

      Returns
      -----------
      a dictionary of date->price like this
      {
          "2020-05-29": {
              "macd_histogram": -0.5565262759342229,
              "macd_line": 9.361568685377279,
              "signal_line": 9.918094961311501
          },
          "2020-05-28": {
              "macd_histogram": -0.3259226480613542,
              "macd_line": 9.731303882233703,
              "signal_line": 10.057226530295058
          }
      }
    '''

    start_date_str = intrinio_util.date_to_string(
        start_date).replace('-', '').replace('-', '')
    end_date_str = intrinio_util.date_to_string(
        end_date).replace('-', '').replace('-', '')

    macd_dict = {}

    cache_key = "%s-%s-%s-%s-%d.%d.%d-%s" % (INTRINIO_CACHE_PREFIX,
                                             ticker, start_date_str, end_date_str, fast_period, slow_period, signal_period, "tech-macd")
    api_response = cache.read(cache_key)

    if api_response is None:
        try:
            api_response = SECURITY_API.get_security_price_technicals_macd(
                ticker, fast_period=fast_period, slow_period=slow_period, signal_period=signal_period, price_key='close', start_date=start_date, end_date=end_date, page_size=100)

            cache.write(cache_key, api_response)
        except ApiException as ae:
            raise DataError("API Error while reading MACD indicator from Intrinio Security API: ('%s', %s - %s (%d, %d, %d))" %
                            (ticker, start_date_str, end_date_str, fast_period, slow_period, signal_period), ae)
        except Exception as e:
            raise ValidationError("Unknown Error while reading MACD indicator from Intrinio Security API: ('%s', %s - %s (%d, %d, %d))" %
                                  (ticker, start_date_str, end_date_str, fast_period, slow_period, signal_period), e)

    macd_list = api_response.technicals

    if len(macd_list) == 0:
        raise DataError("No MACD indicators returned from Intrinio Security API: ('%s', %s - %s (%d, %d, %d))" %
                        (ticker, start_date_str, end_date_str, fast_period, slow_period, signal_period), None)

    for macd in macd_list:
        macd_dict[intrinio_util.date_to_string(macd.date_time)] = {
            "macd_histogram": macd.macd_histogram,
            "macd_line": macd.macd_line,
            "signal_line": macd.signal_line
        }

    return macd_dict


@retry_server_errors
def get_sma_indicator(ticker: str, start_date: datetime, end_date: datetime,
                      period_days: int):
    '''
      Returns a dictionary of SMA (simple moving average) indicators given a 
      ticker symbol, a date range and the period.  

      Currently only returns one page of 100 results

      Parameters
      ----------
      ticker : str
        Ticker Symbol
      start_date : object
        The beginning price date as python date object
      end_date : object
        The end price date as python date object
      period_days: int
        The number of price days included in this average


      Returns
      -----------
      a dictionary of date->price like this
      {
        "2020-05-29": 282.51779999999997,
        "2020-05-28": 281.09239999999994,
        "2020-05-27": 279.7845999999999,
        "2020-05-26": 278.26659999999987,
        "2020-05-22": 277.4913999999999,
        "2020-05-21": 276.07819999999987,
        "2020-05-20": 275.2497999999999
      }

    '''

    start_date_str = intrinio_util.date_to_string(
        start_date).replace('-', '').replace('-', '')
    end_date_str = intrinio_util.date_to_string(
        end_date).replace('-', '').replace('-', '')

    sma_dict = {}

    cache_key = "%s-%s-%s-%s-%d-%s" % (INTRINIO_CACHE_PREFIX,
                                       ticker, start_date_str, end_date_str, period_days, "tech-sma")
    api_response = cache.read(cache_key)

    if api_response is None:
        try:
            api_response = SECURITY_API.get_security_price_technicals_sma(
                ticker, period=period_days, price_key='close', start_date=start_date, end_date=end_date, page_size=100)

            cache.write(cache_key, api_response)
        except ApiException as ae:
            raise DataError("API Error while reading SMA indicator from Intrinio Security API: ('%s', %s - %s (%d))" %
                            (ticker, start_date_str, end_date_str, period_days), ae)
        except Exception as e:
            raise ValidationError("Unknown Error while reading SMA indicator from Intrinio Security API: ('%s', %s - %s (%d))" %
                                  (ticker, start_date_str, end_date_str, period_days), e)

    sma_list = api_response.technicals

    if len(sma_list) == 0:
        raise DataError("No SMA indicators returned from Intrinio Security API: ('%s', %s - %s (%d))" %
                        (ticker, start_date_str, end_date_str, period_days), None)

    for sma in sma_list:
        sma_dict[intrinio_util.date_to_string(sma.date_time)] = sma.sma

    return sma_dict


'''
  Finacial statement APIs using the FUNDAMENTALS_API client
'''


def get_historical_revenue(ticker: str, year_from: int, year_to: int):
    '''
      Returns a dictionary of year->"total revenue" for the supplied ticker and
      range of years.

      Returns
      -----------
      a dictionary of year->"fcff value" like this
      {
        2010: 123,
        2012: 234,
        2013: 345,
        2014: 456,
      }
    '''

    start_date = intrinio_util.get_year_date_range(year_from, 0)[0]
    end_date = intrinio_util.get_year_date_range(year_to, 0)[1]

    return _aggregate_by_year(
        _get_company_historical_data(
            ticker, start_date, end_date, 'totalrevenue')
    )


def get_historical_fcff(ticker: str, year_from: int, year_to: int):
    '''
      Returns a dictionary of year->"fcff value" for the supplied ticker and
      range of years.

        This is the description from Intrinio documentation:

        Definition
        Free cash flow for the firm (FCFF) is a measure of financial performance that
        expresses the net amount of cash that is generated for a firm after expenses,
        taxes and changes in net working capital and investments are deducted.
        FCFF is essentially a measurement of a company's profitability after all expenses
        and reinvestments. It's one of the many benchmarks used to compare and analyze
        financial health.

        Formula
        freecashflow = nopat - investedcapitalincreasedecrease


      Returns
      -----------
      a dictionary of year->"fcff value" like this
      {
        2010: 123,
        2012: 234,
        2013: 345,
        2014: 456,
      }
    '''

    start_date = intrinio_util.get_year_date_range(year_from, 0)[0]
    end_date = intrinio_util.get_year_date_range(year_to, 0)[1]

    return _aggregate_by_year(
        _get_company_historical_data(
            ticker, start_date, end_date, 'freecashflow')
    )


def get_historical_income_stmt(ticker: str, year_from: int,
                               year_to: int, tag_filter_list: list):
    """
      returns a dictionary containing partial or complete income statements given
      a ticker symbol, year from, year to and a list of tag filters
      used to narrow the results.

      Returns
      -------
      A dictionary of year=>dict with the filtered results. For example:

      {2010: {
        'netcashfromcontinuingoperatingactivities': 77434000000.0,
        'purchaseofplantpropertyandequipment': -13313000000
      },}

    """

    return _read_historical_financial_statement(
        ticker.upper(), 'income_statement', year_from, year_to, tag_filter_list)


def get_historical_balance_sheet(ticker: str, year_from: int,
                                 year_to: int, tag_filter_list: list):
    """
      returns a dictionary containing partial or complete balance sheets given
      a ticker symbol, year from, year to and a list of tag filters
      used to narrow the results.

      Returns
      -------
      A dictionary of year=>dict with the filtered results. For example:

      {2010: {
        'netcashfromcontinuingoperatingactivities': 77434000000.0,
        'purchaseofplantpropertyandequipment': -13313000000
      },}

    """
    return _read_historical_financial_statement(
        ticker.upper(), 'balance_sheet_statement', year_from, year_to, tag_filter_list)


def get_historical_cashflow_stmt(ticker: str, year_from: int,
                                 year_to: int, tag_filter_list: list):
    """
      returns a partial or complete set of cashflow statements given
      a ticker symbol, year from, year to and a list of tag filters
      used to narrow the results.

      Returns
      -------
      A dictionary of year=>dict with the filtered results. For example:

      {2010: {
        'netcashfromcontinuingoperatingactivities': 77434000000.0,
        'purchaseofplantpropertyandequipment': -13313000000
      },}

    """
    return _read_historical_financial_statement(
        ticker.upper(), 'cash_flow_statement', year_from, year_to, tag_filter_list)


#
# Private Helper methods
#

def _transform_financial_stmt(std_financials_list: list, tag_filter_list: list):
    """
      Helper function that transforms a financial statement stored in
      the raw Intrinio format into a more user friendly one.

      Returns
      -------
      A dictionary of tag=>value with the filtered results. For example:

      {
        'netcashfromcontinuingoperatingactivities': 77434000000.0,
        'purchaseofplantpropertyandequipment': -13313000000
      }

      Note that the name of the tags are specific to the Intrinio API
    """
    results = {}

    for financial in std_financials_list:

        if (tag_filter_list is None or
                financial.data_tag.tag in tag_filter_list):
            results[financial.data_tag.tag] = financial.value

    return results


@retry_server_errors
def _read_historical_financial_statement(ticker: str, statement_name: str, year_from: int, year_to: int, tag_filter_list: list):
    """
      This helper function will read standardized fiscal year end financials from the Intrinio fundamentals API
      for each year in the supplied range, and normalize the results into simpler user friendly
      dictionary, for example:

      {
        'netcashfromcontinuingoperatingactivities': 77434000000.0,
        'purchaseofplantpropertyandequipment': -13313000000
      }

      results may also be filtered based on the tag_filter_list parameter, which may include
      just the tags that should be returned.

      Parameters
      ----------
      ticker : str
        Ticker Symbol
      statement_name : str
        The name of the statement to read.
      year_from : int
        Start year of financial statement list
      year_to : int
        End year of the financial statement list
      tag_filter_list : list
        List of data tags used to filter results. The name of each tag
        must match an expected one from the Intrinio API. If "None", then all
        tags will be returned.

      Returns
      -------
      A dictionary of tag=>value with the filtered results. For example:

      {
        'netcashfromcontinuingoperatingactivities': 77434000000.0,
        'purchaseofplantpropertyandequipment': -13313000000
      }

      Note that the name of the tags are specific to the Intrinio API

    """
    # return value
    hist_statements = {}
    ticker = ticker.upper()

    statement_type = 'FY'

    try:
        for i in range(year_from, year_to + 1):
            satement_name = ticker + "-" + \
                statement_name + "-" + str(i) + "-" + statement_type

            cache_key = "%s-%s-%s-%s-%s-%d" % (
                INTRINIO_CACHE_PREFIX, "statement", ticker, statement_name, statement_type, i)
            statement = cache.read(cache_key)

            if statement is None:
                statement = FUNDAMENTALS_API.get_fundamental_standardized_financials(
                    satement_name)

                cache.write(cache_key, statement)

            hist_statements[i] = _transform_financial_stmt(
                statement.standardized_financials, tag_filter_list)

    except ApiException as ae:
        raise DataError(
            "Error retrieving ('%s', %d - %d) -> '%s' from Intrinio Fundamentals API" % (ticker, year_from, year_to, statement_name), ae)

    return hist_statements


@retry_server_errors
def _read_company_data_point(ticker: str, tag: str):
    """
      Helper function that will read the Intrinio company API for the supplied ticker
      and return the value


      Returns
      -------
      The numerical value of the datapoint
    """

    # check the cache first
    cache_key = "%s-%s-%s-%s" % (INTRINIO_CACHE_PREFIX,
                                 "company_data_point_number", ticker, tag)
    api_response = cache.read(cache_key)

    if api_response is None:
        # else call the API directly
        try:
            api_response = COMPANY_API.get_company_data_point_number(
                ticker, tag)

            cache.write(cache_key, api_response)
        except ApiException as ae:
            raise DataError(
                "Error retrieving ('%s') -> '%s' from Intrinio Company API" % (ticker, tag), ae)
        except Exception as e:
            raise ValidationError(
                "Error parsing ('%s') -> '%s' from Intrinio Company API" % (ticker, tag), e)

    return api_response


@retry_server_errors
def _get_company_historical_data(ticker: str, start_date: str, end_date: str, tag: str):
    """
      Helper function that will read the Intrinio company API for the supplied date range

      Parameters
      ----------
      ticker : str
        Ticker symbol. E.g. 'AAPL'
      start_date : str
        Start date of the metric formatted as YYYY-MM-DD
      end_date : str
        End date of the metric formatted as YYYY-MM-DD
      tag : the metric name to retrieve

      Raises
      -------
      DataError in case of any error calling the intrio API
      ValidationError in case of an unknown exception

      Returns
      -------
      The 'historical_data_dict' portion of the 'get_company_historical_data'

      [
        {'date': datetime.date(2018, 9, 29), 'value': 265595000000.0},
        {'date': datetime.date(2017, 9, 30), 'value': 229234000000.0}
      ]
    """

    frequency = 'yearly'

    # check the cache first
    cache_key = "%s-%s-%s-%s-%s-%s-%s" % (INTRINIO_CACHE_PREFIX,
                                          "company_historical_data", ticker, start_date, end_date, frequency, tag)
    api_response = cache.read(cache_key)

    if api_response is None:
        # else call the API directly
        try:
            api_response = COMPANY_API.get_company_historical_data(
                ticker, tag, frequency=frequency, start_date=start_date, end_date=end_date)
        except ApiException as ae:
            raise DataError(
                "Error retrieving ('%s', %s - %s) -> '%s' from Intrinio Company API" % (ticker, start_date, end_date, tag), ae)
        except Exception as e:
            raise ValidationError(
                "Error parsing ('%s', %s - %s) -> '%s' from Intrinio Company API" % (ticker, start_date, end_date, tag), e)

    if len(api_response.historical_data) == 0:
        raise DataError("No Data returned for ('%s', %s - %s) -> '%s' from Intrinio Company API" %
                        (ticker, start_date, end_date, tag), None)
    else:
        # only write to cache if response has some valid data
        cache.write(cache_key, api_response)

    return api_response.historical_data_dict


def _aggregate_by_year(historical_data_dict: dict):
    """
      Map historical company data by year (latest occurrence).

      Input

      [
        {'date': datetime.date(2018, 9, 29), 'value': 123.0},
        {'date': datetime.date(2017, 9, 30), 'value': 234.0}
      ]

      Output

      {
        2018: 123,
        2019: 234
      }


      Parameters
      ----------
      api_response : dict
        get_company_historical_data API response

      Returns
      -------
      A dictionary of year=>value with the converted results.
    """

    converted_response = {}

    for datapoint in historical_data_dict:
        converted_response[datapoint['date'].year] = datapoint['value']

    return converted_response


def _aggregate_by_year_month(historical_data: dict):
    """
      Map historical company data by year and month and average out results.

      Input

      [
        {'date': datetime.date(2019, 9, 1), 'value': 10},
        {'date': datetime.date(2019, 9, 15), 'value': 20},
        {'date': datetime.date(2019, 10, 12), 'value': 30}
      ]

      Output

      {
        2019: {
          9 : 15,
          10 : 30
        }
      }


      Parameters
      ----------
      api_response : dict
        get_company_historical_data API response

      Returns
      -------
      A dictionary of year=>month=>value with the converted results.
    """
    if historical_data is None:
        return {}

    converted_response = {}

    # first pass assemble the basic return value
    for datapoint in historical_data:
        year = datapoint['date'].year
        month = datapoint['date'].month

        if year not in converted_response:
            converted_response[year] = {}
        if month not in converted_response[year]:
            converted_response[year][month] = []

        converted_response[year][month].append(datapoint['value'])

    # second pass calculate averages
    for year in converted_response.keys():
        for month in converted_response[year]:
            converted_response[year][month] = sum(
                converted_response[year][month]) / len(converted_response[year][month])

    return converted_response


@atexit.register
def shutdown():
    """
      As of this writing (March 2020) there is a bug in the Intrinion API caused by this:
      https://github.com/swagger-api/swagger-codegen/issues/9991

      that prevents the threads in the API to cleanly shut down.
      This is a workaround until a proper fix is released.

      This code exists in the API source, but it's not invoked reliably, so we force
      its invocation
    """
    FUNDAMENTALS_API.api_client.pool.close()
    FUNDAMENTALS_API.api_client.pool.join()
    COMPANY_API.api_client.pool.close()
    COMPANY_API.api_client.pool.join()
    SECURITY_API.api_client.pool.close()
    SECURITY_API.api_client.pool.join()
