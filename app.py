import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta

# ------------------------
# 定数とページ設定
# ------------------------
PAGE_CONFIG = {
    "page_title": "お客さんカウンター",
    "layout": "centered",
    "initial_sidebar_state": "collapsed"
}
st.set_page_config(**PAGE_CONFIG)

# Googleスプレッドシート関連の定数
GSPREAD_SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SPREADSHEET_NAME = "customer_counter"
EXPECTED_HEADERS = ['時刻', '人数']
JST = timezone(timedelta(hours=+9))


# ------------------------
# 🔒 パスワード認証
# ------------------------
def authenticate_user():
    """ユーザー認証を行う"""
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
        password_input = st.text_input("パスワード", type="password", key="password_input")
        
        if st.button("ログイン", key="login_button"):
            if password_input == PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("パスワードが違います")
        st.stop()

authenticate_user()

# ------------------------
# ✅ Googleスプレッドシート接続 & 初期化
# ------------------------
@st.cache_resource
def setup_gspread_connection():
    """Google Sheetsへの接続を確立し、ワークシートオブジェクトを返す（初回実行時のみ）"""
    try:
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=GSPREAD_SCOPES
        )
        gc = gspread.authorize(credentials)
        
        try:
            sh = gc.open(SPREADSHEET_NAME)
        except gspread.exceptions.SpreadsheetNotFound:
            st.error(f"スプレッドシート '{SPREADSHEET_NAME}' が見つかりません。")
            st.info("指定した名前のスプレッドシートを作成し、サービスアカウントに共有してください。")
            return None
            
        worksheet = sh.sheet1
        initialize_worksheet(worksheet)
        return worksheet

    except Exception as e:
        st.error(f"Google認証またはスプレッドシート接続に失敗: {e}")
        return None

def initialize_worksheet(worksheet):
    """ワークシートのヘッダーを確認し、必要であれば作成する"""
    try:
        current_headers = worksheet.row_values(1)
        if current_headers != EXPECTED_HEADERS:
            worksheet.clear()
            worksheet.append_row(EXPECTED_HEADERS, value_input_option='USER_ENTERED')
            st.toast("スプレッドシートを初期化し、ヘッダーを作成しました。")
    except gspread.exceptions.APIError as e:
        # シートが完全に空の場合のエラーをハンドル
        if 'exceeds grid limits' in str(e): # エラーメッセージが変更される可能性を考慮
             worksheet.append_row(EXPECTED_HEADERS, value_input_option='USER_ENTERED')
             st.toast("空のシートを初期化し、ヘッダーを作成しました。")
        else:
            raise e

# ------------------------
# 📊 データ取得と状態管理
# ------------------------
@st.cache_data(ttl=60) # キャッシュ時間を60秒に延長し、API呼び出しを削減
def fetch_dataframe(_worksheet):
    """スプレッドシートから全データを取得し、DataFrameとして返す"""
    records = _worksheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=EXPECTED_HEADERS)
    
    df = pd.DataFrame(records)
    # データ型の変換とエラーハンドリング
    try:
        df["人数"] = pd.to_numeric(df["人数"])
        df["時刻"] = pd.to_datetime(df["時刻"])
        df["日付"] = df["時刻"].dt.date
        df["時間帯"] = df["時刻"].dt.hour
    except (KeyError, TypeError):
        st.error("スプレッドシートのデータ形式が正しくありません。ヘッダーを確認してください。")
        return pd.DataFrame(columns=EXPECTED_HEADERS)
    return df

def initialize_app_state(worksheet):
    """アプリケーションの初期状態をsession_stateに設定する"""
    if "initialized" in st.session_state:
        return

    df = fetch_dataframe(worksheet)
    st.session_state.df = df
    
    if not df.empty:
        st.session_state.current_count = df["人数"].iloc[-1]
        
        # 累計来客数の計算
        diffs = df["人数"].diff()
        initial_visitor = df["人数"].iloc[0]
        total_visitors = int(diffs[diffs > 0].sum() + initial_visitor)
        st.session_state.total_visitors = total_visitors
    else:
        st.session_state.current_count = 0
        st.session_state.total_visitors = 0
    
    st.session_state.initialized = True

def record_count(worksheet, new_count):
    """新しい人数をスプレッドシートに記録する"""
    try:
        timestamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        worksheet.append_row([timestamp, new_count], value_input_option='USER_ENTERED')
        # データを書き込んだら、次のデータ取得時に最新情報が反映されるようキャッシュをクリア
        st.cache_data.clear()
    except Exception as e:
        st.error(f"スプレッドシートへの書き込みに失敗しました: {e}")

# --- メイン処理 ---
worksheet = setup_gspread_connection()
if worksheet is None:
    st.stop()

# アプリのセッション状態を初期化
initialize_app_state(worksheet)

# ------------------------
# 🧮 メインのカウンターUI
# ------------------------
st.title("👥 お客さんカウンター")

col_metric1, col_metric2 = st.columns(2)
col_metric1.metric(label="現在の人数", value=f"{st.session_state.current_count} 人")
col_metric2.metric(label="累計来客数", value=f"{st.session_state.total_visitors} 人", help="人数が増えた時の合計値です。")

st.divider()

col_button1, col_button2 = st.columns(2)

if col_button1.button("＋1人", use_container_width=True, type="primary"):
    new_count = st.session_state.current_count + 1
    st.session_state.current_count = new_count
    st.session_state.total_visitors += 1
    record_count(worksheet, new_count)
    st.rerun()

if col_button2.button("−1人", use_container_width=True):
    if st.session_state.current_count > 0:
        new_count = st.session_state.current_count - 1
        st.session_state.current_count = new_count
        record_count(worksheet, new_count)
        st.rerun()
    else:
        st.warning("現在の人数は0人です。")

with st.expander("⚠️ 管理者用リセット"):
    if st.button("リセット（0に戻す）"):
        st.session_state.current_count = 0
        record_count(worksheet, 0)
        st.rerun()

# ------------------------
# 📈 グラフ表示
# ------------------------
df = st.session_state.df
if not df.empty and "日付" in df.columns:
    st.divider()
    st.subheader("📈 データ分析")
    
    # 日別の最終人数推移
    st.write("日別の最終人数推移")
    daily_counts = df.groupby("日付")["人数"].last()
    st.bar_chart(daily_counts, use_container_width=True)

    # 時間帯ごとの人数変化
    st.write("時間帯ごとの人数変化")
    date_options = sorted(df["日付"].unique(), reverse=True)
    selected_date = st.selectbox("日付を選択", options=date_options)

    if selected_date:
        hourly_data = df[df["日付"] == selected_date]
        # set_indexの前に時刻の重複がないか確認・処理
        if not hourly_data.duplicated(subset='時刻').all():
            hourly_data = hourly_data.drop_duplicates(subset='時刻', keep='last')
            hourly_counts = hourly_data.set_index("時刻")["人数"].resample("H").ffill()
            full_day_range = pd.date_range(start=pd.to_datetime(selected_date), periods=24, freq='H')
            hourly_counts = hourly_counts.reindex(full_day_range, method='ffill').fillna(0)
            hourly_counts.index = hourly_counts.index.hour
            st.bar_chart(hourly_counts, use_container_width=True)
        else:
            st.info("選択された日付のデータ処理中に問題が発生しました。")


