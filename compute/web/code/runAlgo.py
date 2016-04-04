
from datetime import datetime

from zipline.algorithm import TradingAlgorithm
from zipline.utils.factory import load_from_yahoo
from zipline.api import order, record, symbol, symbols
from zipline.utils.factory import load_from_yahoo

import os
import pytz

def from_yahoo():
	start = datetime(2016, 1, 1, 0, 0, 0, 0, pytz.utc)
	end = datetime(2016, 3, 8, 0, 0, 0, 0, pytz.utc)
	tickers = ['AAPL', 'GOOGL']
	return load_from_yahoo(stocks=tickers, indexes={}, start=start, end=end)

if __name__=='__main__':
	if len(os.sys.argv)!=2:
		print "input strategy required"
	else:
		_, script = os.sys.argv
		algo = TradingAlgorithm(script=open(script).read(), data_frequency='daily')

		data = from_yahoo()
		result = algo.run(data)
		
        result.index.name = 'period'
        result = result.reset_index()
        result['period'] = result['period'].apply(lambda x: x.strftime('%Y-%m-%d'))
        columns = result.columns.values.tolist()
        columns.pop(columns.index("transactions"))
        columns = ['period', 'algo_volatility', 'algorithm_period_return', 
        'alpha', 'benchmark_period_return', 'benchmark_volatility', 
        'beta', 'capital_used', 'ending_cash', 'ending_exposure', 'ending_value', 
        'excess_return', 'gross_leverage', 'information', 'long_exposure', 
        'long_value', 'longs_count', 'max_drawdown', 'max_leverage', 'net_leverage', 
        #'orders', 'period_close', 'period_open', 
        'period_label', 'pnl', 
        'portfolio_value', 'positions', 'returns', 'sharpe', 'short_exposure', 
        'short_value', 'shorts_count', 'sortino', 'starting_cash', 'starting_exposure', 
        'starting_value', 'trading_days', 'treasury_period_return']

        print result[['period','algorithm_period_return','returns','sharpe', 'max_drawdown']].tail()
        result[columns].to_json(orient="records")

