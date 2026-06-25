import uuid
import streamlit as st
import pandas as pd


from test_pages.page3 import page3
from test_pages.page4 import page4


st.set_page_config(
    page_title="Streamlit Test App",
    page_icon="🔵",
    layout="wide",
    initial_sidebar_state="expanded"
)


def nested_layout():
    with st.container(): 
        st.write("This is a nested layout inside a container.")
        cols = st.columns(2)
        cols[0].write("This is the left column.")
        with cols[1]:
            st.write("This is the right column.")
            st.button("Click Me", help="This button is inside a column.")
        st.button("Click Me", help="This is a button that you can click.", key=uuid.uuid4().hex[:6])
        st.checkbox("Check Me", help="This is a checkbox that you can check.")
        st.radio("Choose One", options=["Option 1", "Option 2"], help="This is a radio button group.")


def comp_group2():
    st.title("Component Group 2")
    st.write("This is a nested component group.")
    # Add more content or functionality as needed
    st.button("Click Me", help="This is another button that you can click.")
    st.checkbox("Check Me Too", help="This is a checkbox that you can check.")
    nested_layout()
    st.radio("Choose Another One", options=["Option A", "Option B"], help="This is another radio button group.")


def comp_group():
    st.title("Component Group")
    st.write("This is a group of components that can be reused across pages.")
    # Add more content or functionality as needed
    st.button("Click Me", help="This is a button that you can click.")
    st.checkbox("Check Me", help="This is a checkbox that you can check.")
    st.radio("Choose One", options=["Option 1", "Option 2"], help="This is a radio button group.")
    comp_group2()
    st.write("This is a nested component group.")


def page1():
    st.title("Page 1")
    st.write("This is the content of Page 1.")
    # Add more content or functionality as needed
    st.button("Click Me", key="button1", help="This is a button that you can click.")
    st.checkbox("Check Me", key="checkbox1")
    st.radio("Choose One", options=["Option 1", "Option 2"], key="radio1")
    
    data_df = pd.DataFrame(
        {
            "price": [20, 950, 250, 500],
        }
    )
    
    with st.popover("This is a badge to highlight important information."):
        st.write("This is a badge to highlight important information.")
        st.data_editor(
            data_df,
            column_config={
                "price": st.column_config.NumberColumn(
                    "Price (in USD)",
                    help="The price of the product in USD",
                    min_value=0,
                    max_value=1000,
                    step=1,
                    format="$%d",
                )
            },
            hide_index=True,
        )


def page2():
    st.title("Page 2")
    st.write("This is the content of Page 2.")
    # Add more content or functionality as needed
    comp_group()



with st.sidebar:
    st.header("Hello, Streamlit!")
    st.write("Use the side bar to provide additional global or page-wise hints.")
    st.button("Click Me", help="This is a button that you can click in the sidebar.")


pages = {
    "Your account": [
        st.Page(page1, title="Create your account"),
        st.Page(page2, title="Manage your account"),
    ],
    "Resources": [
        st.Page(page3, title="Learn about us"),
        st.Page(page4, title="Try it out"),
    ],
}

st.title("Streamlit Navigation Example")

# with st.popover("This is a badge to highlight important information."):
pg = st.navigation(pages, position="top") # keep the position as "top", leave the sidebar for high-level controls or hints
pg.run()



