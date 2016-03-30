import pytz
from datetime import datetime

from zipline.utils.factory import load_from_yahoo

import gcloud
from gcloud import datastore

from pandas import DataFrame, concat

client = gcloud.datastore.Client('tigris-1242')

def from_yahoo():
	start = datetime(2006, 1, 1, 0, 0, 0, 0, pytz.utc)
	end = datetime(2016, 3, 8, 0, 0, 0, 0, pytz.utc)
	tickers = ['AAPL', 'GOOGL']

	return load_from_yahoo(stocks=tickers, indexes={}, start=start, end=end)

def create_entities(dfa, k):
	d = []
	dfa = dfa.reset_index()
	dfa.columns = ['Timestamp', 'Close']

	for t in dfa.to_dict('records'):
		tick = datastore.Entity(client.key('Tick', parent=k))
		tick.update(t)
		d.append(tick)

	return d

def populate(df):
	for ticker in df.columns:
		
		parent_key = client.key('Asset', ticker)
		asset = datastore.Entity(parent_key)
		asset.update({'name':ticker, 'exchange':'NASDAQ'})
		client.put(asset)

		dd = create_entities(df[ticker],parent_key)
		if len(dd)<=500:
			client.put_multi(dd)
		else:
			for t in range(len(dd))[::500]:
				if t+500>=len(dd):
					client.put_multi(dd[t:])
				else:
					client.put_multi(dd[t:t+500])

def check(start, end, tickers):
	df = DataFrame()

	for symbol in tickers:
		parent_key = client.key('Asset', symbol)
		query = client.query(kind='Tick', ancestor=parent_key)
		query.add_filter('Timestamp', '>=', start)
		query.add_filter('Timestamp', '<=', end)

		df_t = DataFrame([(t.get('Timestamp'), t.get('Close')) for t in query.fetch()], 
						columns=['Timestamp', symbol])

		df_t = df_t.set_index('Timestamp')
		df = concat([df, df_t], axis=1)

	return df 


# start = datetime(2016, 1, 1, 0, 0, 0, 0, pytz.utc)
# end = datetime(2016, 1, 10, 0, 0, 0, 0, pytz.utc)
# df = check(start, end, ['AAPL', 'GOOGL'])
# print df.head()

populate(from_yahoo())

