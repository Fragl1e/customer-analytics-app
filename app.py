import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import traceback # エラー追跡のためインポート

# ------------------------
# ページ設定 (最初に一度だけ呼び出す)
# ------------------------
st.set_page_config(page_title="COUNTER", layout="centered", initial_sidebar_state="collapsed")

# ------------------------
# 🔒 パスワード認証
# ------------------------
# secrets.toml からパスワードを取得
try:
    PASSWORD = st.secrets["auth"]["password"]
except KeyError:
    st.error("認証用のパスワードが secrets.toml に設定されていません。")
    st.stop()

# セッション状態で認証状態を管理
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 COUNTER（ログイン）")
    st.write("Streamlit Cloudの secrets に設定したパスワードを入力してください。")
    pw = st.text_input("パスワード", type="password")
    if pw:
        if pw == PASSWORD:
            st.session_state.authenticated = True
            st.rerun() # st.experimental_rerun() から st.rerun() に変更
        else:
            st.error("パスワードが違います")
    # 認証が完了するまで以降の処理を停止
    st.stop()

# ------------------------
# ✅ Googleスプレッドシート接続
# ------------------------
# st.cache_resource を使って接続をキャッシュし、パフォーマンスを向上
@st.cache_resource
def connect_to_google_sheet():
    """Googleスプレッドシートへの接続を確立する"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # secrets.toml の "gcp_service_account" セクションから認証情報を取得
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=scope
        )
        gc = gspread.authorize(credentials)
        return gc
    except Exception as e:
        st.error("Googleスプレッドシートへの認証に失敗しました。secrets.toml の設定を確認してください。")
        st.error(f"詳細エラー: {e}")
        # traceback.print_exc() # デバッグ時に詳細なエラーを確認したい場合
        return None

# st.cache_data を使ってデータの取得をキャッシュ
@st.cache_data(ttl=60) # 60秒間データをキャッシュ
def get_sheet_data(_worksheet):
    """ワークシートから全データを取得し、DataFrameに変換する"""
    data = _worksheet.get_all_records()
    return pd.DataFrame(data)


# 接続の実行
gc = connect_to_google_sheet()
if gc is None:
    st.stop() # 接続失敗時はアプリを停止

# スプレッドシートを開く
try:
    SPREADSHEET_NAME = "customer_counter"
    sh = gc.open(SPREADSHEET_NAME)
    worksheet = sh.sheet1
except gspread.exceptions.SpreadsheetNotFound:
    st.error(f"スプレッドシート '{SPREADSHEET_NAME}' が見つかりません。")
    st.info("指定した名前のスプレッドシートを作成し、サービスアカウントに共有してください。")
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
st.title("👥cust_count")
st.metric(label="現在の人数", value=f"{current_count} 人")

col1, col2 = st.columns(2)

def update_sheet(new_count):
    """スプレッドシートに新しいカウントを追記する"""
    # タイムゾーンを日本時間に設定
    from datetime import timezone, timedelta
    JST = timezone(timedelta(hours=+9))
    timestamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")

    try:
        worksheet.append_row([timestamp, new_count])
        # キャッシュをクリアしてデータを再読み込み
        st.cache_data.clear()
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

    # 日別の最終人数を取得
    daily_counts = data.groupby("日付")["人数"].last()
    st.bar_chart(daily_counts, use_container_width=True)

    st.subheader("時間帯ごとの人数変化")
    # デフォルトの日付を最新日に設定
    default_date = data["日付"].max()
    selected_date = st.date_input("日付を選択", value=default_date)

    if selected_date:
        hourly_counts = data[data["日付"] == selected_date].set_index("時刻")["人数"].resample("h").last().fillna(method='ffill')
        hourly_counts = hourly_counts.reindex(pd.date_range(start=selected_date, end=selected_date + pd.Timedelta(hours=23), freq='h'), fill_value=0)
        hourly_counts.index = hourly_counts.index.hour # インデックスを時間にする
        st.bar_chart(hourly_counts, use_container_width=True)

else:
    st.info("まだデータが記録されていません。")

