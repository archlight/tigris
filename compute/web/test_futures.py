import concurrent.futures
import time
import random

from tornado import gen
from tornado.ioloop import IOLoop

def power(n):
	time.sleep(random.randint(1,10))
	return n*n

@gen.coroutine
def task():
	with concurrent.futures.ProcessPoolExecutor() as executor:
		fut = executor.submit(power, 2)
		print "start"
		result = yield fut
		print "finish"
		print result

task()
print "switch to another task"
IOLoop.instance().start()