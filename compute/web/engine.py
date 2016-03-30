import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
from concurrent.futures import ProcessPoolExecutor
from tornado.ioloop import IOLoop
from tornado import web, gen
from tornado.options import define, options
from tornado.escape import json_encode

import os
import pytz
import logging
import json
import urllib
from datetime import datetime

import concurrent.futures

from zipline.algorithm import TradingAlgorithm
from zipline.utils.factory import load_from_yahoo
from zipline.api import order, record, symbol

import gcloud
from gcloud import datastore

from pandas import DataFrame, concat

logger = logging.getLogger('')
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

SYMBOLS_SUPPORTED = ['AAPL', 'GOOGL']

#client = gcloud.datastore.Client('tigris-1242')

def run_algo(code, d):
    def load_from_datastore(stocks, start, end):

        df = DataFrame()

        for symbol in stocks:
            parent_key = client.key('Asset', symbol)
            query = client.query(kind='Tick', ancestor=parent_key)
            query.add_filter('Timestamp', '>=', start)
            query.add_filter('Timestamp', '<=', end)

            df_t = DataFrame([(t.get('Timestamp'), t.get('Close')) for t in query.fetch()], 
                            columns=['Timestamp', symbol])

            df_t = df_t.set_index('Timestamp')
            df = concat([df, df_t], axis=1)

        return df

    def querydata(symbols, start, end, useDatastore=True):
        def utc(dt):
            return datetime(dt.year, dt.month, dt.day, 0, 0, 0, 0, pytz.utc)

        if not isinstance(start, datetime):
            start = utc(datetime.strptime(start, '%Y-%m-%d'))
            end = utc(datetime.strptime(end, '%Y-%m-%d'))

        if useDatastore:
            return load_from_datastore(stocks=symbols, start=start, end=end)
        else:
            return load_from_yahoo(stocks=symbols, indexes={}, start=start, end=end)
    
    algo = TradingAlgorithm(script=code, capital_base=float(d['fund']))
    data = querydata(d['symbols'].split(','), 
                    d['start'], d['end'], not d['useYahoo'])
    return algo.run(data)


class ZiplineCompute(tornado.web.RequestHandler):

    @gen.coroutine
    def post(self):
        d = json.loads(self.request.body)

        symbols = d['symbols'].split(',')
        m = list(filter(lambda x: not x in SYMBOLS_SUPPORTED, symbols))

        #self.set_header('Access-Control-Allow-Origin', '*')

        if len(m) and not d['useYahoo']:
            self.set_status(500)
            self.write('symbols %s not supported' % ','.join(m))
        else:
            with concurrent.futures.ProcessPoolExecutor() as executor:
                try:
                    fut = executor.submit(run_algo, d['code'], d)
                    result = yield fut

                    result.index.name = 'period'
                    result = result.reset_index()
                    result['period'] = result['period'].apply(lambda x: x.strftime('%Y-%m-%d'))

                    self.set_header('Content-Type', 'application/json')

                    self.write(result[['period', 'algorithm_period_return']].to_json(orient='records'))
                except Exception as e:
                    self.set_status(500)
                    self.write(str(e))
                    #raise tornado.web.HTTPError(500, str(e), statusText=str(e))


    def get(self):
        self.write("ZiplineCompute is running")

class Application(tornado.web.Application):

    def __init__(self):
        handlers = [
                        (r"/zipline", ZiplineCompute),
                    ]

        settings = dict(
                    template_path=os.path.join(os.path.dirname(__file__), "templates"),
                    static_path=os.path.join(os.path.dirname(__file__), "static"),
                    cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
                    login_url="/auth/login",
                    debug=True
                    )

        tornado.web.Application.__init__(self, handlers, **settings)

        self.max_workers = 20

if __name__ == '__main__':
    app = Application()
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(8089)
    logger.info("zipline started")
    tornado.ioloop.IOLoop.instance().start()