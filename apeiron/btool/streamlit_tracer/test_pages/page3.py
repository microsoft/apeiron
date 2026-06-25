import streamlit as st
import uuid


def page3():
    st.title("Page 3")
    st.write("This is the content of Page 3.")
    # Add more content or functionality as needed
    with st.expander("More Info"):
        st.write("This is additional information inside an expander.")
        st.text_input("Enter some text", key="text_input1")
        st.slider("Choose a number", 0, 100, 50, key="slider1")
        