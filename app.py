import streamlit as st
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import gspread
from google.oauth2.service_account import Credentials

# ------------------------
# 🔐 パスワード設定（Secrets.toml にも対応可）
# ------------------------
PASSWORD = st.secrets.get("auth", {}).get("password", "mysecret123")

# ------------------------
# セッション初期化
# ------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "count" not in st.session_state:
    st.session_state["count"] = 0
if "log" not in st.session_state:
    st.session_state["log"] = pd.DataFrame(columns=["timestamp", "count"])

# ------------------------
# 認証処理
# ------------------------
if not st.session_state.get("authenticated", False):
    st.title("🔒 人数カウンター（ログイン）")
    pw = st.text_input("パスワードを入力", type="password")
    if pw:
        if pw == PASSWORD:
            st.session_state["authenticated"] = True
            st.experimental_rerun()  # 安全に再読み込み
        else:
            st.error("パスワードが違います")
    st.stop()  # 認証されるまでアプリ本体は実行されない

# ------------------------
# アプリ本体
# ------------------------
st.title("👥 人数カウンター")

col1, col2 = st.columns([1, 1])

with col1:
    if st.button("＋1人"):
        st.session_state["count"] += 1
        st.session_state["log"] = pd.concat(
            [st.session_state["log"], pd.DataFrame([[datetime.now(), st.session_state["count"]]], columns=["timestamp","count"])],
            ignore_index=True
        )
        st.experimental_rerun()

with col2:
    if st.button("－1人"):
        if st.session_state["count"] > 0:
            st.session_state["count"] -= 1
            st.session_state["log"] = pd.concat(
                [st.session_state["log"], pd.DataFrame([[datetime.now(), st.session_state["count"]]], columns=["timestamp","count"])],
                ignore_index=True
            )
            st.experimental_rerun()

st.subheader("現在の人数")
st.metric("人数", st.session_state["count"])

# ------------------------
# 日別・時間帯別グラフ
# ------------------------
if not st.session_state["log"].empty:
    st.subheader("日別人数推移")
    st.session_state["log"]['date'] = st.session_state["log"]['timestamp'].dt.date
    daily = st.session_state["log"].groupby('date')['count'].max()
    st.bar_chart(daily)

    st.subheader("時間帯別人数推移")
    st.session_state["log"]['hour'] = st.session_state["log"]['timestamp'].dt.hour
    hourly = st.session_state["log"].groupby('hour')['count'].max()
    st.bar_chart(hourly)
