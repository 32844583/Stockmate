from twstock import Stock
import datetime
import pandas as pd
# 建立 Stock 實例
stock = Stock('4171')

# 設定查詢日期範圍
end = datetime.date.today()
start = end - datetime.timedelta(days=365)

# 獲取歷史資料
data = stock.fetch_from(2020, 1)

print(data[0])
stock_data = pd.DataFrame(data, columns=['date', 'Volume', 'turnover' , 'Open', 'High', 'Low', 'Close', 'change', 'transaction'])

stock_data.drop(['turnover', 'transaction', 'change'], axis=1, inplace=True)
print(stock_data.info())
print(stock_data)
# stock_data = stock_data.rename(columns={'Date': '日期'})
# stock_data['日期'] = stock_data['日期'].dt.strftime('%Y-%m-%d')
# print(stock_data)