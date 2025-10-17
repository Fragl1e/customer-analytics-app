import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ------------------------
# 🔒 パスワード認証（Secrets）
# ------------------------
st.set_page_config(page_title="お客さんカウンター", layout="centered")
PASSWORD = st.secrets["auth"]["password"]

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 お客さんカウンター（ログイン）")
    pw = st.text_input("パスワードを入力してください", type="password")
    if pw:
        if pw == PASSWORD:
            st.session_state.authenticated = True
            st.experimental_rerun()
        else:
            st.error("パスワードが違います")
    st.stop()

# ------------------------
# ✅ Googleスプレッドシート接続
# ------------------------
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

credentials = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scope)
gc = gspread.authorize(credentials)

SPREADSHEET_NAME = "customer_counter"
sh = gc.open(SPREADSHEET_NAME)
worksheet = sh.sheet1

# ------------------------
# 📊 現在のカウント取得
# ------------------------
data = pd.DataFrame(worksheet.get_all_records())
current_count = 0 if data.empty else data["人数"].iloc[-1]

# ------------------------
# 🧮 カウンター表示と操作
# ------------------------
st.title("👥 お客さんカウンター")
st.metric(label="現在の人数", value=f"{current_count} 人")

col1, col2 = st.columns(2)

with col1:
    if st.button("＋1人", use_container_width=True):
        new_count = current_count + 1
        worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), new_count])
        st.success(f"{new_count}人目を記録しました！")
        st.experimental_rerun()

with col2:
    if st.button("−1人", use_container_width=True):
        new_count = max(current_count - 1, 0)
        worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), new_count])
        st.warning(f"{current_count} → {new_count} に減らしました。")
        st.experimental_rerun()

# ------------------------
# ⚙️ 管理者用リセット（隠し）
# ------------------------
with st.expander("⚠️ 管理者用リセット"):
    if st.button("リセット（0に戻す）"):
        worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 0])
        st.error("カウントを0にリセットしました。")
        st.experimental_rerun()
