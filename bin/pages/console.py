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

# def exp_console():
#     st.header('Experiment Console')

#     system: BasicSystem = st.session_state.system
#     build_states = load_build_states()
#     exp_logs = system.monitor.read_logs()


#     all_status = []
#     current_logs = {}
#     for key, log in exp_logs.items():
#         if len(log) == 0:
#             continue
#         latest_log = log[-1]
#         status = latest_log['status']
#         if status == 'closed':
#             continue
#         latest_log['name'] = key
#         all_status.append(latest_log)
#         cur_log = []
#         for _log in log:
#             if _log['status'] == 'closed':
#                 cur_log = []
#             else:
#                 cur_log.append(_log)
#         current_logs[key] = cur_log

#     df = pd.DataFrame(all_status)
#     st.subheader('Active Workers')
#     if len(df) == 0:
#         st.info('No active workers found.')
#     else:
#         st.dataframe(df)

#     st.subheader('Experiment status')

#     chunk = st.selectbox('Select a chunk', options=system.ckpt.chunks)

#     chunk_states = {}
#     for cat, scenario_id, persona_id in system.ckpt.chunks[chunk]:
#         _state = build_states[f"{scenario_id}_{persona_id}"]
#         chunk_states[f"{scenario_id}_{persona_id}"] = _state
#         num_success = 0
#         n_deliverable = 0
#         for _session in _state.sessions:
#             if _session.status.value == 'succeeded':
#                 num_success += 1
#             if _session._deliverable:
#                 n_deliverable += 1
#         _title = f"Category: {cat}, Scenario: {scenario_id}, Personas: {persona_id}, :blue[(Opt: {_state.opt_step}, sessions: {len(_state.sessions)} ({num_success} succeeded, {n_deliverable} deliverable), feedbacks: {len(_state.feedbacks)})]"
#         _title = '✅' + _title if U.pexists(_state.traces_dir) else '❌' + _title
#         st.write(_title)


def exp_console():
    st.header('Experiment Console')
    
    system: BasicSystem = st.session_state.system
    build_states = load_build_states()
    exp_logs = system.monitor.read_logs()

    all_status = []
    current_logs = {}
    for key, log in exp_logs.items():
        if len(log) == 0:
            continue
        latest_log = log[-1]
        status = latest_log['status']
        if status == 'closed':
            continue
        latest_log['name'] = key
        all_status.append(latest_log)
        cur_log = []
        for _log in log:
            if _log['status'] == 'closed':
                cur_log = []
            else:
                cur_log.append(_log)
        current_logs[key] = cur_log

    df_workers = pd.DataFrame(all_status)

    # --- 1. Active Workers as Status Cards ---
    st.subheader('Active Workers')
    if df_workers.empty:
        st.info('No active workers found.')
    else:
        # # Define status colors for visual cues
        # status_colors = {
        #     "optimizing": "blue",
        #     "running": "green",
        #     "building": "orange",
        # }
        
        # # Create a grid of 2 columns
        # cols = st.columns(2)
        # col_index = 0
        # for index, worker in df_workers.iterrows():
        #     with cols[col_index]:
        #         with st.container(border=True):
        #             color = status_colors.get(worker['status'], "gray")
        #             st.markdown(f"**{worker['name']}**")
        #             st.markdown(f"Status: **:{color}[{worker['status'].capitalize()}]**")
        #             st.caption(f"Timestamp: {worker['timestamp']}")
        #             st.code(worker['note'], language=None)
        #     col_index = (col_index + 1) % 2 # Cycle through columns
        st.dataframe(df_workers)

    st.divider()

    # --- 2. Experiment Status as Expandable Sections with Metrics ---
    st.subheader('Experiment Status')
    chunk_key = st.selectbox('Select a chunk', options=system.ckpt.chunks)

    if chunk_key is not None:
        for cat, scenario_id, persona_id in system.ckpt.chunks[chunk_key]:
            state_key = f"{scenario_id}_{persona_id}"
            _state = build_states[state_key]

            # Calculate stats
            num_success = sum(1 for s in _state.sessions if s.status.value == 'succeeded')
            n_deliverable = sum(1 for s in _state.sessions if s._deliverable)

            # Use an expander for each experiment to reduce clutter
            title_emoji = '✅' if U.pexists(_state.traces_dir) else '❌'
            expander_title = f"{title_emoji} **{scenario_id} > {persona_id}** (Category: {cat})"

            with st.expander(expander_title, expanded = True):
                # Use columns to display key metrics
                metric_cols = st.columns(5)
                metric_cols[0].metric("Total Sessions", len(_state.sessions))
                metric_cols[1].metric("Succeeded", f"{num_success}", delta=f"{round(100*num_success/len(_state.sessions))}%")
                metric_cols[2].metric("Deliverables", n_deliverable)
                metric_cols[3].metric("Feedbacks", len(_state.feedbacks))
                metric_cols[4].metric("Opt Step", _state.opt_step)
                # st.caption(f"Persona: {persona_id}")




def console():
    AU.side_status()

    with st.sidebar:
        st.divider()
        if st.button('Refresh Build States', use_container_width=True):
            build_states = load_build_states()
            st.success('Build states refreshed.')

    exp_console()

