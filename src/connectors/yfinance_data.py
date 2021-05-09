"""Author: Mark Hanegraaff -- 2021

    Yahoo Finance connector. This class offers various API wrappers to the
    service, and can enrich pricing data to generate various indicators. 
    
    It leverages the "yfinance" library to integract with Yahoo and "stock-pandas"
    to enrich the data.
"""

import yfinance as yf
import logging
import pandas as pd
from stock_pandas import StockDataFrame
from datetime import date, datetime, timedelta
from exception.exceptions import DataError, ValidationError
from support.financial_cache import cache

log = logging.getLogger()


YFINANCE_CACHE_PREFIX = 'yfinance'


#pd.set_option("display.max_rows", None, "display.max_columns", None)

def test_api_endpoint():
    """
      Tests the API endpoint directly and throws a DataError if
      anything goes wrong. 
      This is used to validate connetivity to the Yahoo Finance service
    """
    ticker_symbol = "SPY"
    try:
      yf.Ticker(ticker_symbol).info
    except Exception as e:
      raise DataError("Could not read %s ticker info" % ticker_symbol, e)


def get_enriched_prices(ticker: str, price_start : datetime, price_end: datetime):
    '''
      Returns a pricing data frame based on the yfinance API and enriched using
      the stock-pandas library. 
      
      https://pypi.org/project/stock-pandas/

      The dataframe contains these colums

      ['Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits']

      Parameters
      ----------
      ticker : str
        Ticker Symbol
      start_date : object
        The beginning price date as python date object
      end_date : object
        The end price date as python date object
    '''
    def date_to_string(date: date):
      """
        returns a string representation of a date that is usable by the intrinio API

        Returns
        ----------
        A string formatted as YYYY-MM-DD. This is the format used by most Intrinio APIs
      """
      return date.strftime("%Y-%m-%d")

    start = date_to_string(price_start)
    end = date_to_string(price_end + timedelta(days=1))

    cache_key = "%s-%s-%s-%s-%s" % (YFINANCE_CACHE_PREFIX,
                                  ticker, start, end, "prices")

    price_df_json = cache.read(cache_key)

    if price_df_json is None:
      try:
        yf_ticker = yf.Ticker(ticker)
        price_df = StockDataFrame(yf_ticker.history(start=start, end=end))
        cache.write(cache_key, price_df.to_json())
      except Exception as e:
        raise DataError("Could not read prices from Yahoo (start_date=%, end_date=%s)" % (start_date, end_date), e)
    else:
      price_df = StockDataFrame(pd.read_json(price_df_json))

    price_df.alias('close', 'Close')
    return price_df


def get_macd_column(fast_period: int, slow_perdiod: int):
  return "macd:%d,%d" % (fast_period, slow_perdiod) 

def get_macd_signal_column(fast_period: int, slow_perdiod: int, signal_period: int):
  return "macd.signal:%d,%d,%d" % (fast_period, slow_perdiod, signal_period) 