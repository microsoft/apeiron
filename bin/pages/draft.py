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

def draft():
    st.header('Draft Page (Internal)')  
    build_states: Dict[str, BuildState] = load_build_states()


def console():
    AU.side_status()

    with st.sidebar:
        st.divider()
        if st.button('Refresh Build States', use_container_width=True):
            build_states = load_build_states()
            st.success('Build states refreshed.')


    draft()

