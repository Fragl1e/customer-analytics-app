import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta

# ------------------------
# 定数とページ設定
# ------------------------
st.set_page_config(page_title="累計カウンター", layout="centered", initial_sidebar_state="collapsed")

# Googleスプレッドシート関連の定数
GSPREAD_SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SPREADSHEET_NAME = "customer_counter"
# スプレッドシートのヘッダーを「累計」専用に変更
EXPECTED_HEADERS = ['時刻', '累計']
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
        st.title("🔒 累計カウンター（ログイン）")
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
    """Google Sheetsへの接続を確立し、ワークシートオブジェクトを返す"""
    try:
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=GSPREAD_SCOPES
        )
        gc = gspread.authorize(credentials)
        sh = gc.open(SPREADSHEET_NAME)
        worksheet = sh.sheet1
        initialize_worksheet(worksheet)
        return worksheet
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"スプレッドシート '{SPREADSHEET_NAME}' が見つかりません。")
        st.info("同名のスプレッドシートを作成し、サービスアカウントに共有してください。")
        return None
    except Exception as e:
        st.error(f"Google認証または接続に失敗: {e}")
        return None

def initialize_worksheet(worksheet):
    """ワークシートのヘッダーを確認し、必要であれば作成する"""
    try:
        current_headers = worksheet.row_values(1)
        if current_headers != EXPECTED_HEADERS:
            worksheet.clear()
            worksheet.append_row(EXPECTED_HEADERS, value_input_option='USER_ENTERED')
            st.toast("スプレッドシートを「累計カウンター」用に初期化しました。")
    except gspread.exceptions.APIError:
        worksheet.append_row(EXPECTED_HEADERS, value_input_option='USER_ENTERED')
        st.toast("空のシートを「累計カウンター」用に初期化しました。")
    except Exception as e:
        st.error(f"シートの初期化中にエラーが発生しました: {e}")
        st.stop()

# ------------------------
# 📊 データ取得と状態管理
# ------------------------
@st.cache_data(ttl=60)
def fetch_dataframe(_worksheet):
    """スプレッドシートから全データを取得し、DataFrameとして返す"""
    records = _worksheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=EXPECTED_HEADERS)
    df = pd.DataFrame(records)
    try:
        df["累計"] = pd.to_numeric(df["累計"])
        df["時刻"] = pd.to_datetime(df["時刻"])
        df["日付"] = df["時刻"].dt.date
    except (KeyError, TypeError):
        st.error("スプレッドシートのデータ形式が正しくありません。")
        return pd.DataFrame(columns=EXPECTED_HEADERS)
    return df

def initialize_app_state(worksheet):
    """アプリの初回起動時に累計を読み込む"""
    if "initialized" in st.session_state:
        return
    df = fetch_dataframe(worksheet)
    st.session_state.df = df
    st.session_state.total_visitors = df["累計"].iloc[-1] if not df.empty else 0
    st.session_state.initialized = True

# ★★★★★ ここがデータをスプレッドシートに保存する関数です ★★★★★
def record_visit(worksheet, new_total):
    """
    ボタンが押された時の時刻と新しい累計人数をスプレッドシートに記録（保存）する関数。
    """
    try:
        timestamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        # ↓ この行が、実際にスプレッドシートに新しい行を追加してデータを保存しています。
        worksheet.append_row([timestamp, new_total], value_input_option='USER_ENTERED')
        # キャッシュをクリアして、グラフ表示などが次回更新時に最新になるようにする
        st.cache_data.clear()
    except Exception as e:
        st.error(f"スプレッドシートへの書き込み（保存）に失敗しました: {e}")

# --- メイン処理 ---
worksheet = setup_gspread_connection()
if worksheet is None: st.stop()

initialize_app_state(worksheet)

# ------------------------
# 🧮 メインのカウンターUI
# ------------------------
st.title("👥 累計カウンター")

# 「累計来客数」の表示のみに変更
st.metric(label="累計来客数", value=f"{st.session_state.total_visitors} 人")

st.divider()

# 「+1」ボタンのみに変更
if st.button("＋1", use_container_width=True, type="primary", help="来客を1人追加して記録します。"):
    new_total = st.session_state.total_visitors + 1
    st.session_state.total_visitors = new_total
    # ボタンが押されたら、記録（保存）関数を呼び出す
    record_visit(worksheet, new_total)
    st.rerun()

with st.expander("⚠️ 管理者用リセット"):
    if st.button("累計を0に戻す"):
        st.session_state.total_visitors = 0
        # 0になったことも記録（保存）する
        record_visit(worksheet, 0)
        st.rerun()

# ------------------------
# 📈 グラフ表示
# ------------------------
df = st.session_state.df
if not df.empty:
    st.divider()
    st.subheader("📈 累計の推移")
    
    # 日付を選択して、その日の累計の推移を表示
    date_options = sorted(df["日付"].unique(), reverse=True)
    selected_date = st.selectbox("グラフを表示する日付を選択", options=date_options)
    
    if selected_date:
        daily_data = df[df["日付"] == selected_date].copy()
        if not daily_data.empty:
            # グラフが見やすいように、時刻をインデックスに設定
            daily_data.set_index('時刻', inplace=True)
            st.bar_chart(daily_data['累計'])
        else:
            st.info("その日のデータはありません。")


解説：データが保存される仕組み
ご質問いただいた「スプレッドシートへの保存」は、新しいコードの**record_visit**という関数が担当しています。
# ★★★★★ ここがデータをスプレッドシートに保存する関数です ★★★★★
def record_visit(worksheet, new_total):
    """
    ボタンが押された時の時刻と新しい累計人数をスプレッドシートに記録（保存）する関数。
    """
    try:
        timestamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        # ↓ この行が、実際にスプレッドシートに新しい行を追加してデータを保存しています。
        worksheet.append_row([timestamp, new_total], value_input_option='USER_ENTERED')
        
        st.cache_data.clear()
    except Exception as e:
        st.error(f"スプレッドシートへの書き込み（保存）に失敗しました: {e}")


