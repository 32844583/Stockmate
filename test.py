import yfinance as yf
ticker = yf.Ticker('6150.TWO')
stock_data = ticker.history(period='1y')
print(stock_data.tail(30))