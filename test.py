import pandas as pd

# 创建一个示例数据框
df = pd.DataFrame({'A': ['abc', 'def', 'ghi', 'jkl']})

# 计算列 A 中包含 'a' 的行数
count = df['A'].str.contains('a').sum()

# 查看结果
print(count)
