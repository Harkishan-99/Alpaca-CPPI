import time
import numpy as np
import pandas as pd
import alpaca_trade_api as tradeapi


API_KEY = "ENTER YOUR API KEY"
API_SECRET = "ENTER YOUR API SECRET" 
api = tradeapi.REST(API_KEY, API_SECRET, base_url='https://paper-api.alpaca.markets', api_version='v2')

class CPPI:

    def __init__(self, asset:str, cppi_budget:int, floor_percent:float=0.8, asset_muliplier:int=6):
        """
        The CPPI algorithm class.

        :param asset :(str) the ticker symbol of the asset to invest in. E.g. : AAPL or GS
        :param cppi_budget :(int) the budget to be allocated to CPPI algorithm.
        :param floor_percent :(float) this will be the floor percentage that the CPPI will
                               try to maintain. Deafult is 80% of the initial budget.
        :param asset_muliplier :(int) the risky asset mutiplier for the CPPI. Usually it is
                                 set between 4 and 8. Deafult is 6.
        """
        self.asset = asset
        self.CPPI = cppi_budget
        self.floor_value = cppi_budget * floor_percent
        self.m = asset_muliplier
        self.position_value = 0
        #check if the account permits the given budget
        self._check_budget()

    def _check_budget(self):
        """
        A function that checks if the current account value meets the CPPI budget.
        """
        AC = api.get_account()
        client_budget = float(AC.cash)
        if self.CPPI > client_budget:
            raise Exception("The cash in the account is less than the CPPI budget.")


    def rebalance(self, dollar_amount:float):
        """
        This function will check if any reblancing is required based on the
        recent CPPI risk budget allocation.

        :param dollar_amount : (float) current risk budget.
        """
        #check if a position exists in the asset
        try:
            pos = api.get_position(self.asset)
            #if position value > dollar_amount reduce the holding by the difference
            excess_risk = self.position_value - dollar_amount
            if abs(excess_risk) > 0:
                #find the excess qty to be squared off
                current_asset_price = float(pos.current_price)
                excess_qty = int(abs(excess_risk) / current_asset_price)
                if excess_risk > 0:
                    order = api.submit_order(symbol=self.symbol,
                                             qty=excess_qty,
                                             side='sell',
                                             type='market',
                                             time_in_force='day')
                elif excess_risk < 0:
                    #increse the holding by the difference
                    order = api.submit_order(symbol=self.symbol,
                                             qty=excess_qty,
                                             side='buy',
                                             type='market',
                                             time_in_force='day')

        except Exception as e:
            #long the entire budget
            current_asset_price = api.get_last_trade(self.asset).price
            qty = int(dollar_amount / current_asset_price)
            order = api.submit_order(symbol=self.asset,
                                     qty=qty,
                                     side='buy',
                                     type='market',
                                     time_in_force='day')


    def get_position_value(self):
        """
        Get the current value of the asset position.
        """
        value, returns = 0, 0
        try:
            #get the position details
            pos = api.get_position(self.asset)
            #return = (current_price/avg_entry_price) - 1
            returns = (float(pos.current_price)/float(pos.avg_entry_price)) - 1
            #value = current_price * qty
            value = float(pos.current_price) * int(pos.qty)

        except Exception as e:
            #position doesn't exists
            pass
        return value, returns

    def _check_market_open(self):
        """
        A function to check if the market open. If not the sleep till
        the market opens.
        """
        clock = api.get_clock()
        if clock.is_open:
            pass
        else:
            time_to_open = clock.next_open - clock.timestamp
            print(
                f"Market is closed now going to sleep for {time_to_open.total_seconds()//60} minutes")
            time.sleep(time_to_open.total_seconds())

    def run(self, period_in_hours:int=24):
        """
        Start the CPPI algorithm.

        :param period_in_hours :(int) rebalancing period in hours.
                                 Default is 24 hours.
        """
        self._check_market_open()
        while True:
            #calculate the floor value
            floor = self.CPPI - self.floor_value
            #compute the risk budget
            risk_budget = max(min(self.m*floor, self.CPPI), 0)
            print('Floor : ', floor  ,' Risk Budget : ', risk_budget)
            #order the risk budget
            self.rebalance(risk_budget)
            cash = self.CPPI - risk_budget
            #sleep till next rebalancing.
            time.sleep(period_in_hours*60*60)
            self._check_market_open()
            #re-calculate the CPPI value based on the asset holding returns
            self.position_value, returns = self.get_position_value()
            self.CPPI = risk_budget * (1 + returns) + cash

def main(asset, cppi_budget=10000, floor_percent=0.8, asset_muliplier=4, rebalance_period=1):
    cppi = CPPI(asset, cppi_budget, floor_percent, asset_muliplier)
    cppi.run(rebalance_period*24)
