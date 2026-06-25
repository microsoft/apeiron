import streamlit as st
import sys,os
from datetime import datetime
import asyncio

import apeiron.utils as U
import bin.app_utils as AU
import json
import numpy as np

from apeiron.system import BasicSystem, BuildState
from apeiron.agent.prompts.cua import cua_conclude_parser, default_parser
import pandas as pd
from typing import Dict



@st.cache_data
def load_build_states():
    system = st.session_state.system
    pairs = [(system.get_app_pair(cat, scenario_id, personas_id)) for cat, scenario_id, personas_id in system.app_pairs]
    build_states = {}
    for scenario, personas in pairs:
        for cicd in range(len(system.experiment_configs['cicd_samples'])):
            try:
                tag = system.gen_tag(cicd)
                _name = f"{scenario.id}_{personas.id}_{tag}" if tag else f"{scenario.id}_{personas.id}"
                build_states[_name] = system.get_build_state(scenario, personas, tag)
            except Exception as e:
                # U.cprint(f"Error loading build state for {scenario.id}_{personas.id}: {e}", 'r')
                pass
    return build_states

# def app_gallery():
#     st.header('App Gallery')

#     system: BasicSystem = st.session_state.system
#     build_states: Dict[str,BuildState] = load_build_states()
#     exp_logs = system.monitor.read_logs()

#     apps = {}
#     for key,state in build_states.items():
#         if 'cicd' in key:
#             continue
#         for session in reversed(state.sorted_sessions):
#             if session.deliverable:
#                 apps[key] = state
#                 break

#     # st.write(f"App Directories ({len(app_dirs)}):")
#     for key, state in apps.items():
#         cols = st.columns([4,1,1])
#         scenario = state.scenario
#         personas = state.personas
#         with cols[0]:
#             st.write(f"**:blue[Scenario:] {scenario.name:<50} :red[>] :blue[Persona:] {personas.name}**")
#         with cols[1]:
#             _app_running = system.app_running(scenario, personas)
#             if _app_running:
#                 stop_app_button = st.button('🌑 Stop App', use_container_width=True, key = f'stop_{key}')
#             else:
#                 run_app_button = st.button('🌕 Run App', use_container_width=True, key = f'run_{key}')
#         with cols[2]:
#             download_app_button = st.button("🌐 Download", use_container_width=True, key = f'download_{key}')



def app_gallery():
    st.header('App Gallery')
    
    system: BasicSystem = st.session_state.system
    build_states: Dict[str,BuildState] = load_build_states()
    exp_logs = system.monitor.read_logs()

    apps = {}
    for key,state in build_states.items():
        if 'cicd' in key:
            continue
        for session in reversed(state.sorted_sessions):
            if session.deliverable:
                apps[key] = state
                break


    # --- 1. Add Search and Layout Controls ---
    search_query = st.text_input("Search Apps", placeholder="Search by name or persona...")
    
    # Filter apps based on search query
    if search_query:
        apps = {
            key: state for key, state in apps.items()
            if search_query.lower() in state.scenario.name.lower() or \
               search_query.lower() in state.personas.name.lower()
        }

    # --- 2. Create a Grid Layout ---
    cols = st.columns(3) # Create a 3-column grid. You can change this number.
    col_index = 0

    for key, state in apps.items():
        # Place each app card in the next available column
        with cols[col_index]:
            
            # --- 3. Use a Container as a "Card" ---
            with st.container(border=True):
                
                # --- 4. Improve Typography and Information Hierarchy ---
                st.subheader(state.scenario.name)
                st.caption(f"Persona: {state.personas.name}")
                desc = state.personas.description
                max_len = 120
                desc = desc if len(desc) <= max_len else desc[:max_len] + "..."
                st.markdown(desc)

                # --- 5. Use Columns for Buttons for a Cleaner Look ---
                b_cols = st.columns(3)
                running_url = None
                with b_cols[0]:
                    if system.app_running(state.scenario, state.personas):
                        _hash = U.hash_str(state.scenario.id + state.personas.id)
                        running_url = system.running_apps[_hash]['state'].running_url()
                        if st.button('Stop', type="primary", use_container_width=True, key=f'stop_{key}', icon="⏹️"):
                            system.stop_app(state.scenario, state.personas)
                    else:
                        if st.button('Launch App', use_container_width=True, key=f'run_{key}', icon="▶️"):
                            if not system.app_running(state.scenario, state.personas):
                                _state = asyncio.run(system.run_app(state.scenario, state.personas, use_venv=False))
                                # running_url = _state.running_url()
                
                with b_cols[1]:
                    if running_url:
                        st.link_button('Go to App', running_url, use_container_width=True, icon="🔗")
                    else:
                        st.link_button('Go to App', "http://localhost", use_container_width=True, icon="🔗", disabled=True)

                with b_cols[2]:
                    st.button("Download", use_container_width=True, key=f'download_{key}', icon="📥")

        # --- Logic to cycle through columns ---
        col_index = (col_index + 1) % len(cols)


def gallery():
    AU.side_status()

    with st.sidebar:
        st.divider()
        if st.button('Refresh Build States', use_container_width=True):
            build_states = load_build_states()
            st.success('Build states refreshed.')

    app_gallery()

