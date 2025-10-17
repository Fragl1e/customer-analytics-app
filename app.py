import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt

# ------------------------
# 🔒 パスワード設定
# ------------------------
PASSWORD = "mysecret123"  # 後で Secrets に置き換え可能

# セッション状態の初期化
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "count" not in st.session_state:
    st.session_state.count = 0
if "log" not in st.session_state:
    st.session_state.log = pd.DataFrame(columns=["timestamp", "count"])

# ------------------------
# 🔐 認証
# ------------------------
if not st.session_state.authenticated:
    st.title("🔒 人数カウンター（ログイン）")
    pw = st.text_input("パスワードを入力", type="password")

    if pw:
        if pw == PASSWORD:
            st.session_state.authenticated = True
            st.experimental_rerun()  # 状態更新後に再読み込み
        else:
            st.error("パスワードが違います。")
    st.stop()  # 認証されるまでここで停止

# ------------------------
# ✅ 認証後アプリ本体
# ------------------------
st.title("👥 人数カウンター")

col1, col2 = st.columns([1, 1])

with col1:
    if st.button("＋1人"):
        st.session_state.count += 1
        # ログに記録（日時＋人数）
        st.session_state.log = pd.concat(
            [st.session_state.log, pd.DataFrame([[datetime.now(), st.session_state.count]], columns=["timestamp","count"])],
            ignore_index=True
        )
        st.experimental_rerun()  # 状態更新後に再読み込み

with col2:
    if st.button("－1人"):
        if st.session_state.count > 0:
            st.session_state.count -= 1
            st.session_state.log = pd.concat(
                [st.session_state.log, pd.DataFrame([[datetime.now(), st.session_state.count]], columns=["timestamp","count"])],
                ignore_index=True
            )
            st.experimental_rerun()

st.subheader("現在の人数")
st.metric("人数", st.session_state.count)

# ------------------------
# 📊 日別・時間帯別グラフ
# ------------------------
if not st.session_state.log.empty:
    st.subheader("日別人数推移")
    st.session_state.log['date'] = st.session_state.log['timestamp'].dt.date
    daily = st.session_state.log.groupby('date')['count'].max()
    st.bar_chart(daily)

    st.subheader("時間帯別人数推移")
    st.session_state.log['hour'] = st.session_state.log['timestamp'].dt.hour
    hourly = st.session_state.log.groupby('hour')['count'].max()
    st.bar_chart(hourly)
