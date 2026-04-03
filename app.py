import streamlit as st

st.set_page_config(
    page_title="Hisse Analizi",
    page_icon="📈",
    layout="wide",
)

pg = st.navigation([
    st.Page("pages/tr.py", title="TR", icon="🇹🇷"),
    st.Page("pages/usa.py", title="USA", icon="🇺🇸"),
])
pg.run()
