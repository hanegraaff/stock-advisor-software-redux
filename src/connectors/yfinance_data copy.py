"""Author: Mark Hanegraaff -- 2020

This module is a value add to the Yahoo Finance and implements a 
number of functions to read current and historical prices and indicators
"""

import yfinance as yf
import logging
from datetime import date, datetime, timedelta
from exception.exceptions import DataError, ValidationError
from support.financial_cache import cache

log = logging.getLogger()


YFINANCE_CACHE_PREFIX = 'yfinance'

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

'''
  Testing APIs using requests package
'''
def test_api_endpoint():
    """
      Tests the API endpoint directly and throws a DataError if
      anything goes wrong. 
      This is used to validate that the API key works
    """
    pass

def date_to_string(date: date):
    """
      returns a string representation of a date that is usable by the intrinio API

      Returns
      ----------
      A string formatted as YYYY-MM-DD. This is the format used by most Intrinio APIs
    """
    return date.strftime("%Y-%m-%d")

#@retry_server_errors
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

    ticker = yf.Ticker(ticker)

    start = date_to_string(start_date)
    end = date_to_string(end_date + timedelta(days=1))

    hist = ticker.history(start=start, end=end)

    print(hist)


def get_latest_close_price(ticker, price_date: datetime, max_looback: int):
    """
      Retrieves the most recent close price given a price_date and a lookback window

      Returns
      -----------
      a tuple of date, float with the latest price date and price value
    """

    pass

'''
  Price indicator APIs using the SECURITY_API client
'''


#@retry_server_errors
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

    pass


#@retry_server_errors
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

    pass


