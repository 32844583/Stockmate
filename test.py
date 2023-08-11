import yfinance as yf
import pandas_ta as ta
from datetime import datetime, timedelta

def is_buy_in_overbought(stock_symbol, target_date, rsi_period, rsi_threshold, judge):
    # 計算開始日期（前兩個月）
    start_date = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=60)).strftime('%Y-%m-%d')
    
    # 從Yahoo Finance獲取股票數據
    stock_data = yf.download(stock_symbol, start=start_date, end=target_date)
    
    # 計算RSI
    stock_data['RSI'] = ta.rsi(stock_data['Close'], length=rsi_period)
    
    # 判斷是否在RSI超買區
    if judge == 'buy':
        if stock_data['RSI'].iloc[-1] >= rsi_threshold:
            return "買點在RSI超買區"
        else:
            return "買點不在RSI超買區"
    else:
        if stock_data['RSI'].iloc[-1] <= rsi_threshold:
            return "賣點在RSI超賣區"
        else:
            return "賣點不在RSI超賣區"

# 使用範例
stock_symbol = "AAPL"  # 股票代碼
target_date = "2023-08-01"  # 指定日期
rsi_period = 14  # RSI的計算週期
rsi_threshold = 70  # 超買區閾值
judge = 'buy'

result = is_buy_in_overbought(stock_symbol, target_date, rsi_period, rsi_threshold, judge)
print(result)


# 使用範例
stock_symbol = "AAPL"  # 股票代碼
target_date = "2023-08-01"  # 指定日期
rsi_period = 28  # RSI的計算週期
rsi_threshold = 30  # 超買區閾值
judge = 'sell'
result = is_buy_in_overbought(stock_symbol, target_date, rsi_period, rsi_threshold, judge)
print(result)