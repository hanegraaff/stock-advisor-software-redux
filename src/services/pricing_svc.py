"""Author: Mark Hanegraaff -- 2021
"""

import logging
from datetime import date
import connectors.yfinance_data as yfinance

log = logging.getLogger()


class PricingSvc():
    '''
        The pricing service class loads and caches pricing data so that it can be
        shared with the various strategies while minimizing API calls to Yahoo Finance
        and avoiding the need to re-load similar data.
    '''

    pricing_dict = {}

    @classmethod
    def load_financial_data(cls, ticker_symbol: str, start_date: date, end_date: date):
        '''
            Loads a range of prices for a ticker symbol and caches them in memory.
            If prices already exist, they will be overwritten.

            Parameters
            ----------
            ticker_symbol: int
                xxx
            start_date: date
                xxx
            end_date: date
                xxx

            Returns
            ----------
            Returns the pricing dataframe that was just loaded
        '''

        log.info("Loading Prices for ticker: %s, from: %s, to: %s" % (ticker_symbol, start_date, end_date))
        cls.pricing_dict[ticker_symbol] = yfinance.get_enriched_prices(
                ticker_symbol, start_date, end_date)

        return cls.pricing_dict


    @classmethod
    def get_pricing_dataframe(cls, ticker_symbol: str):
        '''
            Returns the currently available pricing dataframe, or None if
            one does not exist
        '''
        return cls.pricing_dict.get(ticker_symbol, None)