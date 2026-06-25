import json
import time
import pathlib
import streamlit as st
import sys,os
from datetime import datetime
import asyncio
# import python_weather

import apeiron.utils as U
import bin.app_utils as AU

from apeiron.const import PersonaDistribution


sys.path.append('.')


current_dir = pathlib.Path(__file__).parent




def library():
    AU.side_status()

    st.header('Library Browser')

    system = st.session_state.system
    library = system.library

    col1, col2, col3 = st.columns([1,1.5,1])
    with col1:
        _proxies = {i._proxy_name: i for i in library.proxies.values()}
        _proxy = st.selectbox('Proxy', _proxies, index=0)
        proxy = _proxies[_proxy]
        st.markdown(f'**Path:** {proxy._proxy_path} ({len(proxy.registry)} APIs)')
        st.markdown(f'**Description:** {proxy._proxy_description}')
        if proxy.additional_docs:
            _additional_doc = st.selectbox('Additional Docs',proxy.additional_docs)
            with st.expander('Additional Documentation', expanded=False):
                additional_doc = proxy.additional_docs[_additional_doc]
                st.markdown(f'**{additional_doc}**')

    _data = []
    for cat in proxy.index:
        _num = sum(len(proxy.index[cat][i]) for i in proxy.index[cat])
        _data.append(AU.PieObject(
            Category=cat,
            Caption=f'{_num} APIs in this category: {cat}',
            Value=_num,
        ))
    pie_data = AU.PieData(data=_data)
    cats_pie = AU.draw_pie(pie_data)

    with col2:
        st.markdown('### Number of APIs by Category')
        st.altair_chart(cats_pie)

    with col3:
        # _c1, _c2, _c3 = st.columns([1,1,1])
        # with _c1:
        _category = st.selectbox('Category', proxy.index, index=0)
        category = proxy.index[_category]
    # with _c2:
        _subcategory = st.selectbox('Sub-category', category, index=0)
        subcategory = category[_subcategory]
    # with _c3:
        _api = st.selectbox('API', subcategory, index=0)
        api = proxy.registry[_api]

    st.subheader(api['name'] if api['name'] else _api)
    st.markdown(f'**Full Path:** {proxy._proxy_path}/{_api}')
    st.markdown(f'**Description:** {api["description"]}')
    st.markdown(f'**Doc string:** {api["doc_string"]}')
    st.markdown('#### Parameters')
    st.code(api['params'], language='python')
    st.markdown('#### Response')
    st.code(api['response'], language='python')

