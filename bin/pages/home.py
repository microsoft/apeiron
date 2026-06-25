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

sys.path.append('.')


current_dir = pathlib.Path(__file__).parent
apeiron_jpg = U.pjoin(current_dir.parent, 'assets', 'apeiron.jpg')

# async def _getweather(city):
#   # declare the client. the measuring unit used defaults to the metric system (celcius, km/h, etc.)
#   async with python_weather.Client(unit=python_weather.IMPERIAL) as client:
#     weather = await client.get(city)
#     return weather.temperature
  

# def tabs():
#     st.subheader('Tabs')

#     tabs=st.tabs([
#         'Helper',
#         'Builder',
#         'Optimizer',
#         'CUA',
#         'Viewer',
#     ])

#     with tabs[0]:
#       st.markdown('''
# The Helper tab is about the builder helper that generate samples for experiments and the one who guide users to decide the specs when deployment.
# ''')
    
#     with tabs[1]:
#       st.markdown('''The Builder tab is for the builder agent that produces the actual application given the specifications through the optimization process.
# ''')
      
#     with tabs[2]:
#       st.markdown('''The Optimizer tab is for developing and visualizing the optimization process over widget trees.
# ''')
      
#     with tabs[3]:
#       st.markdown('''The CUA tab is for developing the Computer User Agents that make the tests.  
# ''')
      
#     with tabs[4]:
#       st.markdown('''The Viewer tab is the hub for visualizing the results of the Apeiron system.
# ''')
      


def howtouse():
    st.markdown('# Welcome to ♾️Apeiron')


    st.markdown(f'''
## How to use Apeiron

Apeiron is an 🔵 Amorphware (**Amorph**ous Soft**ware**) engine.
It is a framework that covering the entire software development lifecycle of generating the software applications in the domain.
''')

    st.markdown(f'''
## 🔵 Amorphware

Amorphware is another layer of abstraction on top of the existing software stack, which allows users to build applications that are not tied to any specific hardware or software platform. It is a new paradigm for software development that enables developers to create applications between the libraries and the applications, 
conceptually, its a "generative modeling" of the application universe of a domain determined by the libraries it binds to.
''')
    # centering
    _, col, _ = st.columns([1, 6, 1])
    with col:
        st.image(apeiron_jpg, use_container_width=True)


from apeiron.system import build_system, SystemBase
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@st.cache_resource()
def build(cfg_name,exp_name) -> SystemBase:
    config = U.load_config(
        U.pjoin(PROJECT_ROOT, 'configs', f'{cfg_name}.yaml'),
    )
    system = build_system(config,exp_name,stream=st)
    return system



def home():
    AU.side_status()

    with st.sidebar:
        system = st.session_state.system
        ckpt_dir = os.environ.get('CKPT_DIR')
        configs_dir = os.path.join(PROJECT_ROOT, 'configs')
        cols = st.columns([1,1])
        with cols[0]:
            cfgs = sorted([f.removesuffix('.yaml') for f in os.listdir(configs_dir) if f.endswith('.yaml')])
            cur_cfg = system.config['name']
            cfg_idx = cfgs.index(cur_cfg) if cur_cfg in cfgs else 0
            cfg_name = st.selectbox("Select Config", cfgs, index=cfg_idx)
        with cols[1]:
            cfg_ckpt_dir = U.pjoin(ckpt_dir, cfg_name)
            exps = sorted(os.listdir(cfg_ckpt_dir)) if os.path.isdir(cfg_ckpt_dir) else []
            cur_exp = system.exp_name
            exp_idx = exps.index(cur_exp) if cur_exp in exps else 0
            exp_name = st.selectbox("Select Experiment", exps, index=exp_idx) if exps else None
        rebuildable = exp_name is not None and (system.config['name'] != cfg_name or system.exp_name != exp_name)
        if st.button("Rebuild System", disabled=not rebuildable, use_container_width=True):
            st.session_state._cfg_name = cfg_name
            st.session_state._exp_name = exp_name
            st.cache_resource.clear()
            del st.session_state.system
            st.rerun()

    howtouse()
    # tabs()


