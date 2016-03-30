
from datetime import datetime

from zipline.algorithm import TradingAlgorithm
from zipline.utils.factory import load_from_yahoo
from zipline.api import order, record, symbol, symbols
from zipline.utils.factory import load_from_yahoo

import os
import pytz

def from_yahoo():
	start = datetime(2012, 1, 1, 0, 0, 0, 0, pytz.utc)
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
		print result.head()

