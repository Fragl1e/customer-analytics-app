import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.title("お客さん集計アプリ")

# データ保持（セッションごと）
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=["名前", "年齢", "性別", "購入金額"])

# 入力フォーム
with st.form("input_form"):
    name = st.text_input("名前")
    age = st.number_input("年齢", min_value=0, max_value=120, step=1)
    gender = st.selectbox("性別", ["男性", "女性", "その他"])
    amount = st.number_input("購入金額", min_value=0, step=100)
    submitted = st.form_submit_button("登録")

if submitted:
    new_data = pd.DataFrame([[name, age, gender, amount]], columns=["名前", "年齢", "性別", "購入金額"])
    st.session_state.data = pd.concat([st.session_state.data, new_data], ignore_index=True)
    st.success("データを登録しました！")

# データ一覧
st.subheader("登録データ一覧")
st.dataframe(st.session_state.data)

# 集計・統計
if not st.session_state.data.empty:
    st.subheader("統計情報")
    st.write(st.session_state.data.describe())

    st.subheader("性別ごとの購入平均")
    gender_avg = st.session_state.data.groupby("性別")["購入金額"].mean()
    st.bar_chart(gender_avg)
