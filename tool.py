from datetime import datetime
import feedparser
import pandas as pd
import twstock
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
import math
import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Date
from sqlalchemy import and_
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
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import Column, Integer, String, JSON


def get_graph(data, buy_point, sell_point):
    data = pd.DataFrame(data, columns=['Date', 'Volume', 'turnover' , 'Open', 'High', 'Low', 'Close', 'change', 'transaction'])
    
    data.drop(['turnover', 'transaction', 'change'], axis=1, inplace=True)

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

    if buy_point:
        fig.add_trace(go.Scatter(x=[point.date for point in buy_point],
        y=[point.price for point in buy_point],
        mode='markers',
        marker=dict(symbol='triangle-up', color='black', line=dict(color='black', width=2), size=13),
        text=[point.action for point in buy_point],
        customdata=[point.reason for point in buy_point],
        hovertemplate='<b>日期</b>: %{x}<br><b>價格</b>: %{y}<br><b>數量</b>: %{customdata[0]}<br><b>買賣</b>: %{text}<br><b>原因</b>: %{customdata[1]}<extra></extra>'),
        row=1, col=1)

    if sell_point:
        fig.add_trace(go.Scatter(x=[point.date for point in sell_point],
        y=[point.price for point in sell_point],
        mode='markers',
        marker=dict(symbol='triangle-down', color='black', line=dict(color='black', width=2), size=13),
        text=[point.action for point in sell_point],
        customdata=[point.reason for point in sell_point],
        hovertemplate='<b>日期</b>: %{x}<br><b>價格</b>: %{y}<br><b>數量</b>: %{customdata[0]}<br><b>買賣</b>: %{text}<br><b>原因</b>: %{customdata[1]}<extra></extra>'),
        row=1, col=1)
    return fig.to_html()