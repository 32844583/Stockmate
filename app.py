from datetime import datetime, timedelta
from datetime import date
import feedparser
import pandas as pd
import yfinance as yf
import twstock
import re
import time
import requests
from bs4 import BeautifulSoup
from pprint import pprint
from flask import Flask, render_template, jsonify, request, redirect, url_for
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


# Sample route to display stock data and candlestick chart
@app.route('/', methods=['POST', 'GET'])
@login_required
def index():
    user_id = int(current_user.get_id())

    symbol = '2330.TW'
    if request.method == 'POST':
        symbol = request.form.get("symbol")
    print(symbol)        

    stock = yf.Ticker(symbol)
    data = stock.history(period='6mo')
    data = data[['Open','High','Low','Close','Volume']]
    data.reset_index(level='Date', inplace=True)

    # https://stackoverflow.com/questions/61346100/plotly-how-to-style-a-plotly-figure-so-that-it-doesnt-display-gaps-for-missing
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
        df = pd.DataFrame(columns=["trade_id", "user_id", "日期", "股票代號", "股票名稱", "價格", "數量", "買/賣", "原因", "使用規則"])

        df.to_csv("trades.csv", index=False, encoding='utf-8-sig')

    df = pd.read_csv('trades.csv', encoding='utf-8-sig')
    print(df)
    trade_df = df[(df['user_id'] == user_id) & (df['股票名稱'] == stock_name)]
    trade_df['日期'] = trade_df['日期'].str.replace("-", "/")

    trade_df['日期'] = pd.to_datetime(trade_df['日期'])

    fig.add_trace(go.Scatter(x=trade_df.loc[trade_df['買/賣'] == '買', '日期'],
    y=trade_df.loc[trade_df['買/賣'] == '買', '價格'],
    mode='markers',
    marker=dict(symbol='triangle-up', color='green', size=10),
    text=trade_df.loc[trade_df['買/賣'] == '買', '買/賣'],
    customdata=trade_df.loc[trade_df['買/賣'] == '買', ['數量', '原因']],
    hovertemplate='<b>日期</b>: %{x}<br><b>價格</b>: %{y}<br><b>數量</b>: %{customdata[0]}<br><b>買賣</b>: %{text}<br><b>原因</b>: %{customdata[1]}<extra></extra>'),
    row=1, col=1)

    fig.add_trace(go.Scatter(x=trade_df.loc[trade_df['買/賣'] == '賣', '日期'],
    y=trade_df.loc[trade_df['買/賣'] == '賣', '價格'],
    mode='markers',
    marker=dict(symbol='triangle-down', color='red', size=10),
    text=trade_df.loc[trade_df['買/賣'] == '賣', '買/賣'],
    customdata=trade_df.loc[trade_df['買/賣'] == '賣', ['數量', '原因']],
    hovertemplate='<b>日期</b>: %{x}<br><b>價格</b>: %{y}<br><b>數量</b>: %{customdata[0]}<br><b>買賣</b>: %{text}<br><b>原因</b>: %{customdata[1]}<extra></extra>'),
    row=1, col=1)

    print(df)
    trade_df = df[(df['user_id'] == user_id) & (df['股票名稱'] == stock_name)]
    trades=trade_df.to_dict(orient='records')
    print(trades)

    card_df = pd.read_csv('cards.csv', encoding='utf-8-sig')
    card_df = card_df[(card_df['user_id'] == user_id)]
    cards=card_df.to_dict(orient='records')

    return render_template('index.html', plot=fig.to_html(), cards=cards, trades=trades, stock_name=stock_name, stock_code=symbol)


@app.route('/update', methods=['POST', 'GET'])
def update():
    df = pd.read_csv('cards.csv', encoding='utf-8-sig')

    user_id = int(current_user.get_id())

    value = request.args.get('value')
    print('value', value)
    cards = df.loc[(df['卡組名稱'] == value) & (df['user_id'] == user_id)]
    card_item = cards['使用卡牌'].values[0].split('-')

    card_df = df[(df['user_id'] == user_id)]

    cards=card_df.to_dict(orient='records')
    print(card_item)
    return render_template('cards.html', card_item=card_item, cards=cards)



@app.route('/cards', methods=['POST', 'GET'])
@login_required
def cards():
    current_dir = os.getcwd()
    filename = 'cards.csv'
    card_item = ['test']
    df = pd.read_csv('cards.csv', encoding='utf-8-sig')
    test = ""
    user_id = int(current_user.get_id())
    cards = df.loc[(df['user_id'] == user_id)]
    customs = cards['使用卡牌'].tolist()
    print(customs)

    # get all user's cards
    custom_list = []
    for custom in customs:
        temp = custom.split('-')
        index = temp.index('custom')+1
        # print(custom.split('-').index('custom')+1)
        print(temp[index:])
        for item in temp[index:]:
            if item not in custom_list:
                custom_list.append(item)

    if not os.path.exists(os.path.join(current_dir, filename)):
        df = pd.DataFrame(columns=["card_id", "user_id", "卡組名稱", "使用卡牌"])
        df.to_csv("cards.csv", index=False, encoding='utf-8-sig')

    if request.method == 'POST':
        customs = request.form.getlist('item')
        print(customs)
        term = request.form.get("term", ' ')
        trend = request.form.get("trend", ' ')
        oscillators = request.form.get("oscillators", ' ')
        volatility = request.form.get("volatility", ' ')
        energy = request.form.get("energy", ' ')
        rule_name = request.form.get("rule_name", ' ')

        # if trend == None:
        #     trend = ' '
        # if oscillators == None:
        #     oscillators = ' '
        # if volatility == None:
        #     volatility = ' '
        # if energy == None:
        #     energy = ' '

        select_item = '-'.join([term, trend, oscillators, volatility, energy]) + '-custom-' + '-'.join(customs)
        # print(select_item.split('-'))
        # print(select_item)

        mask = cards['卡組名稱'] == rule_name

        data = {
            '卡組名稱': rule_name,
            '使用卡牌': select_item,
        }
        cards.loc[mask, data.keys()] = data.values()

        cards.to_csv('cards.csv', mode='w', encoding='utf-8-sig', index=False)

        # card_list = request.form.getlist('card_name') # 獲取勾選框的 value 列表
        # card_string = '-'.join(card_list) # 將列表中的元素用 '-' 串成一個字串
        # card_id = pd.read_csv('cards.csv', encoding='utf-8-sig').shape[0]
        # df = pd.DataFrame([[ card_id, user_id, rule, card_string]], \
        #     columns=["card_id", "user_id",  "卡組名稱", "使用卡牌"])
        # df = pd.read_csv('cards.csv', encoding='utf-8-sig')
        return redirect(url_for('cards'))

    cards =cards.to_dict(orient='records')
    print(custom_list)
    return render_template('cards.html', cards=cards, card_item=card_item, test=test, custom_list=custom_list)

@app.route('/delete_card/<int:card_id>', methods=['GET', 'POST'])
@login_required
def delete_card(card_id):
    df = pd.read_csv('cards.csv', encoding='utf-8-sig')
    df = df[~(df['card_id'] == card_id)]
    df.to_csv('cards.csv', mode='w', encoding='utf-8-sig', index=False)
    return redirect(url_for('cards'))

@app.route('/edit_card/<int:card_id>', methods=['GET', 'POST'])
@login_required
def edit_card(card_id):
    if request.method == 'GET':
        df = pd.read_csv('cards.csv')
        card = df[df['card_id'] == card_id]
        cards = card.to_dict('records')
        return render_template('edit_card.html', cards=cards)
    else:
        df = pd.read_csv('cards.csv', encoding='utf-8-sig')

        rule = request.form.get("rule")
        card_list = request.form.getlist('card_name') # 獲取勾選框的 value 列表
        card_string = '-'.join(card_list) # 將列表中的元素用 '-' 串成一個字串

        mask = df['card_id'] == card_id

        data = {
            '卡組名稱': rule,
            '使用卡牌': card_string,
        }

        df.loc[mask, data.keys()] = data.values()
        print(data)
        df.to_csv('cards.csv', mode='w', encoding='utf-8-sig', index=False)

        return redirect(url_for('cards'))

@app.route('/add_trade', methods=['GET', 'POST'])
@login_required
def add_trade():
    print('test')
    user_id = int(current_user.get_id())
    date = request.form.get("date")
    print('type(date)', type(date))
    stock_symbol = request.form.get("stock_symbol")
    stock_name = request.form.get("stock_name")
    price = request.form.get("price")
    quantity = request.form.get("quantity")
    action = request.form.get("action")
    reason = request.form.get("reason")
    rule = request.form.get("rule")
    trade_id = pd.read_csv('trades.csv', encoding='utf-8-sig').shape[0]
    print(trade_id)
    df = pd.DataFrame([[trade_id, user_id, date, stock_symbol, stock_name, price, quantity, action, reason, rule]], \
        columns=["trade_id", "user_id", "日期", "股票代號", "股票名稱", "價格", "數量", "買/賣", "原因", "使用規則"])
    print(df)
    df.to_csv("trades.csv", index=False, encoding='utf-8-sig', mode="a", header=False)
    return redirect(url_for('index'))


# 定義一個路由和函數來處理刪除交易的請求
@app.route('/delete_trade/<int:trade_id>', methods=['GET', 'POST'])
def delete_trade(trade_id):
    df = pd.read_csv('trades.csv', encoding='utf-8-sig')
    df = df[~(df['trade_id'] == trade_id)]
    df.to_csv('trades.csv', mode='w', encoding='utf-8-sig')
    return redirect(url_for('index'))

# 定義一個路由和函數來處理編輯交易的請求
@app.route('/edit_trade/<int:trade_id>', methods=['GET', 'POST'])
def edit_trade(trade_id):
    user_id = current_user.get_id()
    if request.method == 'GET':
        df = pd.read_csv('trades.csv')
        trade = df[df['trade_id'] == trade_id]
        print(trade)
        trades = trade.to_dict('records')
        print(trade)
        return render_template('edit_trade.html', trades=trades)
    else:
        df = pd.read_csv('trades.csv', encoding='utf-8-sig')
        date = request.form.get('date')
        stock_symbol = request.form.get('stock_symbol')
        stock_name = request.form.get("stock_name")
        price = request.form.get('price')
        quantity = request.form.get('quantity')
        action = request.form.get('action')
        reason = request.form.get('reason')
        rule = request.form.get('rule')

        mask = df['trade_id'] == trade_id

        data = {
            '日期': date,
            '股票代號': stock_symbol,
            '股票名稱': stock_name,
            '價格': price,
            '數量': quantity,
            '買/賣': action,
            '原因': reason,
            '使用規則': rule
        }

        df.loc[mask, data.keys()] = data.values()

        df.to_csv('trades.csv', mode='w', encoding='utf-8-sig', index=False)

        return redirect(url_for('index'))

buy_df = pd.DataFrame()
sell_df = pd.DataFrame()


@app.route('/review', methods=['GET', 'POST'])
@login_required
def review():
    global buy_df, sell_df

    user_id = int(current_user.get_id())
    df = pd.read_csv('trades.csv', encoding='utf-8-sig')
    trades = df.loc[(df['user_id'] == user_id)]
    trade_data = pd.DataFrame()
    stock_data = pd.DataFrame()
    point = pd.DataFrame()

    if request.method == 'GET' and request.args.get('rule') and request.args.get('options'):

        rule = request.args.get('rule')
        options = request.args.get('options')
        card_df = pd.read_csv('cards.csv', encoding='utf-8-sig')
        cards = card_df.loc[card_df['卡組名稱'] == rule]
        data = cards['使用卡牌'].values[0].split('-')
        term = data[0]

        df = trades.loc[(trades['股票名稱'] == options) & (trades['使用規則'] == rule) & (trades['user_id'] == user_id)]
        
        stock_symbol = df['股票代號'].iloc[0]
        start_date = pd.to_datetime(df['日期'].min()) - relativedelta(months=2)
        start_date_str = start_date.strftime('%Y-%m-%d')

        end_date = pd.to_datetime(df['日期'].max()) + relativedelta(days=2)
        end_date_str = end_date.strftime('%Y-%m-%d')

        ticker = yf.Ticker(stock_symbol)
        stock_data = ticker.history(stock_symbol, start=start_date_str, end=end_date_str)
        stock_data.reset_index(inplace=True)
        stock_data = stock_data.rename(columns={'Date': '日期'})
        stock_data['日期'] = stock_data['日期'].dt.strftime('%Y-%m-%d')

        # ======================================== #
        card_list = cards['使用卡牌'].tolist()[0].split('-')

        custom_list = []
        custom_index = card_list.index("custom")
        # print(custom.split('-').index('custom')+1)
        custom_list = card_list[custom_index+1:]
        default_list = card_list[:custom_index]

        # 趨勢指標
        if 'sma' in default_list:
            stock_data['sma'] = ta.sma(stock_data['Close'], length=20)

        if 'ema' in default_list:
            stock_data['ema'] = ta.ema(stock_data['Close'], length=20)

        if 'wma' in default_list:
            stock_data['wma'] = ta.wma(stock_data['Close'], length=20)

        if 'hma' in default_list:
            stock_data['hma'] = ta.hma(stock_data['Close'], length=20)

        # 震盪指標
        if 'rsi' in default_list:
            stock_data['rsi'] = ta.rsi(stock_data['Close'], length=14)

        if 'stoch' in default_list:
            stock_data[['slowk', 'slowd']] = ta.stoch(stock_data['High'], stock_data['Low'], stock_data['Close'], fastk_period=14, slowk_period=3, slowd_period=3)
        
        if 'cci' in default_list:
            stock_data['cci'] = ta.cci(stock_data['High'], stock_data['Low'], stock_data['Close'], length=20)

        # 通道指標
        if 'bbl' in default_list:
            stock_data[['bbm', 'bbh', 'bbl', 'bbb', 'bbp']] = ta.bbands(stock_data['Close'], length=20)
        
        if 'kc' in default_list:
            stock_data[['kc', 'kcb', 'kct']] = ta.kc(stock_data['High'], stock_data['Low'], stock_data['Close'], length=20)


        # 能量指標
        if 'cmf' in default_list:
            stock_data['cmf'] = ta.cmf(stock_data['High'], stock_data['Low'], stock_data['Close'], stock_data['Volume'], length=20)
        
        if 'mfi' in default_list:
            stock_data['mfi'] = ta.mfi(stock_data['High'], stock_data['Low'], stock_data['Close'], stock_data['Volume'], length=14)


        df = pd.merge(df, stock_data, how='left', on='日期')
        df = df.drop(['Dividends', 'Stock Splits'], axis=1)
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
            buy_df['rsi_buy'] = buy_df['rsi'] > 30

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
            sell_df['rsi_sell'] = sell_df['rsi'] < 70

        if 'stoch' in default_list:
            sell_df['stoch_sell'] = (sell_df['slowd'] < 80) & (sell_df['slowd'].shift(1) < 80)

        if 'cci' in default_list:
            sell_df['cci_sell'] = sell_df['cci'] < 100

        # 通道指標

        if 'bbl' in default_list:
            sell_df['bb_sell'] = sell_df['Close'] < sell_df['bb_bbl']

        if 'kc' in default_list:
            sell_df['kc_sell'] = sell_df['Close'] < sell_df['kc']

        # 能量指標
        if 'cmf' in default_list:
            sell_df['cmf_sell'] = sell_df['cmf'] < 0

        if 'mfi' in default_list:
            sell_df['mfi_sell'] = sell_df['mfi'] < 80

        # ======================================== #
        stock_data = stock_data[['日期', 'Open','High','Low','Close','Volume']]

        stock_data = stock_data.rename(columns={'日期': 'date'})
        stock_data = stock_data.rename(columns={'Open': 'open'})
        stock_data = stock_data.rename(columns={'High': 'high'})
        stock_data = stock_data.rename(columns={'Low': 'low'})
        stock_data = stock_data.rename(columns={'Close': 'close'})


        stock_data['MA5'] = stock_data['close'].rolling(window=5).mean()
        stock_data['MA20'] = stock_data['close'].rolling(window=20).mean()

        trade_data = trades.loc[(trades['股票名稱'] == options) & (trades['使用規則'] == rule)]

        trade_data.loc[:, '日期'] = trade_data['日期'].str.replace("/", "-")

        trade_data = trade_data.rename(columns={'日期': 'date'})
        trade_data['price'] = trade_data['價格']
        trade_data['type'] = trade_data['買/賣'].replace({'買': 'buy', '賣': 'sell'})

    if request.method == 'POST':
        print('-'*30)
        print(sell_df)
        print('-'*30)
        violate = []
        follow = []

        user_id = int(current_user.get_id())
        data = request.get_json()

        trades = pd.read_csv('trades.csv', encoding='utf-8-sig')

        if data['type'] == 'sell':
            action = '賣'
        else:
            action = '買'
        
        rule = data['rule']
        options = data['options']

        trades = trades[(trades['user_id'] == user_id) & (trades['股票名稱'] == str(options)) & (trades['日期'] == data['date'].split(" ")[0].replace('-', '/').replace('/0', '/'))\
            & (trades['價格'] == data['price']) & (trades['買/賣'] == action)]
        temp_buy_df = buy_df
        temp_sell_df = sell_df

        trades = trades.to_dict(orient='records')
        print("test", temp_buy_df.iloc[:, :8])
        print(data['date'])
        if action == '買':
            temp_buy_df = temp_buy_df[(temp_buy_df['user_id'] == user_id) & (temp_buy_df['股票名稱'] == str(options)) & (temp_buy_df['日期'] == data['date'].replace('-', '/').replace('/0', '/'))\
            & (temp_buy_df['價格'] == data['price']) & (temp_buy_df['買/賣'] == action)]
            print(temp_buy_df)

            if 'sma' in temp_buy_df.columns:
                if temp_buy_df['sma_buy'].tolist()[0] == True:
                    follow.append("遵守 sma 上穿越")
                else:
                    violate.append("未遵守 sma 上穿越")

            if 'ema' in temp_buy_df.columns:
                if temp_buy_df['ema'].tolist()[0] == True:
                    follow.append("遵守 ema 上穿越")
                else:
                    violate.append("未遵守 ema 上穿越")

            if 'wma' in temp_buy_df.columns:
                if temp_buy_df['wma_buy'].tolist()[0] == True:
                    follow.append("遵守 wma 上穿越")
                else:
                    violate.append("未遵守 wma 上穿越")

            if 'hma' in temp_buy_df.columns:
                if temp_buy_df['hma_buy'].tolist()[0] == True:
                    follow.append("遵守 hma 上穿越")
                else:
                    violate.append("未遵守 hma 上穿越")    
        else:
            temp_sell_df = temp_sell_df[(temp_sell_df['user_id'] == user_id) & (temp_sell_df['股票名稱'] == str(options)) & (temp_sell_df['日期'] == data['date'].replace('-', '/').replace('/0', '/'))\
            & (temp_sell_df['價格'] == data['price']) & (temp_sell_df['買/賣'] == action)]
            print(temp_sell_df)
            if 'sma' in temp_sell_df.columns:
                if temp_sell_df['sma_sell'].tolist()[0] == True:
                    follow.append("遵守 sma 下穿越")
                else:
                    violate.append("未遵守 sma 下穿越")

            if 'ema' in temp_sell_df.columns:
                if temp_sell_df['ema'].tolist()[0] == True:
                    follow.append("遵守 ema 下穿越")
                else:
                    violate.append("未遵守 ema 下穿越")

            if 'wma' in temp_sell_df.columns:
                if temp_sell_df['wma_sell'].tolist()[0] == True:
                    follow.append("遵守 wma 下穿越")
                else:
                    violate.append("未遵守 wma 下穿越")

            if 'hma' in temp_sell_df.columns:
                if temp_sell_df['hma_sell'].tolist()[0] == True:
                    follow.append("遵守 hma 下穿越")
                else:
                    violate.append("未遵守 hma 下穿越")                            
        point_data = {}
        point_data['遵守'] = follow
        point_data['違反'] = violate
        return jsonify(point_data)

    items = trades
    items.drop_duplicates(subset=['使用規則', '股票名稱'], keep='first', inplace=True)
    items = items.to_dict(orient='records')

    # buy_df = buy_df.to_dict(orient='records')
    # sell_df = sell_df.to_dict(orient='records')
    data = stock_data.to_json(orient='records')
    trade_data = trade_data.to_json(orient='records')
    return render_template('review.html', items=items, buy_df=buy_df, sell_df=sell_df, data=data, trade_data=trade_data)

@app.route('/options')
def options():
    rule = request.args.get('rule')
    user_id = int(current_user.get_id())
    df = pd.read_csv('trades.csv', encoding='utf-8-sig')
    cards = df.loc[(df['user_id'] == user_id) & (df['使用規則'] == rule)]
    cards.drop_duplicates(subset=['使用規則', '股票名稱'], keep='first', inplace=True)

    return jsonify(cards['股票名稱'].tolist())  


# @app.route('/trade', methods=['POST'])
# def trade():


if __name__ == '__main__':
    app.run(debug=True)
