"""test_script.py

A general purpose test script. Nothing to see here.
"""
import argparse
import logging
import logging
from datetime import datetime, timedelta, time
from datetime import date, time
import pandas_market_calendars as mcal
import pandas as pd
from strategies.macd_crossover_strategy import MACDCrossoverStrategy
from support import logging_definition, util, constants
import connectors.yfinance_data as yfinance
from model.ticker_list import TickerList
from support import constants
from support.configuration import Configuration
from exception.exceptions import ValidationError

#
# Main script
#

log = logging.getLogger()


def main():
    '''
        Main testing script
    '''
    try:

        ticker_list = TickerList.from_local_file(
            "%s/macd_tickers.json" % (constants.APP_DATA_DIR))

        config = Configuration.from_local_config(
            constants.STRATEGY_CONFIG_FILE_NAME)

        #macd_strategy = MACDCrossoverStrategy.from_configur    ation(config, 'sa')
        macd_strategy = MACDCrossoverStrategy(
            ticker_list, date(2021, 5, 7), 0.0016, 12, 26, 9)

        MACDCrossoverStrategy.preload_financial_data(ticker_list, date(2021, 5, 7), 200)

        macd_strategy.generate_recommendation()
        macd_strategy.display_results()

        '''price_df = yfinance.get_enriched_prices('SPY', datetime(2021, 1, 1), datetime(2021, 4, 25))

        price_df[yfinance.get_macd_column(12, 26)]
        price_df[yfinance.get_macd_signal_column(12, 26, 9)]

        print(price_df.loc['2021-01-05'])
        print(price_df.loc['2021-01-05']['Close'])
        print(price_df.loc['2021-01-05'][yfinance.get_macd_column(12, 26)])
        print(price_df.loc['2021-01-05'][yfinance.get_macd_signal_column(12, 26, 9)])
        '''
    except Exception as e:
        log.error("Could run script, because, %s" % (str(e)))
        #raise e

if __name__ == "__main__":
    main()
