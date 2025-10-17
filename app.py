import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta

# ------------------------
# ページ設定
# ------------------------
st.set_page_config(page_title="お客さんカウンター", layout="centered", initial_sidebar_state="collapsed")

# ------------------------
# 🔒 パスワード認証
# ------------------------
try:
    PASSWORD = st.secrets["auth"]["password"]
except KeyError:
    st.error("認証用のパスワードが secrets.toml に設定されていません。")
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 お客さんカウンター（ログイン）")
    st.write("Streamlit Cloudの secrets に設定したパスワードを入力してください。")
    pw = st.text_input("パスワード", type="password")
    if pw:
        if pw == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("パスワードが違います")
    st.stop()

# ------------------------
# ✅ Googleスプレッドシート接続 & 初期化
# ------------------------
EXPECTED_HEADERS = ['時刻', '人数']

@st.cache_resource
def connect_to_google_sheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=scope
        )
        gc = gspread.authorize(credentials)
        return gc
    except Exception as e:
        st.error(f"Google認証に失敗: {e}")
        return None

def initialize_sheet(worksheet):
    """
    スプレッドシートのヘッダーを確認し、存在しない場合は自動的に作成する関数。
    """
    try:
        # 1行目を取得してヘッダーを確認
        current_headers = worksheet.row_values(1)
        if current_headers != EXPECTED_HEADERS:
             # ヘッダーが期待通りでない場合（空も含む）、ヘッダー行をクリアして再設定
             worksheet.clear()
             worksheet.append_row(EXPECTED_HEADERS, value_input_option='USER_ENTERED')
             st.toast("スプレッドシートを初期化し、ヘッダーを作成しました。")
    except gspread.exceptions.APIError as e:
        # シートが完全に空で、row_values(1)がエラーになる場合
        if e.response.status_code == 400:
             worksheet.append_row(EXPECTED_HEADERS, value_input_option='USER_ENTERED')
             st.toast("空のスプレッドシートを初期化し、ヘッダーを作成しました。")
        else:
            raise e


@st.cache_data(ttl=10) # キャッシュ時間を短くして更新を反映しやすくする
def get_sheet_data(_worksheet):
    """
    ヘッダーが必ず存在することを前提にデータを取得する関数。
    """
    all_records = _worksheet.get_all_records()
    if not all_records:
        return pd.DataFrame(columns=EXPECTED_HEADERS)
    
    df = pd.DataFrame(all_records)
    return df

gc = connect_to_google_sheet()
if gc is None:
    st.stop()

try:
    SPREADSHEET_NAME = "customer_counter"
    sh = gc.open(SPREADSHEET_NAME)
    worksheet = sh.sheet1
    # ★★★ アプリ起動時に必ずシートの初期化処理を実行 ★★★
    initialize_sheet(worksheet)

except gspread.exceptions.SpreadsheetNotFound:
    st.error(f"スプレッドシート '{SPREADSHEET_NAME}' が見つかりません。")
    st.info("指定した名前のスプレッドシートを作成し、サービスアカウントに共有してください。")
    st.stop()
except Exception as e:
    st.error(f"スプレッドシートを開く際にエラーが発生しました: {e}")
    st.stop()

# ------------------------
# 📊 データ取得と計算
# ------------------------
data = get_sheet_data(worksheet)
total_visitors = 0
current_count = 0

if not data.empty:
    try:
        data["人数"] = pd.to_numeric(data["人数"])
        data["時刻"] = pd.to_datetime(data["時刻"])
        
        if not data.empty:
            current_count = data["人数"].iloc[-1]
            data["日付"] = data["時刻"].dt.date
            data["時間帯"] = data["時刻"].dt.hour

            diffs = data["人数"].diff()
            # 最初の行の NaN を 0 で埋め、最初の来客をカウントする
            initial_visitor = data["人数"].iloc[0] if not data.empty else 0
            total_visitors = int(diffs[diffs > 0].sum() + initial_visitor)

    except (KeyError, TypeError) as e:
        st.error("データの処理中にエラーが発生しました。")
        st.error(f"エラー詳細: {e}")
        data = pd.DataFrame() 

# ------------------------
# 🧮 メインのカウンターUI
# ------------------------
st.title("👥 お客さんカウンター")

col_metric1, col_metric2 = st.columns(2)
col_metric1.metric(label="現在の人数", value=f"{current_count} 人")
col_metric2.metric(label="累計来客数", value=f"{total_visitors} 人", help="人数が増えた時の合計値です。")

st.divider()

col_button1, col_button2 = st.columns(2)

def update_sheet(new_count):
    JST = timezone(timedelta(hours=+9))
    timestamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    try:
        worksheet.append_row([timestamp, new_count], value_input_option='USER_ENTERED')
        st.cache_data.clear() # キャッシュをクリアして即時反映
    except Exception as e:
        st.error(f"スプレッドシートへの書き込みに失敗しました: {e}")

with col_button1:
    if st.button("＋1人", use_container_width=True, type="primary"):
        new_count = current_count + 1
        update_sheet(new_count)
        st.rerun()

with col_button2:
    if st.button("−1人", use_container_width=True):
        if current_count > 0:
            new_count = current_count - 1
            update_sheet(new_count)
            st.rerun()
        else:
            st.warning("現在の人数は0人です。")

with st.expander("⚠️ 管理者用リセット"):
    if st.button("リセット（0に戻す）"):
        update_sheet(0)
        st.rerun()

# ------------------------
# 📈 グラフ表示
# ------------------------
if not data.empty and "日付" in data.columns:
    st.divider()
    st.subheader("📈 データ分析")
    st.write("日別の最終人数推移")
    daily_counts = data.groupby("日付")["人数"].last()
    st.bar_chart(daily_counts, use_container_width=True)

    st.subheader("時間帯ごとの人数変化")
    # 日付のリストを降順で作成
    date_options = sorted(data["日付"].unique(), reverse=True)
    selected_date = st.selectbox("日付を選択", options=date_options)

    if selected_date:
        hourly_data = data[data["日付"] == selected_date]
        if not hourly_data.empty:
            hourly_counts = hourly_data.set_index("時刻")["人数"].resample("h").last().fillna(method='ffill')
            full_day_range = pd.date_range(start=pd.to_datetime(selected_date), end=pd.to_datetime(selected_date) + pd.Timedelta(hours=23), freq='h')
            hourly_counts = hourly_counts.reindex(full_day_range).fillna(0)
            hourly_counts.index = hourly_counts.index.hour
            st.bar_chart(hourly_counts, use_container_width=True)
        else:
            st.info(f"{selected_date}のデータはありません。")


