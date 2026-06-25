import streamlit as st
import utils as U
from pages import page1, page2, page3, page4



st.set_page_config(
    page_title="Streamlit App",
    layout="wide"
)
st.logo("assets/logo.svg")

pages = [
    st.Page(page1, title="Page 1"),
    st.Page(page2, title="Page 2"),
    st.Page(page3, title="Page 3"),
    st.Page(page4, title="Page 4"),
]

pg = st.navigation(pages, position="top") # keep the position as "top"
pg.run()
