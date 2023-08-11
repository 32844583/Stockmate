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
        width=800,
        height=800,
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
    trade_df['日期'] = pd.to_datetime(trade_df['日期'])

    fig.add_trace(go.Scatter(x=trade_df.loc[trade_df['買/賣'] == '買', '日期'],
    y=trade_df.loc[trade_df['買/賣'] == '買', '價格'],
    mode='markers',
    marker=dict(symbol='triangle-up', color='green', size=30),
    text=trade_df.loc[trade_df['買/賣'] == '買', '買/賣'],
    customdata=trade_df.loc[trade_df['買/賣'] == '買', ['數量', '原因']],
    hovertemplate='<b>日期</b>: %{x}<br><b>價格</b>: %{y}<br><b>數量</b>: %{customdata[0]}<br><b>買賣</b>: %{text}<br><b>原因</b>: %{customdata[1]}<extra></extra>'),
    row=1, col=1)

    fig.add_trace(go.Scatter(x=trade_df.loc[trade_df['買/賣'] == '賣', '日期'],
    y=trade_df.loc[trade_df['買/賣'] == '賣', '價格'],
    mode='markers',
    marker=dict(symbol='triangle-down', color='red', size=30),
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

@app.route('/cards', methods=['POST', 'GET'])
@login_required
def cards():
    current_dir = os.getcwd()
    filename = 'cards.csv'
    print("test2")
    if not os.path.exists(os.path.join(current_dir, filename)):
        df = pd.DataFrame(columns=["card_id", "user_id", "卡組名稱", "使用卡牌"])
        df.to_csv("cards.csv", index=False, encoding='utf-8-sig')
    df = pd.read_csv('cards.csv', encoding='utf-8-sig')

    if request.method == 'POST':
        rule = request.form.get("rule")

        user_id = int(current_user.get_id())
        card_list = request.form.getlist('card_name') # 獲取勾選框的 value 列表
        card_string = '-'.join(card_list) # 將列表中的元素用 '-' 串成一個字串
        card_id = pd.read_csv('cards.csv', encoding='utf-8-sig').shape[0]
        df = pd.DataFrame([[ card_id, user_id, rule, card_string]], \
            columns=["card_id", "user_id",  "卡組名稱", "使用卡牌"])
        df.to_csv("cards.csv", index=False, encoding='utf-8-sig', mode="a", header=False)
        df = pd.read_csv('cards.csv', encoding='utf-8-sig')
        print("test")
        return redirect(url_for('cards'))
    user_id = int(current_user.get_id())
    print(df)
    card_df = df[(df['user_id'] == user_id)]
    cards=card_df.to_dict(orient='records')
    print(cards)
    return render_template('cards.html', cards=cards)

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



@app.route('/review', methods=['GET', 'POST'])
@login_required
def review():
    user_id = int(current_user.get_id())
    df = pd.read_csv('trades.csv', encoding='utf-8-sig')
    trades = df.loc[(df['user_id'] == user_id)]
    buy_df = pd.DataFrame()
    sell_df = pd.DataFrame()
    if request.method == 'POST':
        rule = request.form.get("rule")
        options = request.form.get("options")
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
        # 计算简单移动平均线（SMA）
        stock_data['sma'] = ta.sma(stock_data['Close'], length=20)

        # 计算相对强弱指数（RSI）
        stock_data['rsi'] = ta.rsi(stock_data['Close'], length=14)

        # 计算布林带（Bollinger Bands）
        stock_data[['bb_bbm', 'bb_bbh', 'bb_bbl', 'bb_bbb', 'bb_BBP']] = ta.bbands(stock_data['Close'], length=20)

        # 计算能量潮（Chaikin Money Flow, CMF）
        stock_data['cmf'] = ta.cmf(stock_data['High'], stock_data['Low'], stock_data['Close'], stock_data['Volume'], length=20)
        
        # 判断买入信号是否达成

        df = pd.merge(df, stock_data, how='left', on='日期')
        df = df.drop(['Dividends', 'Stock Splits'], axis=1)
        buy_df = df.loc[df['買/賣'] == '買']
        buy_df['sma_buy'] = buy_df['Close'] > buy_df['sma']
        buy_df['rsi_buy'] = buy_df['rsi'] < 30
        buy_df['bb_buy'] = buy_df['Close'] < buy_df['bb_bbl']
        buy_df['cmf_buy'] = buy_df['cmf'] > 0
        sell_df = df.loc[df['買/賣'] == '賣']
        sell_df['sma_sell'] = sell_df['Close'] < sell_df['sma']
        sell_df['rsi_sell'] = sell_df['rsi'] > 70
        sell_df['bb_sell'] = sell_df['Close'] > sell_df['bb_bbl']
        sell_df['cmf_sell'] = sell_df['cmf'] < 0
        print(buy_df)
        print(sell_df)
        # if 'RSI' in data[1:]:
        #     stock_data['RSI'] = ta.rsi(stock_data['Close'], length=rsi_period)
        # elif 'MA' in data[1:]:
        #     ...
        # stock_data['OBV'] = ta.obv(stock_data['Close'], stock_data['Volume'])


        # print(stock_data)
        for card in data[1:]:
            print(card)


    trades.drop_duplicates(subset=['使用規則', '股票名稱'], keep='first', inplace=True)

    trades = trades.to_dict(orient='records')

    buy_df = buy_df.to_dict(orient='records')
    sell_df = sell_df.to_dict(orient='records')
    return render_template('review.html', trades=trades, buy_df=buy_df, sell_df=sell_df)

@app.route('/options')
def options():

    rule = request.args.get('rule')
    user_id = int(current_user.get_id())
    df = pd.read_csv('trades.csv', encoding='utf-8-sig')
    cards = df.loc[(df['user_id'] == user_id) & (df['使用規則'] == rule)]
    cards.drop_duplicates(subset=['使用規則', '股票名稱'], keep='first', inplace=True)

    return jsonify(cards['股票名稱'].tolist())


@app.route('/form', methods=['GET', 'POST'])
@login_required
def form():
    return render_template('form.html')

if __name__ == '__main__':
    app.run(debug=True)
