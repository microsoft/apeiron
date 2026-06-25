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
from apeiron.system import build_system


current_dir = pathlib.Path(__file__).parent


# async def _getweather(city):
#   # declare the client. the measuring unit used defaults to the metric system (celcius, km/h, etc.)
#   async with python_weather.Client(unit=python_weather.IMPERIAL) as client:
#     weather = await client.get(city)
#     return weather.temperature
  

def distribution_to_pie(distribution: PersonaDistribution):
    """
    Convert a PersonaDistribution to a pie chart data format.
    """
    _data = []
    for persona in distribution._personas:
        _data.append(AU.PieObject(
            Category=persona.name,
            Caption=persona.description,
            Value=persona.ratio,
        ))
    pie_data = AU.PieData(data=_data)
    return AU.draw_pie(pie_data)

def demands_to_pie(demands):
    """
    Convert a list of demands to a pie chart data format.
    """
    _data = []
    for demand in demands:
        _data.append(AU.PieObject(
            Category=demand['task'],
            Caption=demand['description'],
            Value=demand['ratio'],
        ))
    pie_data = AU.PieData(data=_data)
    return AU.draw_pie(pie_data)




def helper():
    
    st.header('Building Helper')

    system = st.session_state.system 

    library = system.library

    with st.expander('Binded Libraries API Directory (See details in the Library page)', expanded=False):
        st.code(library.api_directory)
    
    personas = None
    create_personas_button = False
    create_demands_button = False
    build_button = False
    run_app_button = False
    stop_app_button = False
    builder_inputs = None

    col1, col2 = st.columns([1,2])
    with col1:
        _c1, _c2 = st.columns([1,2.2])
        with _c1:
            category = st.selectbox('Category', system.scenario_dict, index=0)
            scenarios = {i.name: i for i in system.scenario_dict[category]}
        with _c2:
            scenario = st.selectbox('Scenario', scenarios, index=0)
        scenario = scenarios[scenario]
        st.markdown(f'##### {scenario.name}') 
        st.caption(f'**Sub-category:** {scenario.category}')
        st.markdown(f'**Description:** {scenario.description}')
    with col2:
        if scenario.personas is None:
            st.warning('No persona distributions available for this scenario. Please call the builder to generate them.')
            create_personas_button = st.button('Create Personas')
            # TODO: call the builder to generate the personas
        else: 
            persona_distribution = {i.name:i for i in scenario.personas.distributions}
            _c1, _c2 = st.columns([2.2,3])
            with _c1:
                distribution = st.selectbox('Persona Distribution', persona_distribution, index=0)
                distribution = persona_distribution[distribution]
                description = distribution.description
                distribution_pie = distribution_to_pie(distribution)
                # st.markdown('### Persona Distribution Description')
                st.caption(f'**Description:** {description}')
                if distribution.demands_created:
                    builder_inputs = (scenario, distribution)
                    appspace_dir = system.ckpt.appspace_dir(scenario, distribution)
                    app_dir = U.pjoin(appspace_dir, 'app')
                    state_dir = U.pjoin(appspace_dir, 'state.json')
                    _built = U.pexists(state_dir)
                    U.mkdirs(app_dir)
                    _c11,_c12,_c13 = st.columns([1,1,1])
                    with _c11:
                        build_button = st.button('🚀 Build!', use_container_width=True, 
                                                 help=f'Build the app for the selected scenario and persona distribution.')
                    with _c12:
                        _help_text = f'App directory: {app_dir}'  if _built else 'App directory does not exist yet.'
                        if st.button('📂 Directory', use_container_width=True, help=_help_text, disabled=not _built):
                            # open the app directory in a your file explorer
                            if os.name == 'nt':  # Windows
                                os.startfile(app_dir)
                    with _c13:
                        _app_running = system.app_running(scenario, distribution)
                        if _app_running:
                            stop_app_button = st.button('🌑 Stop App', use_container_width=True)
                        else:
                            _help_text = f'Run app.' if _built else 'Please build first.'
                            run_app_button = st.button('🌕 Run App', use_container_width=True, disabled=not _built, help=_help_text)
            with _c2:
                st.altair_chart(distribution_pie)
            distribution_data = distribution.to_dict()
            distribution_data.pop('reasoning', None)  # Remove reasoning if it exists
            personas = distribution_data.pop('personas', None)  # Remove personas if it exists
            # demands = distribution_data.pop('demands', None)  # Remove demands if it exists
        
        
        # st.json(distribution_data)

    # col1, col2 = st.columns(2)
    # with col1:
    #     st.markdown('### Persona Distribution Pie Chart')
    #     st.altair_chart(distribution_pie)

    if scenario.personas is None:
        pass
    elif personas is None:
        st.warning('No personas available for this scenario. Please call the builder to generate them.')
    else:
        c1, c2 = st.columns([1,3])
        with c1:
            _personas = {i['name']: i for i in personas} if personas else {}
            persona = st.selectbox('Persona', _personas, index=0)
            persona = _personas[persona]
            st.caption(f'**Description:** {persona["description"]}')

        with c2:
            demands = persona['demands']['demands']

            if demands:
                demands_pie = demands_to_pie(demands)
                _c1, _c2 = st.columns([1.5,1])
                with _c1:
                    st.altair_chart(demands_pie)
                with _c2:
                    _demands = {i['task']: i for i in demands}
                    _demand = st.selectbox('Demand', _demands, index=0)
                    _demand = _demands[_demand]
                    st.markdown(f'**Description:** {_demand["description"]}')
                    st.caption(f'**Expected Outcome:** {_demand["expected_outcome"]}')
                    if 'rubric' in _demand:
                        st.caption(f'**Rubric:** {_demand["rubric"]}')
                builder_inputs = (scenario, distribution)
            else:
                st.warning('No demands available for this persona. Please call the builder to generate them.')
                create_demands_button = st.button('Create Demands')


    # st.divider()

    if create_personas_button:
        # Call the builder to generate the personas
        system.create_personas(scenario)
        st.success('Persona distributions created successfully! Please refresh the page to see the updated personas.')

    if create_demands_button:
        system.create_demands(scenario, distribution)
        st.success('Demands created successfully! Please refresh the page to see the updated demands.')

    if build_button:
        st.toast('Builder Agent will build app... Please check the console for output.', icon="🛰")
        force_rebuild = False #True # FIXME: force rebuild for testing
        system.build_app(*builder_inputs, force_rebuild=force_rebuild)

    if run_app_button:
        st.toast('Running app... Please check the console to check the running port.', icon="🌕")
        system.run_app(*builder_inputs)

    if stop_app_button:
        st.toast('Stopping app...', icon="🌑")
        system.stop_app(*builder_inputs)

    with st.expander('Running Applications', expanded=False, icon="📱"):
        st.dataframe(system.running_apps_df, use_container_width=True)


def statistics():
    """
    Placeholder for the statistics page.
    """
    st.header('Data Statistics')

    system = st.session_state.system 

    st.write("## Total number of scenario-personas pairs: ", len(system.app_pairs))

    category = st.selectbox('Select Category', list(system.scenario_dict.keys()), index=0)

    scenarios = system.scenario_dict[category]
    total_demands = 0
    total_distributions = 0
    empty = {
        'demands': [],
        'rubrics': [],
        'personas': []
    }
    _mdtext = ''
    for scenario in scenarios:
        if scenario.personas:
            _mdtext += f'- {scenario.name}: :green[**{len(scenario.personas.distributions)}**] persona distributions\n'
            # number of personas in each distribution
            for distribution in scenario.personas.distributions:
                if distribution.personas:
                    _mdtext += f'  - {distribution.name}: :green[**{len(distribution.personas)}**] personas\n'
                    # number of demands in each persona
                    _total_demands = 0
                    for persona in distribution.personas.values():
                        if persona.demands:
                                for demand in persona.demands.demands:
                                    try:
                                        assert demand.rubric is not None, "Demand rubric cannot be None"
                                        assert isinstance(demand.rubric, str), "Demand rubric must be a string"
                                        assert len(demand.rubric) > 0, "Demand rubric cannot be empty"
                                    except AssertionError as e:
                                        empty['rubrics'].append(f"{scenario.name}-{distribution.name}-{persona.name}-{demand.task}")
                                _mdtext += f'    - {persona.name}: :green[**{len(persona.demands.demands)}**] demands with rubrics\n'
                                _total_demands += len(persona.demands.demands)
                        else:
                            _mdtext += f'    - {persona.name}: :red[**0**] demands\n'
                            empty['demands'].append(f"{scenario.name}-{distribution.name}-{persona.name}")
                    _mdtext += f'    - **Total**: :blue[**{_total_demands}**] demands\n'
                    total_demands += _total_demands
                else:
                    _mdtext += f'  - {distribution.name}: :red[**0** personas]\n'
                    empty['personas'].append(f"{scenario.name}-{distribution.name}")
            total_distributions += len(scenario.personas.distributions)
        else:
            _mdtext += f'- {scenario.name}: :red[**0**] distributions\n'
            empty[scenario.name] = 'distributions'
    st.write(f'#### **Total**: :blue[**{total_demands}**] demands across :blue[**{total_distributions}**] distributions in :blue[**{len(scenarios)}**] scenarios for {category}.')
    check_txt = ''
    for k, v in empty.items():
        if len(v) == 0:
            check_txt += f'{len(v)} empty {k} found. '
    if any(len(v) > 0 for v in empty.values()):
        st.warning(f'⚠️ {check_txt}Please check the console for details.')
    else:
        st.success('✅ No empty demands, rubrics, or personas found.')
    st.markdown(_mdtext)




def build_helper():
    AU.side_status()

    with st.sidebar:
        st.divider()

        tab = st.selectbox("Select Tab", ['Build Helper', 'Data Statistics'])


    if tab == 'Build Helper':
        helper()
    elif tab == 'Data Statistics':
        statistics()







    # personas = st.selectbox('Persona', system.personas, index=0)