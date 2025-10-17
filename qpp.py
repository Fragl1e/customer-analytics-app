import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ------------------------
# 🔒 パスワード認証
# ------------------------
st.set_page_config(page_title="お客さんカウンター", layout="centered")
PASSWORD = "mysecret123"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 お客さんカウンター（ログイン）")
    pw = st.text_input("パスワードを入力してください", type="password")

    if pw:
        if pw == PASSWORD:
            st.session_state.authenticated = True
            st.success("ログイン成功！")
            st.experimental_rerun()
        else:
            st.error("パスワードが違います。")
    st.stop()

# ------------------------
# ✅ Googleスプレッドシート接続
# ------------------------
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

credentials = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scope)
gc = gspread.authorize(credentials)

SPREADSHEET_NAME = "customer_counter"  # ご自身のスプレッドシート名に変更
sh = gc.open(SPREADSHEET_NAME)
worksheet = sh.sheet1

# ------------------------
# 📊 現在のカウント取得
# ------------------------
data = pd.DataFrame(worksheet.get_all_records())

if data.empty:
    current_count = 0
else:
    current_count = data["人数"].iloc[-1]

# ------------------------
# 🧮 カウンター表示と操作ボタン
# ------------------------
st.title("👥 お客さんカウンター")
st.metric(label="現在の人数", value=f"{current_count} 人")

col1, col2 = st.columns(2)

with col1:
    if st.button("＋1人", use_container_width=True):
        new_count = current_count + 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        worksheet.append_row([timestamp, new_count])
        st.success(f"{new_count}人目を記録しました！")
        st.experimental_rerun()

with col2:
    if st.button("−1人", use_container_width=True):
        new_count = max(current_count - 1, 0)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        worksheet.append_row([timestamp, new_count])
        st.warning(f"{current_count} → {new_count} に減らしました。")
        st.experimental_rerun()

# ------------------------
# ⚙️ 小さくリセット機能（誤操作防止）
# ------------------------
with st.expander("⚠️ 管理者用リセット（押すと0に戻ります）"):
    if st.button("リセットする"):
        worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 0])
        st.error("カウントを0にリセットしました。")
        st.experimental_rerun()
