"""Author: Mark Hanegraaff -- 2020

This module contains a collection of calculations shared by the trading
strategies contained in this package.
"""
import pandas as pd
from datetime import date
from connectors import intrinio_data
from exception.exceptions import ValidationError, CalculationError, DataError


def mark_to_market(data_frame: object, ticker_col_name: str, price_col_name: str, price_date: date):
    """
        Peforms a Mark to Market on a Pandas dataframe representing
        a set of stocks given a price date. This is used
        to calculate returns on a portfolio generated by one of the
        strategies

        The dataframe must contain a ticker and price column, which are defined
        via the parameters and will add:

        * current_price
        * actual_return

        Parmeters
        ---------
        data_frame: Pandas DataFrame
            Portfolio dataframe
        ticker_col_name: str
            Name of the ticker column
        price_col_name: str
            Name of the price column
        price_date: date
            Price date, current or historical

        Returns
        ---------
        A new dataframe with the added columns

    """

    if (data_frame is None or price_date is None):
        raise ValidationError(
            "Invalid Parameters supplied to Mark to Market calculation", None)

    if (ticker_col_name not in data_frame.columns
            or price_col_name not in data_frame.columns):
        raise ValidationError(
            "Could not extract required fields for Mark to Market calculation", None)

    mmt_prices = []

    for ticker in data_frame[ticker_col_name]:
        try:
            latest_price = intrinio_data.get_daily_stock_close_prices(
                ticker, price_date, price_date)

            mmt_prices.append(latest_price[price_date.strftime("%Y-%m-%d")])
        except Exception as e:
            raise DataError("Could not perform MMT calculation", e)

    data_frame['current_price'] = mmt_prices
    data_frame['actual_return'] = (data_frame['current_price'] -
                                   data_frame[price_col_name]) / data_frame[price_col_name]
    return data_frame