from zipline.api import order, record, symbol

def initialize(context):
    context.has_ordered = False
    context.symbols = ['AAPL']

def handle_data(context, data):
    if not context.has_ordered:
        for stock in context.symbols:
            order(symbol('AAPL'), 1000)
        context.has_ordered = True
