import streamlit as st
import utils as U



def tab1():
    st.header('Page 5 Tab 1')
    st.write("This is the content of Tab 1.")

def tab2():
    st.header('Page 5 Tab 2')
    st.write("This is the content of Tab 2.")


def page5():
    with st.sidebar:
        st.markdown('# Sidebar')
        st.write("Use the sidebar to navigate between tabs and provide high-level controls.")
        selected_tab = st.sidebar.selectbox(
            "Select a tab",
            ("Tab 1", "Tab 2")
        )

    if selected_tab == "Tab 1":
        tab1()
    elif selected_tab == "Tab 2":
        tab2()

