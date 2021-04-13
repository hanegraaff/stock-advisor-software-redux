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

from support import logging_definition, util, constants
from connectors import yfinance_data as yf
from strategies.price_dispersion_strategy import PriceDispersionStrategy
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

        '''ticker_list = TickerList.from_local_file(
            "%s/djia30.json" % (constants.APP_DATA_DIR))

        config = Configuration.try_from_s3(
            constants.STRATEGY_CONFIG_FILE_NAME, 'sa')

        #macd_strategy = MACDCrossoverStrategy.from_configuration(config, 'sa')
        macd_strategy = MACDCrossoverStrategy(
            ticker_list, date(2020, 6, 16), 0.0016, 12, 16, 9)
        macd_strategy.generate_recommendation()
        macd_strategy.display_results()'''


        yf.get_daily_stock_close_prices('SPY', datetime(2021, 4, 9), datetime(2021, 4, 12))



    except Exception as e:
        log.error("Could run script, because, %s" % (str(e)))
        #raise e

if __name__ == "__main__":
    main()
