from datetime import datetime, timedelta
from datetime import date
import feedparser
import pandas as pd
import twstock
import re
import time
import requests
from bs4 import BeautifulSoup
from pprint import pprint
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from decimal import Decimal
import math
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import Date
from sqlalchemy import and_
import json
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from flask_bcrypt import Bcrypt
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dateutil.relativedelta import relativedelta
from sqlalchemy import MetaData
import pandas_ta as ta
pd.options.mode.chained_assignment = None  # default='warn'
naming_convention = {
"ix": "ix_%(column_0_label)s",
"uq": "uq_%(table_name)s_%(column_0_name)s",
"ck": "ck_%(table_name)s_%(constraint_name)s",
"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
"pk": "pk_%(table_name)s"
}

app = Flask(__name__, static_folder='static')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stock.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False

app.config['SECRET_KEY'] = 'thisisasecretkey'

db = SQLAlchemy(app, metadata=MetaData(naming_convention=naming_convention))
migrate = Migrate(app ,db)
bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

buy_df = pd.DataFrame()
sell_df = pd.DataFrame()
trade_df = pd.read_csv('trades.csv', encoding='utf-8-sig')

current_dir = os.getcwd()
filename = 'cards.csv'

if not os.path.exists(os.path.join(current_dir, filename)):
    df = pd.DataFrame(columns=["card_id", "user_id", "卡組名稱", "使用卡牌"])
    df.to_csv("cards.csv", index=False, encoding='utf-8-sig')

card_df = pd.read_csv('cards.csv', encoding='utf-8-sig')

review_df = pd.read_csv('reviews.csv', encoding='utf-8-sig')
chart_data = 0
trade_point = 0
# Sample User class for Flask-Login
class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))



class RegisterForm(FlaskForm):
    username = StringField(validators=[
                           InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})

    password = PasswordField(validators=[
                             InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Password"})

    submit = SubmitField('Register')

    def validate_username(self, username):
        existing_user_username = User.query.filter_by(
            username=username.data).first()
        if existing_user_username:
            raise ValidationError(
                'That username already exists. Please choose a different one.')


class LoginForm(FlaskForm):
    username = StringField(validators=[
                           InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})

    password = PasswordField(validators=[
                             InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Password"})

    submit = SubmitField('Login')


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('index'))
    return render_template('login.html', form=form)


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@ app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data)
        new_user = User(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('register.html', form=form)


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    global  trade_df
    user_id = int(current_user.get_id())
    symbol = "2330.TW"
    if request.method=='POST':
        symbol = request.form['symbol']

    # -----------------取得資料----------------#


    df = trade_df.loc[(trade_df['股票代號'] == symbol) & (trade_df['user_id'] == user_id)]

    if df.empty:
        print(df)
        stock = twstock.Stock(symbol[:4]) # 台積電的股票代碼為 2330
        data = stock.fetch_from(2023, 7) # 從 start_date 開始查詢
    else:
        temp = pd.DataFrame()
        temp['日期'] = df['日期'].apply(lambda x: datetime.strptime(x, '%Y/%m/%d'))
        stock_symbol = symbol[:4]
        start_date = temp['日期'].min() - relativedelta(months=2)
        end_date = temp['日期'].max() + relativedelta(days=2)
        print(start_date)
        print(end_date)
        stock = twstock.Stock(stock_symbol) # 台積電的股票代碼為 2330
        data = stock.fetch_from(start_date.year, start_date.month) # 從 start_date 開始查詢

        data = [d for d in data if start_date <= d.date <= end_date]
    data = pd.DataFrame(data, columns=['Date', 'Volume', 'turnover' , 'Open', 'High', 'Low', 'Close', 'change', 'transaction'])
    
    data.drop(['turnover', 'transaction', 'change'], axis=1, inplace=True)
    print(data)

    # -----------------取得資料----------------#
    dt_all = pd.date_range(start=data['Date'].iloc[0],end=data['Date'].iloc[-1])
    dt_obs = [d.strftime("%Y-%m-%d") for d in pd.to_datetime(data['Date'])]
    dt_breaks = [d for d in dt_all.strftime("%Y-%m-%d").tolist() if not d in dt_obs]

    fig = make_subplots(rows=2, cols=1,
                        shared_xaxes=True,
                        vertical_spacing=0.1,
                        row_width=[0.4, 0.4])


    data['MA20'] = data['Close'].rolling(window=20).mean()
    data['MA5'] = data['Close'].rolling(window=5).mean()
    fig.add_trace(go.Scatter(x=data['Date'],
                             y=data['MA5'],
                             opacity=0.7,
                             line=dict(color='blue', width=2),
                             name='MA 5',hoverinfo='skip'), row=1, col=1)
    fig.add_trace(go.Scatter(x=data['Date'],
                             y=data['MA20'],
                             opacity=0.7,
                             line=dict(color='orange', width=2),
                             name='MA 20',hoverinfo='skip'), row=1, col=1)

    # revise: candlestick + scatter 
    cand = go.Figure(go.Candlestick(x=data['Date'],
                    open=data['Open'], high=data['High'],
                    low=data['Low'], close=data['Close'],
                    increasing_line_color = 'red',
                    decreasing_line_color = 'green'))


    fig.add_trace(cand.data[0], row=1, col=1)


    # volume bar

    temp_vol = {'vol': data['Volume'].tolist(), 'last_vol': data['Volume'].shift(1).tolist()}
    temp_vol = pd.DataFrame(data=temp_vol)
    temp_vol = temp_vol.dropna()
    colors = ['red' if row['vol'] - row['last_vol'] >= 0
              else 'green' for index, row in temp_vol.iterrows()]
    colors.insert(0, 'green')
    fig.add_trace(go.Bar(x=data['Date'], y=data['Volume'], marker_color=colors, name="volume"),
                   secondary_y=False, row=2, col=1)

    fig.update_xaxes(
        rangebreaks=[dict(values=dt_breaks)]
    )

    fig.update_layout(
        autosize=False,
        width=650,
        height=650,
        margin=dict(l=0, r=0, t=0, b=0),
        )

    fig.update_layout(xaxis_rangeslider_visible=False, 
                      xaxis_type="date")

    stock_name = twstock.codes[symbol.split('.')[0]].name

    current_dir = os.getcwd()
    filename = 'trades.csv'
    if not os.path.exists(os.path.join(current_dir, filename)):
        df = pd.DataFrame(columns=["trade_id", "user_id", "日期", "股票代號", "股票名稱", "價格", "數量", "買/賣", "原因", "使用規則", "遵守", "違反", "待決定"])

        df.to_csv("trades.csv", index=False, encoding='utf-8-sig')

    df['日期'] = df['日期'].str.replace("-", "/")

    df['日期'] = pd.to_datetime(df['日期'])

    fig.add_trace(go.Scatter(x=df.loc[df['買/賣'] == '買', '日期'],
    y=df.loc[df['買/賣'] == '買', '價格'],
    mode='markers',
    marker=dict(symbol='triangle-up-open', color='black', line=dict(color='black', width=2), size=10),
    text=df.loc[df['買/賣'] == '買', '買/賣'],
    customdata=df.loc[df['買/賣'] == '買', ['數量', '原因']],
    hovertemplate='<b>日期</b>: %{x}<br><b>價格</b>: %{y}<br><b>數量</b>: %{customdata[0]}<br><b>買賣</b>: %{text}<br><b>原因</b>: %{customdata[1]}<extra></extra>'),
    row=1, col=1)

    fig.add_trace(go.Scatter(x=df.loc[df['買/賣'] == '賣', '日期'],
    y=df.loc[df['買/賣'] == '賣', '價格'],
    mode='markers',
    marker=dict(symbol='triangle-down-open', color='black', line=dict(color='black', width=2), size=10),
    text=df.loc[df['買/賣'] == '賣', '買/賣'],
    customdata=df.loc[df['買/賣'] == '賣', ['數量', '原因']],
    hovertemplate='<b>日期</b>: %{x}<br><b>價格</b>: %{y}<br><b>數量</b>: %{customdata[0]}<br><b>買賣</b>: %{text}<br><b>原因</b>: %{customdata[1]}<extra></extra>'),
    row=1, col=1)

    df = df[(df['user_id'] == user_id) & (df['股票名稱'] == stock_name)]
    trades=df.to_dict(orient='records')

    card_df = pd.read_csv('cards.csv', encoding='utf-8-sig')
    card_df = card_df[(card_df['user_id'] == user_id)]
    cards=card_df.to_dict(orient='records')

    return render_template('index.html', plot=fig.to_html(), cards=cards, trades=trades, stock_name=stock_name, stock_code=symbol)


@app.route('/update', methods=['POST', 'GET'])
def update():
    df = pd.read_csv('cards.csv', encoding='utf-8-sig')

    user_id = int(current_user.get_id())

    value = request.args.get('value')
    cards = df.loc[(df['卡組名稱'] == value) & (df['user_id'] == user_id)]
    card_item = cards['使用卡牌'].values[0].split('-')

    card_df = df[(df['user_id'] == user_id)]

    cards=card_df.to_dict(orient='records')
    return render_template('cards.html', card_item=card_item, cards=cards)


@app.route('/cards', methods=['POST', 'GET'])
@login_required
def cards():
    global card_df
    user_id = int(current_user.get_id())
    cards = card_df.loc[(card_df['user_id'] == user_id)]
    customs = cards['使用卡牌'].tolist()

    # get all user's cards
    custom_list = []
    for custom in customs:
        temp = custom.split('-')
        index = temp.index('custom')+1
        # print(custom.split('-').index('custom')+1)
        for item in temp[index:]:
            if item not in custom_list:
                custom_list.append(item)


    if request.method == 'POST':
        customs = request.form.getlist('item')
        term = request.form.get("term", ' ')
        trend = request.form.get("trend", ' ')
        oscillators = request.form.get("oscillators", ' ')
        volatility = request.form.get("volatility", ' ')
        energy = request.form.get("energy", ' ')
        rule_name = request.form.get("rule_name", ' ')
        card_id = request.form.get("card_id", ' ')

        select_item = '-'.join([term, trend, oscillators, volatility, energy]) + '-custom-' + '-'.join(customs)
        # print(select_item.split('-'))
        # print(select_item)


        if card_id == "" :
            card_id = card_df.shape[0]
            cards = pd.DataFrame([[card_id, user_id, rule_name, select_item]], \
                columns=["card_id", "user_id", "卡組名稱", "使用卡牌"])
            cards.to_csv('cards.csv', mode='a', encoding='utf-8-sig', index=False, header=False)

        else:
            mask = cards['card_id'] == int(card_id)
            data = {
                '卡組名稱': rule_name,
                '使用卡牌': select_item,
            }
            cards.loc[mask, data.keys()] = data.values()
            cards.to_csv('cards.csv', mode='w', encoding='utf-8-sig', index=False)

        card_df = pd.read_csv('cards.csv', encoding='utf-8-sig')
        print(f'--------------新增卡組-------------')
        print(f'目前卡組 \n {cards}')
        print(f'--------------新增卡組-------------')
        # card_list = request.form.getlist('card_name') # 獲取勾選框的 value 列表
        # card_string = '-'.join(card_list) # 將列表中的元素用 '-' 串成一個字串
        # card_id = pd.read_csv('cards.csv', encoding='utf-8-sig').shape[0]
        # df = pd.DataFrame([[ card_id, user_id, rule, card_string]], \
        #     columns=["card_id", "user_id",  "卡組名稱", "使用卡牌"])
        # df = pd.read_csv('cards.csv', encoding='utf-8-sig')
        return redirect(url_for('cards'))

    cards =cards.to_dict(orient='records')
    return render_template('cards.html', cards=cards, custom_list=custom_list)


@app.route('/delete_component', methods=['GET', 'POST'])
def delete_component():
    global card_df, trade_df

    user_id = int(current_user.get_id())
    cards = card_df.loc[(card_df['user_id'] == user_id)]
    customs = cards['使用卡牌'].tolist()
    custom_list = []

    component = str(request.form['component'])

    for custom in customs:
        temp = custom.split('-')
        index = temp.index('custom')+1
        # print(custom.split('-').index('custom')+1)
        for item in temp[index:]:
            if item not in custom_list:
                custom_list.append(item)

    print(f'--------------刪除卡牌-------------')
    print(f'刪除卡牌 {component}')
    print(trade_df['遵守'].str.contains(component, regex=False).any())
    print(f'--------------刪除卡牌-------------')

    if trade_df['遵守'].str.contains(component, regex=False).any() | trade_df['違反'].str.contains(component, regex=False).any():
        flash('不可刪除套用在交易上的卡牌')
        return redirect(request.referrer)
    else:
        card_df['使用卡牌'] = card_df['使用卡牌'].replace(component, '', regex=True)
        return redirect(url_for('cards'))




@app.route('/delete_card/<int:card_id>', methods=['GET', 'POST'])
@login_required
def delete_card(card_id):
    global card_df, trade_df
    user_id = int(current_user.get_id())
    rule = card_df.loc[card_df['card_id']==card_id, "卡組名稱"].iloc[0]

    check = trade_df.loc[(trade_df['使用規則'] == str(rule))]

    if not check.empty:
        flash('不可刪除正在使用的策略')
        return redirect(request.referrer)

    print(f'--------------刪除卡組-------------')
    print(f'刪除卡組 \n {card_id}')
    print(f'刪除卡組 \n {check}')
    print(f'刪除卡組 \n {rule}')
    print(f'--------------刪除卡組-------------')
    card_df = card_df[(~(card_df['card_id'] == card_id) & (card_df['user_id'] == user_id))]
    card_df.to_csv('cards.csv', mode='w', encoding='utf-8-sig', index=False)
    return redirect(url_for('cards'))


@app.route('/add_trade', methods=['GET', 'POST'])
@login_required
def add_trade():
    global trade_df
    user_id = int(current_user.get_id())
    date = request.form.get("date")
    date = date.replace('-', '/')
    date = date.replace('/0', '/')
    stock_symbol = request.form.get("stock_symbol")
    stock_name = request.form.get("stock_name")
    price = request.form.get("price")
    quantity = request.form.get("quantity")
    action = request.form.get("action")
    reason = request.form.get("reason")
    rule = request.form.get("rule")
    trade_id = pd.read_csv('trades.csv', encoding='utf-8-sig').shape[0]
    df = pd.DataFrame([[trade_id, user_id, date, stock_symbol, stock_name, price, quantity, action, reason, rule, "", "", ""]], \
        columns=["trade_id", "user_id", "日期", "股票代號", "股票名稱", "價格", "數量", "買/賣", "原因", "使用規則", "遵守", "違反", "待決定"])
    df.to_csv("trades.csv", index=False, encoding='utf-8-sig', mode="a", header=False)
    trade_df = pd.read_csv('trades.csv', encoding='utf-8-sig')
    return redirect(request.referrer)

# 定義一個路由和函數來處理刪除交易的請求
@app.route('/delete_trade/<int:trade_id>', methods=['GET', 'POST'])
def delete_trade(trade_id):
    global trade_df
    trade_df = trade_df[~(trade_df['trade_id'] == trade_id)]
    trade_df.to_csv('trades.csv', mode='w', encoding='utf-8-sig', index=False)
    return redirect(url_for('index'))

# 定義一個路由和函數來處理編輯交易的請求
@app.route('/edit_trade/<int:trade_id>', methods=['GET', 'POST'])
def edit_trade(trade_id):
    global card_df, trade_df
    user_id = current_user.get_id()
    if request.method == 'GET':
        trade = trade_df[trade_df['trade_id'] == trade_id]
        date_str = trade['日期'].iloc[0]
        date_obj = datetime.strptime(date_str, '%Y/%m/%d')
        formatted_date_str = date_obj.strftime('%Y-%m-%d')

        trade['日期'].iloc[0] = formatted_date_str
        trade = trade.to_dict('records')
        df = card_df[(card_df['user_id'] == user_id)]
        cards=df.to_dict(orient='records')
        return render_template('edit_trade.html', cards=cards, trade=trade)
    else:
        date = request.form.get('date')

        date = date.replace('-', '/')

        date = date.replace('/0', '/')
        stock_symbol = request.form.get('stock_symbol')
        stock_name = request.form.get("stock_name")
        price = request.form.get('price')
        quantity = request.form.get('quantity')
        action = request.form.get('action')
        reason = request.form.get('reason')
        rule = request.form.get('rule')

        mask = trade_df['trade_id'] == trade_id

        data = {
            '日期': date,
            '股票代號': stock_symbol,
            '股票名稱': stock_name,
            '價格': price,
            '數量': quantity,
            '買/賣': action,
            '原因': reason,
            '使用規則': rule,
            '違反': "",
            '遵守': "",
            '待決定': "",
        }

        trade_df.loc[mask, data.keys()] = data.values()

        trade_df.to_csv('trades.csv', mode='w', encoding='utf-8-sig', index=False)

        return redirect(url_for('index'))



@app.route('/review', methods=['GET', 'POST'])
@login_required
def review():
    global trade_df, review_df
    reviews = review_df.to_dict(orient='records')
    items = trade_df.drop_duplicates(subset=['使用規則', '股票名稱'], keep='first')
    items = items.to_dict(orient='records')
    print(f'--------------載入所有績效-------------')
    print(f'所有item{reviews}')
    print(f'--------------所有績效-------------')
    return render_template('review.html', items=items, reviews=reviews)

@app.route('/options')
def options():
    rule = request.args.get('rule')
    user_id = int(current_user.get_id())
    df = pd.read_csv('trades.csv', encoding='utf-8-sig')
    cards = df.loc[(df['user_id'] == user_id) & (df['使用規則'] == rule)]
    cards.drop_duplicates(subset=['使用規則', '股票名稱'], keep='first', inplace=True)

    return jsonify(cards['股票名稱'].tolist())  

@app.route('/check_point', methods=['GET', 'POST'])
def check_point():
    global trade_df
    user_id = int(current_user.get_id())
    data = request.get_json()
    # print(f'--------------按下點位-------------')
    # print(f'資料: {data}')
    # print(f'--------------按下點位-------------')
    if data['type'] == 'sell':
        action = '賣'
    else:
        action = '買'
    
    rule = data['rule']
    options = data['option']
    date = data['date'].replace('-', '/').replace('/0', '/')
    point_data = one_point_indicator_detail(user_id, options, date, data['price'], action, rule)
    print(f'--------------按下點位-------------')
    print(f'資料: {point_data}')
    print(f'--------------按下點位-------------')
    return jsonify(point_data)
@app.route('/add_review', defaults={'review_id': 9999}, methods=['GET', 'POST'])
@app.route('/add_review/<int:review_id>', methods=['GET', 'POST'])
def add_review(review_id):
    global card_df, buy_df, sell_df, trade_df, review_df

    user_id = int(current_user.get_id())
    if review_id == 9999:
        rule = request.args.get('rule')
        option = request.args.get('options')
        repeat_check = review_df.loc[(review_df['股票名稱'] == option) & (review_df['使用規則'] == rule)]
        if not repeat_check.empty:
            flash('不可重複添加報表')
            return redirect(request.referrer)

    else:
        review = review_df[review_df['review_id'] == review_id].iloc[0]
        rule = str(review['使用規則'])
        option = str(review['股票名稱'])

    cards = card_df.loc[card_df['卡組名稱'] == rule]
    data = cards['使用卡牌'].values[0].split('-')
    term = data[0]
    # print("---------------編輯頁面---------------")
    # print("trade_data \n ", trade_df)
    # print("---------------編輯頁面---------------")

    df = trade_df.loc[(trade_df['股票名稱'] == option) & (trade_df['使用規則'] == rule) & (trade_df['user_id'] == user_id)]
    df['日期'] = df['日期'].apply(lambda x: datetime.strptime(x, '%Y/%m/%d'))

    # twstock 只取數字
    stock_symbol = df['股票代號'].iloc[0][:4]

    start_date = df['日期'].min() - relativedelta(months=3)
    end_date = df['日期'].max() + relativedelta(days=2)

    stock = twstock.Stock(stock_symbol) # 台積電的股票代碼為 2330
    data = stock.fetch_from(start_date.year, start_date.month) # 從 start_date 開始查詢

    # 篩選出 start_date 至 end_date 之間的資料
    data = [d for d in data if start_date <= d.date <= end_date]
    stock_data = pd.DataFrame(data, columns=['Date', 'Volume', 'turnover' , 'Open', 'High', 'Low', 'Close', 'change', 'transaction'])
    
    # 去掉無用欄位並且轉換 datetime => string
    stock_data.drop(['turnover', 'transaction', 'change'], axis=1, inplace=True)
    stock_data = stock_data.rename(columns={'Date': '日期'})

    stock_copy = stock_data.copy()
    stock_copy['日期'] = pd.to_datetime(stock_copy['日期'])
    stock_copy['日期'] = stock_copy['日期'].dt.strftime('%Y/%m/%d')

    stock_data['日期'] = stock_data['日期'].dt.strftime('%Y-%m-%d')


    # ======================================== #
    card_list = cards['使用卡牌'].tolist()[0].split('-')

    custom_list = []
    custom_index = card_list.index("custom")
    # print(custom.split('-').index('custom')+1)





    custom_list = card_list[custom_index+1:]
    default_list = card_list[:custom_index]
    if term == 'short':
        args_day = 5
    elif term == 'medium':
        args_day = 20
    else:
        args_day = 50

    # 趨勢指標
    if 'sma' in default_list:
        stock_copy['sma'] = ta.sma(stock_copy['Close'], length=args_day)

    if 'ema' in default_list:
        stock_copy['ema'] = ta.ema(stock_copy['Close'], length=args_day)

    if 'wma' in default_list:
        stock_copy['wma'] = ta.wma(stock_copy['Close'], length=args_day)

    if 'hma' in default_list:
        stock_copy['hma'] = ta.hma(stock_copy['Close'], length=args_day)

    # 震盪指標
    if 'rsi' in default_list:
        stock_copy['rsi'] = ta.rsi(stock_copy['Close'], length=args_day)

    if 'stoch' in default_list:
        stock_copy[['slowk', 'slowd']] = ta.stoch(stock_copy['High'], stock_copy['Low'], stock_copy['Close'], fastk_period=args_day, slowk_period=3, slowd_period=3)
    
    if 'cci' in default_list:
        stock_copy['cci'] = ta.cci(stock_copy['High'], stock_copy['Low'], stock_copy['Close'], length=args_day)

    # 通道指標
    if 'bbl' in default_list:
        stock_copy[['bbm', 'bbh', 'bbl', 'bbb', 'bbp']] = ta.bbands(stock_copy['Close'], length=args_day)
    
    if 'kc' in default_list:
        stock_copy[['kc', 'kcb', 'kct']] = ta.kc(stock_copy['High'], stock_copy['Low'], stock_copy['Close'], length=args_day)


    # 能量指標
    if 'cmf' in default_list:
        stock_copy['cmf'] = ta.cmf(stock_copy['High'], stock_copy['Low'], stock_copy['Close'], stock_copy['Volume'], length=args_day)
    
    if 'mfi' in default_list:
        stock_copy['mfi'] = ta.mfi(stock_copy['High'], stock_copy['Low'], stock_copy['Close'], stock_copy['Volume'], length=args_day)
    

    stock_data = stock_data[['日期', 'Open','High','Low','Close','Volume']]

    stock_data = stock_data.rename(columns={'日期': 'date'})
    stock_data = stock_data.rename(columns={'Open': 'open'})
    stock_data = stock_data.rename(columns={'High': 'high'})
    stock_data = stock_data.rename(columns={'Low': 'low'})
    stock_data = stock_data.rename(columns={'Close': 'close'})


    stock_data['MA5'] = stock_data['close'].rolling(window=5).mean()
    stock_data['MA20'] = stock_data['close'].rolling(window=20).mean()
    stock_data['MA50'] = stock_data['close'].rolling(window=50).mean()
    stock_data['MA60'] = stock_data['close'].rolling(window=60).mean()
    dt_all = pd.date_range(start=stock_data['date'].iloc[0],end=stock_data['date'].iloc[-1])
    dt_obs = [d.strftime("%Y-%m-%d") for d in pd.to_datetime(stock_data['date'])]
    dt_break = [d for d in dt_all.strftime("%Y-%m-%d").tolist() if not d in dt_obs]
    stock_data['MFI'] = ta.mfi(stock_data['high'], stock_data['low'], stock_data['close'], stock_data['Volume'], length=5)
    # stock_data['CCI'] = ta.mfi(stock_data['high'], stock_data['low'], stock_data['close'], stock_data['Volume'], length=20)
    # stock_copy['RSI'] = ta.rsi(stock_copy['Close'], length=20)

    data = stock_data.to_json(orient='records')


    # stock_data 的日期為 object 型態(為了讓 plotly.js 顯示)
    df['日期'] = df['日期'].apply(lambda x: x.strftime('%Y/%m/%d'))
    df = pd.merge(df, stock_copy, how='left', on='日期')

    buy_df = df.loc[df['買/賣'] == '買']

    # 趨勢指標

    if 'sma' in default_list:
        buy_df['sma_buy'] = buy_df['Close'] > buy_df['sma']

    if 'ema' in default_list:
        buy_df['ema_buy'] = buy_df['Close'] > buy_df['ema']

    if 'wma' in default_list:
        buy_df['wma_buy'] = buy_df['Close'] > buy_df['wma']

    if 'hma' in default_list:
        buy_df['hma_buy'] = buy_df['Close'] > buy_df['hma']

    # 震盪指標
    if 'rsi' in default_list:
        buy_df['rsi_buy'] = buy_df['rsi'] > 20

    if 'stoch' in default_list:
        buy_df['stoch_buy'] = (buy_df['slowd'] > 20) & (buy_df['slowd'].shift(1) > 20)

    if 'cci' in default_list:
        buy_df['cci_buy'] = buy_df['cci'] > -100


    # 通道指標

    if 'bbl' in default_list:
        buy_df['bbl_buy'] = buy_df['Close'] > buy_df['bbl']

    if 'kc' in default_list:
        buy_df['kc_buy'] = buy_df['Close'] > buy_df['kc']

    # 能量指標

    if 'cmf' in default_list:
        buy_df['cmf_buy'] = buy_df['cmf'] > 0

    if 'mfi' in default_list:
        buy_df['mfi_buy'] = buy_df['mfi'] > 20

    sell_df = df.loc[df['買/賣'] == '賣']

    # 趨勢指標
    if 'sma' in default_list:
        sell_df['sma_sell'] = sell_df['Close'] < sell_df['sma']

    if 'ema' in default_list:
        sell_df['ema_sell'] = sell_df['Close'] < sell_df['ema']

    if 'wma' in default_list:
        sell_df['wma_sell'] = sell_df['Close'] < sell_df['wma']

    if 'hma' in default_list:
        sell_df['hma_sell'] = sell_df['Close'] < sell_df['hma']

    # 震盪指標
    if 'rsi' in default_list:
        sell_df['rsi_sell'] = sell_df['rsi'] < 50

    if 'stoch' in default_list:
        sell_df['stoch_sell'] = (sell_df['slowd'] < 80) & (sell_df['slowd'].shift(1) < 80)

    if 'cci' in default_list:
        sell_df['cci_sell'] = sell_df['cci'] < 0

    # 通道指標

    if 'bbl' in default_list:
        sell_df['bbl_sell'] = sell_df['Close'] < sell_df['bbl']

    if 'kc' in default_list:
        sell_df['kc_sell'] = sell_df['Close'] < sell_df['kc']

    # 能量指標
    if 'cmf' in default_list:
        sell_df['cmf_sell'] = sell_df['cmf'] < 0

    if 'mfi' in default_list:
        sell_df['mfi_sell'] = sell_df['mfi'] < 50

    # ======================================== #

    trade_data = trade_df.loc[(trade_df['股票名稱'] == option) & (trade_df['使用規則'] == rule)]

    trade_data.loc[:, '日期'] = trade_data['日期'].str.replace("/", "-")

    trade_data = trade_data.rename(columns={'日期': 'date', '價格':'price', '數量':'volume'})
    trade_data['type'] = trade_data['買/賣'].replace({'買': 'buy', '賣': 'sell'})
    basic_info = get_stock_basic_info(option, rule)

    trade_data = trade_data.to_json(orient='records')
    buy_df['遵守'] = df['遵守'].astype('object')
    buy_df['違反'] = df['違反'].astype('object')
    sell_df['遵守'] = df['遵守'].astype('object')
    sell_df['違反'] = df['違反'].astype('object')
    buy_dict = {}
    for item in custom_list:
        if '(賣)' not in item:
            try:
                buy_dict.update(calculate_probability(buy_df, "遵守", "違反", item))
            except AttributeError:
                print("目前沒有資料")
    buy_ratio = {col: buy_df[col].mean() for col in buy_df.columns if col.endswith('_buy')}
    buy_ratio.update(buy_dict)


    sell_dict = {}
    for item in custom_list:
        if '(買)' not in item:
            try:
                sell_dict.update(calculate_probability(sell_df, "遵守", "違反", item))
            except AttributeError:
                print("目前沒有資料")
    sell_ratio = {col: sell_df[col].mean() for col in sell_df.columns if col.endswith('_sell')}
    sell_ratio.update(sell_dict)

    fig = go.Figure([go.Bar(x=list(buy_ratio.keys()), y=list(buy_ratio.values()))])
    fig.update_layout(xaxis_title='Indicator Name',
        yaxis_title='True Probability',
        autosize=False,
        width=500,
        height=280,
        margin=dict(l=50, r=50, t=0, b=10),
    )

    fig2 = go.Figure([go.Bar(x=list(sell_ratio.keys()), y=list(sell_ratio.values()))])
    fig2.update_layout(xaxis_title='Indicator Name',
        yaxis_title='True Probability',
        autosize=False,
        width=500,
        height=280,
        margin=dict(l=50, r=50, t=0, b=10),
    )

    global chart_data, trade_point
    chart_data = data
    trade_point = trade_data
    print(f'--------------載入頁面-------------')
    print(f'買點執行率{buy_ratio}')
    print(f'買點執行率{sell_ratio}')
    # print(f'所有交易點(顯示在圖表上的){trade_data}')
    print(f'買點資料: ', buy_df['Close'])

    print(f'--------------載入頁面-------------')

    if review_id == 9999:
        return render_template('review_form.html', fig2=fig2.to_html(), fig=fig.to_html(), custom_list=custom_list, basic_info=basic_info, option=option, rule=rule, buy_df=buy_df, sell_df=sell_df, data=data, trade_data=trade_data, dt_break=dt_break)

    else:
        review = review_df[review_df['review_id'] == review_id]
        review = review.to_dict('records')
        return render_template('review_form.html', fig2=fig2.to_html(), fig=fig.to_html(), review=review, custom_list=custom_list, basic_info=basic_info, option=option, rule=rule, buy_df=buy_df, sell_df=sell_df, data=data, trade_data=trade_data, dt_break=dt_break)

@app.route('/view_chart', methods=['GET'])
def view_chart():
    global chart_data, trade_point
    data = chart_data
    trade_data = trade_point
    return render_template('view_chart.html',  data=data, trade_data=trade_data)


def get_stock_basic_info(stock_name, rule):
    global trade_df

    trades = trade_df.loc[(trade_df['使用規則'] == rule) & (trade_df['股票名稱'] == stock_name)]
    data = {}
    data['股票名稱'] = stock_name
    data['股票代號'] = trades['股票代號'].iloc[0]
    total_profit = 0
    for _, row in trades.iterrows():
        if row['買/賣'] == '買':
            total_profit -= row['價格'] * row['數量']
        else:
            total_profit += row['價格'] * row['數量']
    return_rate = total_profit / (trades[trades['買/賣'] == '買']['價格'] * trades[trades['買/賣'] == '買']['數量']).sum()
    data['獲利'] = total_profit
    data['報酬率'] = return_rate
    data['交易筆數'] = trades.shape[0]
    data['交易期間'] =  f"{trades['日期'].min()} - {trades['日期'].max()}"
    data['使用策略'] = trades['使用規則'].iloc[0]
    return data

def calculate_probability(df, follow, violate, keyword):
    count1 = df[follow].str.contains(keyword, regex=False).sum()
    count2 = df[violate].str.contains(keyword, regex=False).sum()
    print(keyword, "的違反為", count2)
    print(keyword, "的遵守為", count1)
    if (count1 + count2) == 0:
        probability = 0
    else:
        probability = count1 / (count1 + count2)
    result = {keyword: probability}
    return result


def one_point_indicator_detail(user_id, stock_name, date, price, action, rule):
    global buy_df, sell_df, trade_df, card_df
    # print(f'--------------讀取目前頁面資料-------------')
    # print(f'買點資料: {buy_df}')
    # print(f'賣點資料: {sell_df}')
    # print(f'--------------讀取目前頁面資料-------------')
    buys = buy_df
    sells = sell_df

    point_data = {}
    violate = []
    follow = []
    stay = []
    user_id = int(current_user.get_id())
    cards = card_df.loc[card_df['卡組名稱'] == rule]

    card_list = cards['使用卡牌'].tolist()[0].split('-')
    custom_list = []
    custom_index = card_list.index("custom")
    custom_list = card_list[custom_index+1:]
    # print(f'--------------按下點位-------------')
    # print(f'sells: ', sells)
    # print(f'buys: ', buys)
    # print(f'--------------按下點位-------------')

    buys['日期'] = buys['日期'].str.replace("/0", "/")
    sells['日期'] = sells['日期'].str.replace("/0", "/")

    if action == '買':
        # print(f'--------------校驗檢索-------------')
        # print('type:', buys['user_id'].dtype, ' value:', buys['user_id'].iloc[0])
        # print('type:', buys['股票名稱'].dtype, ' value:', buys['股票名稱'].iloc[0])
        # print('type:', buys['日期'].dtype, ' value:', buys['日期'].iloc[0])
        # print('type:', buys['價格'].dtype, ' value:', buys['價格'].iloc[0])
        # print('type:', buys['買/賣'].dtype, ' value:', buys['買/賣'].iloc[0])
        # print(f'--------------校驗檢索-------------')
        # print('type:', type(user_id), ' value:', user_id)
        # print('type:', type(stock_name), ' value:', stock_name)
        # print('type:', type(date), ' value:', date)
        # print('type:', type(price), ' value:', price)
        # print('type:', type(action), ' value:', action)
        # print(f'--------------校驗檢索-------------')
        buys = buys[(buys['user_id'] == user_id) & (buys['股票名稱'] == stock_name) & (buys['日期'] == date) & (buys['價格'] == price) & (buys['買/賣'] == action)]

        if 'sma' in buys.columns:
            if buys['sma_buy'].tolist()[0] == True:
                follow.append("穿越 sma 後交易")
            else:
                violate.append("穿越 sma 後交易")

        if 'ema' in buys.columns:
            if buys['ema_buy'].tolist()[0] == True:
                follow.append("穿越 ema 後交易")
            else:
                violate.append("穿越 ema 後交易")

        if 'wma' in buys.columns:
            if buys['wma_buy'].tolist()[0] == True:
                follow.append("穿越 wma 後交易")
            else:
                violate.append("穿越 wma 後交易")

        if 'hma' in buys.columns:
            if buys['hma_buy'].tolist()[0] == True:
                follow.append("穿越 hma 後交易")
            else:
                violate.append("穿越 hma 後交易")

        if 'rsi' in buys.columns:
            if buys['rsi_buy'].tolist()[0] == True:
                follow.append("依 rsi 強弱交易")
            else:
                violate.append("依 rsi 強弱交易")

        if 'stoch' in buys.columns:
            if buys['stoch_buy'].tolist()[0] == True:
                follow.append("依 stoch 強弱交易")
            else:
                violate.append("依 stoch 強弱交易")

        if 'cci' in buys.columns:
            if buys['cci_buy'].tolist()[0] == True:
                follow.append("依 cci 強弱交易")
            else:
                violate.append("依 cci 強弱交易")

        if 'bbl' in buys.columns:
            if buys['bbl_buy'].tolist()[0] == True:
                follow.append("穿越 bbl 後交易")
            else:
                violate.append("穿越 bbl 後交易")

        if 'kc' in buys.columns:
            if buys['kc_buy'].tolist()[0] == True:
                follow.append("穿越 kc 後交易")
            else:
                violate.append("穿越 kc 後交易")


        if 'cmf' in buys.columns:
            if buys['cmf_buy'].tolist()[0] == True:
                follow.append("依 cmf 強弱交易")
            else:
                violate.append("依 cmf 強弱交易")

        if 'mfi' in buys.columns:
            if buys['mfi_buy'].tolist()[0] == True:
                follow.append("依 mfi 強弱交易")
            else:
                violate.append("依 mfi 強弱交易")

        if buys['遵守'].tolist():
            point_data['遵守'] = str(buys['遵守'].tolist()[0]).split('-')
        if buys['違反'].tolist():
            point_data['違反'] = str(buys['違反'].tolist()[0]).split('-')

    else:
        sells = sells[(sells['user_id'] == user_id) & (sells['股票名稱'] == stock_name) & (sells['日期'] == date) & (sells['價格'] == price) & (sells['買/賣'] == action)]

        if 'sma' in sells.columns:
            if sells['sma_sell'].tolist()[0] == True:
                follow.append("穿越 sma 後交易")
            else:
                violate.append("穿越 sma 後交易")

        if 'ema' in sells.columns:
            if sells['ema_sell'].tolist()[0] == True:
                follow.append("穿越 ema 後交易")
            else:
                violate.append("穿越 ema 後交易")

        if 'wma' in sells.columns:
            if sells['wma_sell'].tolist()[0] == True:
                follow.append("穿越 wma 後交易")
            else:
                violate.append("穿越 wma 後交易")

        if 'hma' in sells.columns:
            if sells['hma_sell'].tolist()[0] == True:
                follow.append("穿越 hma 後交易")
            else:
                violate.append("穿越 hma 後交易")

        if 'rsi' in sells.columns:
            if sells['rsi_sell'].tolist()[0] == True:
                follow.append("依 rsi 強弱交易")
            else:
                violate.append("依 rsi 強弱交易")

        if 'stoch' in sells.columns:
            if sells['stoch_sell'].tolist()[0] == True:
                follow.append("依 stoch 強弱交易")
            else:
                violate.append("依 stoch 強弱交易")

        if 'cci' in sells.columns:
            if sells['cci_sell'].tolist()[0] == True:
                follow.append("依 cci 強弱交易")
            else:
                violate.append("依 cci 強弱交易")

        if 'bbl' in sells.columns:
            if sells['bbl_sell'].tolist()[0] == True:
                follow.append("穿越 bbl 後交易")
            else:
                violate.append("穿越 bbl 後交易")

        if 'kc' in sells.columns:
            if sells['kc_sell'].tolist()[0] == True:
                follow.append("穿越 kc 後交易")
            else:
                violate.append("穿越 kc 後交易")


        if 'cmf' in sells.columns:
            if sells['cmf_sell'].tolist()[0] == True:
                follow.append("依 cmf 強弱交易")
            else:
                violate.append("依 cmf 強弱交易")

        if 'mfi' in sells.columns:
            if sells['mfi_sell'].tolist()[0] == True:
                follow.append("依 mfi 強弱交易")
            else:
                violate.append("依 mfi 強弱交易")

        if sells['遵守'].tolist():
            point_data['遵守'] = str(sells['遵守'].tolist()[0]).split('-')
        if sells['違反'].tolist():
            point_data['違反'] = str(sells['違反'].tolist()[0]).split('-')



    stay = [x for x in custom_list if x not in point_data['遵守'] and x not in point_data['違反']]
    point_data['待決定'] = stay
    point_data['系統遵守'] = follow
    point_data['系統違反'] = violate

    point_data = remove_nan(point_data)

    print(f'--------------按下點位-------------')
    print(f'目前策略的所有卡牌: {card_list}')
    print(f'目前策略的客製卡牌: {custom_list}')
    # print(f'輸出: ',buys['sma'], buys['Close'].tolist())
    # print(f'輸出: ',sells['sma'], sells['Close'].tolist())
    print(f'--------------按下點位-------------')

    return point_data


def remove_nan(d):
    if isinstance(d, dict):
        return {k: remove_nan(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [remove_nan(v) for v in d if not (isinstance(v, float) and math.isnan(v))]
    else:
        return d

@app.route('/update_review', methods=['POST'])
def update_review():
    global review_df
    status = request.form.get("status", ' ')
    conclusion = request.form.get('myTextarea')
    duration = request.form.get('duration')
    stock_name = request.form.get('stock_name')
    profit = request.form.get('profit')
    ratio = request.form.get('ratio')
    number = request.form.get('number')
    rule = request.form.get('rule')

    user_id = int(current_user.get_id())
    current_dir = os.getcwd()
    filename = 'reviews.csv'
    if not os.path.exists(os.path.join(current_dir, filename)):
        df = pd.DataFrame(columns=["review_id", "user_id", "交易期間",  "股票名稱", "獲利", "報酬率", "交易筆數", "狀態", "結論", "使用規則"])

        df.to_csv("reviews.csv", index=False, encoding='utf-8-sig')
    review_id = pd.read_csv('reviews.csv', encoding='utf-8-sig').shape[0]

    df = pd.DataFrame([[review_id, user_id, duration, stock_name, profit, ratio, number, status, conclusion, rule]], \
        columns=["review_id", "user_id", "交易期間",  "股票名稱", "獲利", "報酬率", "交易筆數", "狀態", "結論", "使用規則"])

    df.to_csv("reviews.csv", index=False, encoding='utf-8-sig', mode="a", header=False)
    review_df = pd.read_csv('reviews.csv', encoding='utf-8-sig')

    print(f'--------------送出表單-------------')
    print(f'目前資料: {df}')
    print(f'--------------送出表單-------------')
    return redirect(url_for('index'))

@app.route('/edit_review/<int:review_id>', methods=['GET', 'POST'])
def edit_review(review_id):
    global review_df
    status = request.form.get("status", ' ')
    conclusion = request.form.get('myTextarea')
    user_id = current_user.get_id()

    mask = review_df['review_id'] == review_id

    data = {
        '狀態': status,
        '結論': conclusion,
    }

    review_df.loc[mask, data.keys()] = data.values()

    review_df.to_csv('reviews.csv', mode='w', encoding='utf-8-sig', index=False)

    return redirect(request.referrer)

@app.route('/delete_review/<int:review_id>', methods=['GET', 'POST'])
def delete_review(review_id):
    global review_df
    review_df = review_df[~(review_df['review_id'] == review_id)]
    review_df.to_csv('reviews.csv', mode='w', encoding='utf-8-sig', index=False)
    return redirect(request.referrer)

@app.route('/update_custom', methods=['POST'])
def update_custom():
    global trade_df
    user_id = int(current_user.get_id())
    date = request.form['date'].replace('-', '/').replace('/0', '/')
    price = request.form['price']
    action = request.form['action']
    data = request.form.to_dict()
    action = str(action)[0]

    # print(f'--------------更新指標-------------')
    # print('收到資料: ', data)
    # print(f'--------------更新指標-------------')


    mask = (trade_df['user_id'] == user_id) & (trade_df['日期'] == date) & (trade_df['價格'] == float(price)) & (trade_df['買/賣'] == action[0])
    


    follow_form = [k for k, v in data.items() if v == '遵守']
    violate_form = [k for k, v in data.items() if v == '違反']

    follow = '-'.join(follow_form)
    violate = '-'.join(violate_form)
    # stay = '-'.join([k for k, v in data.items() if v == '待決定'])


    data = {
        "遵守" : follow ,
        "違反" : violate ,
        # "待決定" : stay
    }
    
    trade_df.loc[mask, data.keys()] = data.values()
    trade_df.to_csv('trades.csv', mode='w', encoding='utf-8-sig', index=False)

    print(f'--------------更新指標-------------')
    print(f'日期為 {date}')
    print(f'trade_df: \n {trade_df}')
    print(f'遵守項目有: {follow}')
    print(f'違反項目有: {violate}')
    print('修改資料: ', trade_df.loc[mask])
    print(f'--------------更新指標-------------')

    return redirect(request.referrer)

if __name__ == '__main__':
    app.run(debug=True)


