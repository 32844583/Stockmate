import pandas as pd
from datetime import datetime
# 原始数据
# data = {'trade_id': [2, 3, 8, 9],
#         'user_id': [2, 2, 2, 2],
#         '日期': ['2023/6/5', '2023/6/12', '2023/6/10', '2023/7/7'],
#         '股票代號': ['2330.TW', '2330.TW', '2330.TW', '2330.TW'],
#         '股票名稱': ['台積電', '台積電', '台積電', '台積電'],
#         '價格': [553, 555, 506, 567],
#         '數量': [30, 30, 30, 30],
#         '買/賣': ['買', '賣', '買', '賣'],
#         '原因': ['靠感覺', '靠感覺', '靠感覺', '靠感覺'],
#         '使用規則': ['我的策略一', '我的策略一', '我的策略二', '我的策略二']}
# df = pd.DataFrame(data)

# df.to_csv('temp.csv', encoding='utf-8-sig')

new_data = {'trade_id': 10,
            'user_id': 2,
            '日期': '2023/8/1',
            '股票代號': '2330.TW',
            '股票名稱': '台積電',
            '價格': 600,
            '數量': 40,
            '買/賣': '買',
            '原因': '靠感覺',
            '使用規則': '我的策略一'}

df = pd.read_csv('temp.csv', encoding='utf-8-sig')
df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)

# 计算每种策略的总损益和报酬率
result = []
for strategy in df['使用規則'].unique():
    df_strategy = df[df['使用規則'] == strategy]
    start_date = df_strategy['日期'].min()
    end_date = df_strategy['日期'].max()
    period = f"{start_date}-{end_date}"
    stock_name = df_strategy['股票名稱'].iloc[0]
    total_profit = 0
    for _, row in df_strategy.iterrows():
        if row['買/賣'] == '買':
            total_profit -= row['價格'] * row['數量']
        else:
            total_profit += row['價格'] * row['數量']
    return_rate = total_profit / (df_strategy[df_strategy['買/賣'] == '買']['價格'] * df_strategy[df_strategy['買/賣'] == '買']['數量']).sum()
    result.append([period, stock_name, strategy, total_profit, return_rate])

result_df = pd.DataFrame(result, columns=['交易期間', '股票名稱', '使用規則', '總損益', '報酬率'])
# print(result_df)
result_df.to_csv('result.csv', encoding='utf-8-sig')

df = pd.read_csv('result.csv', encoding='utf-8-sig')
print(df['交易期間'].dtype)