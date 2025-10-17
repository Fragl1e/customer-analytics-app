import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta
import traceback # エラー追跡のためインポート

# ------------------------
# ページ設定 (最初に一度だけ呼び出す)
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
# ✅ Googleスプレッドシート接続
# ------------------------
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
        st.error("Googleスプレッドシートへの認証に失敗しました。secrets.toml の設定を確認してください。")
        st.error(f"詳細エラー: {e}")
        return None

# st.cache_data を使ってデータの取得をキャッシュ
@st.cache_data(ttl=30) # キャッシュ時間を短めに設定
def get_sheet_data(_worksheet):
    """
    ワークシートから全データを取得し、DataFrameに変換する。
    KeyErrorを防ぐため、より堅牢な方法でデータを読み込む。
    """
    all_values = _worksheet.get_all_values()
    if len(all_values) > 1:  # ヘッダー + 1行以上のデータがある場合
        headers = all_values[0]
        # DataFrameを作成
        df = pd.DataFrame(all_values[1:], columns=headers)
        return df
    else:
        # ヘッダーしかない、または空の場合は、正しい列名を持つ空のDataFrameを返す
        return pd.DataFrame(columns=['時刻', '人数'])


gc = connect_to_google_sheet()
if gc is None:
    st.stop()

try:
    SPREADSHEET_NAME = "customer_counter"
    sh = gc.open(SPREADSHEET_NAME)
    worksheet = sh.sheet1
except gspread.exceptions.SpreadsheetNotFound:
    st.error(f"スプレッドシート '{SPREADSHEET_NAME}' が見つかりません。")
    st.info("指定した名前のスプレッドシートを作成し、サービスアカウントに共有してください。")
    st.stop()
except Exception as e:
    st.error(f"スプレッドシートを開く際にエラーが発生しました: {e}")
    st.stop()

# ------------------------
# 📊 データ取得と前処理
# ------------------------
data = get_sheet_data(worksheet)

if data.empty:
    current_count = 0
else:
    # データ型を適切に変換
    data["人数"] = pd.to_numeric(data["人数"])
    data["時刻"] = pd.to_datetime(data["時刻"])
    current_count = data["人数"].iloc[-1]
    # 日付・時間列を追加
    data["日付"] = data["時刻"].dt.date
    data["時間帯"] = data["時刻"].dt.hour

# ------------------------
# 🧮 メインのカウンターUI
# ------------------------
st.title("👥 お客さんカウンター")
st.metric(label="現在の人数", value=f"{current_count} 人")

col1, col2 = st.columns(2)

def update_sheet(new_count):
    """スプレッドシートに新しいカウントを追記する"""
    JST = timezone(timedelta(hours=+9))
    timestamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    try:
        worksheet.append_row([timestamp, new_count])
        st.cache_data.clear() # キャッシュをクリアして即時反映
    except Exception as e:
        st.error(f"スプレッドシートへの書き込みに失敗しました: {e}")

with col1:
    if st.button("＋1人", use_container_width=True, type="primary"):
        new_count = current_count + 1
        update_sheet(new_count)
        st.success(f"人数を {new_count} 人に更新しました。")
        st.rerun()

with col2:
    if st.button("−1人", use_container_width=True):
        if current_count > 0:
            new_count = current_count - 1
            update_sheet(new_count)
            st.warning(f"人数を {new_count} 人に更新しました。")
            st.rerun()
        else:
            st.warning("現在の人数は0人です。")

# ------------------------
# ⚙️ 管理者用リセット
# ------------------------
with st.expander("⚠️ 管理者用リセット"):
    if st.button("リセット（0に戻す）", type="secondary"):
        update_sheet(0)
        st.error("カウントを0にリセットしました。")
        st.rerun()

# ------------------------
# 📈 グラフ表示
# ------------------------
if not data.empty:
    st.divider()
    st.subheader("📈 データ分析")

    st.write("日別の最終人数推移")
    daily_counts = data.groupby("日付")["人数"].last()
    st.bar_chart(daily_counts, use_container_width=True)

    st.subheader("時間帯ごとの人数変化")
    default_date = data["日付"].max()
    selected_date = st.date_input("日付を選択", value=default_date)

    if selected_date:
        hourly_data = data[data["日付"] == selected_date]
        if not hourly_data.empty:
            hourly_counts = hourly_data.set_index("時刻")["人数"].resample("h").last().fillna(method='ffill')
            full_day_range = pd.date_range(start=selected_date, end=selected_date + pd.Timedelta(hours=23), freq='h')
            hourly_counts = hourly_counts.reindex(full_day_range).fillna(0) # 0で埋める
            hourly_counts.index = hourly_counts.index.hour
            st.bar_chart(hourly_counts, use_container_width=True)
        else:
            st.info(f"{selected_date}のデータはありません。")
else:
    st.info("まだデータが記録されていません。")

