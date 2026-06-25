import sys,os
sys.path.append('.')

import time
import pathlib
import streamlit as st
import apeiron.utils as U
import bin.app_utils as AU


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

custom_args = sys.argv[1:]

DEPLOY_MODE = 'deploy' in custom_args or '--deploy' in custom_args or '-d' in custom_args or 'd' in custom_args



current_dir = pathlib.Path(__file__).parent

bin_dir = U.pjoin(PROJECT_ROOT, 'bin')
logo, _ = AU.load_logo(bin_dir=bin_dir)

st.set_page_config(page_title="Apeiron",page_icon=logo,layout="wide")


import importlib
from streamlit_theme import st_theme

# from streamlit_navigation_bar import st_navbar



# Import the parent module first
if not DEPLOY_MODE:
    import bin.pages

    # Function to dynamically import and reload modules
    def import_and_reload(module_name):
        full_module_name = f'bin.pages.{module_name}'
        if full_module_name in sys.modules:
            return importlib.reload(sys.modules[full_module_name])
        return importlib.import_module(full_module_name)

    # Import and reload modules
    home = import_and_reload('home').home
    build_helper = import_and_reload('build').build_helper
    library = import_and_reload('library').library
    console = import_and_reload('console').console
    draft = import_and_reload('draft').draft
    gallery = import_and_reload('gallery').gallery
else:
    from bin.pages.home import home
    from bin.pages.build import build_helper
    from bin.pages.library import library
    from bin.pages.console import console
    from bin.pages.draft import draft
    from bin.pages.gallery import gallery
    


from apeiron.system import build_system, SystemBase



# Setup

@st.cache_resource()
def build(cfg_name,exp_name) -> SystemBase:
    config = U.load_config(
        U.pjoin(PROJECT_ROOT, 'configs', f'{cfg_name}.yaml'),
    )
    system = build_system(config,exp_name,stream=st)
    return system




if 'system' not in st.session_state:
    cfg_name = st.session_state.get('_cfg_name', 'default')
    _ckpt_cfg_dir = U.pjoin(os.environ.get('CKPT_DIR', U.pjoin(PROJECT_ROOT, 'ckpts')), cfg_name)
    _available_exps = sorted(os.listdir(_ckpt_cfg_dir)) if os.path.isdir(_ckpt_cfg_dir) else []
    exp_name = st.session_state.get('_exp_name', _available_exps[-1] if _available_exps else 'exp002')
    st.session_state.system = build(cfg_name, exp_name)

st.session_state.is_deploy = DEPLOY_MODE
st.session_state.current_theme = st_theme()
st.session_state.project_dir = PROJECT_ROOT



project_dir = current_dir.parent

styles = {
    "nav": {
        # "background-color": "royalblue",
        # "justify-content": "left",
    },
    "img": {
        "padding-right": "14px",
    },
    "span": {
        # "color": "white",
        "padding": "14px",
    },
    # "active": {
    #     "background-color": "white",
    #     "color": "var(--text-color)",
    #     "font-weight": "normal",
    #     "padding": "14px",
    # }
}

# pages = {
#     'Helper': helper,
#     'Builder': builder,
#     'Optimizer': optimizer,
#     'CUA': cua,
#     'Viewer': viewer,
# }

# titles=list(pages.keys())

# if not DEPLOY_MODE:
#     titles.append('Random')
#     pages['Random'] = random

# titles.append('DevOps')

# pg = st_navbar(
#     titles,
#     logo_path=logo_path,
#     styles=styles,
#     urls=urls
# )
# pages['Home'] = home

# if pg is None:
#     pg = 'Home'
    

# pages[pg]()



pages = [
    st.Page(home, title="Home", icon="♾️"),
    st.Page(build_helper, title="Build", icon="🌠"),
    st.Page(library, title="Library", icon="🌌"),
    st.Page(console, title="Console", icon="🖥️"),
    st.Page(gallery, title="Gallery", icon="🖼️"),
    st.Page(draft, title="Draft", icon="📝"),
]

pg = st.navigation(pages, position="top") # keep the position as "top"
pg.run()
