import os
import streamlit as st

st.set_page_config(page_title="Streamlit App",layout="wide")

from streamlit_navigation_bar import st_navbar
from pages import page1, page2, page3, page4, page5
import utils as U




def home():
    st.markdown('# Welcome to Streamlit App')
    st.write("This is the home page of your Streamlit app. You can use this page to provide an overview or introduction to your application.")

    with st.sidebar:
        st.markdown('# Sidebar')
        st.write("Use the sidebar of home page to provide usage hints, high-level controls, etc.")


pages = {
    'Page 1': page1, # Rename these to match your actual page names
    'Page 2': page2,
    'Page 3': page3,
    'Page 4': page4,
    'Page 5': page5,
}

pg = st_navbar( # Use the navigation bar to switch between pages
    list(pages.keys()),
    logo_path=os.path.join('assets', 'logo.svg'), # DO NOT CHANGE OR REMOVE THIS LINE, it is the logo of the app and the entry point of the home page
)
pages['Home'] = home # the key of home page must be called 'Home' to be used as the default page

if pg is None:
    pg = 'Home'


pages[pg]()

