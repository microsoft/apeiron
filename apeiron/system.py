from concurrent.futures import ThreadPoolExecutor
import random
import numpy as np
from sllm.llm import Dialog
from apeiron.library.re import Library
from apeiron.agent.aw import build_agent, AgentType, PrintSystem, BuildState, is_builder_agent, BuilderBase, BuildHelper, CUA, Feedback
import apeiron.utils as U
import psutil
from typing import List, Dict, Any, Tuple
import os
import uuid
import shutil
import traceback
import asyncio
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import time
from apeiron.const import DemandLists, Demand, Frameworks, Scenario, ScenarioList, ScenarioLists, PersonaDistribution, PersonaDistributions, Persona, Demand
from sllm.tools.cua import CUASession
import json
import functools as ft

U.load_dotenv()


_CICD_TAG = 'cicd'


@dataclass
class Ckpt:
    '''
    - state.json # state of the checkpoint, such as whether it is tested, etc.
    - config.json # metadata of the checkpoint, such as category setup, for backup
    - Category 1
      - metadata.json # scenario, category, etc.
      - Scenario 1
        - metadata.json # scenario, category, etc.
        - personas
            - persona distribution 1 # one scenario-persona pair, one program
                    - state.json # state of the experiments, such as whether it is built, etc.
                    - appspace # a separate environment for building the application
                        - app # the application built for this scenario-persona pair
                        - dialogs and other files
                        - state.json # the state of the application, such as whether it is built, etc.
                    - appspace_cicd_1
                    ...
                - ...
            - persona distribution 2
    ...
    '''
    ckpt_dir: str
    scenarios: ScenarioLists = None

    def __post_init__(self):  
        self.load_scenarios()

    def save_state(self, state: Dict[str, Any]):
        U.save_json(U.pjoin(self.ckpt_dir, 'state.json'), state)
    
    def load_state(self) -> Dict[str, Any]:
        return U.load_json(U.pjoin(self.ckpt_dir, 'state.json'))

    @property
    def state(self) -> Dict[str, Any]:
        return self.load_state()

    @property
    def scenarios_created(self) -> bool:
        state = self.load_state()
        return 'version' in state and 'note' in state
    
    def persona_created(self, scenario: Scenario) -> bool:
        personas_dir = U.pjoin(self.scenario_dir(scenario), 'personas')
        return U.pexists(personas_dir) and U.pexists(U.pjoin(personas_dir, 'state.json'))
    
    def demands_created(self, persona_distribution: PersonaDistribution) -> bool:
        return persona_distribution.demands_set

    def new_scenarios(self, scenario_lists: ScenarioLists, dialog: Dialog = None):
        U.clean_and_backup(self.ckpt_dir)
        for scenario_list in scenario_lists.scenario_lists:
            top_category = scenario_list.category
            category_dir = U.pjoin(self.ckpt_dir, top_category)
            U.mkdirs(category_dir)
            U.save_json(U.pjoin(category_dir, 'metadata.json'), {
                'reasoning': scenario_list.reasoning,
                'category': top_category,
            })
            for scenario in scenario_list.scenarios:
                scenario_dir = U.pjoin(category_dir, scenario.id)
                U.mkdirs(scenario_dir)
                U.save_json(U.pjoin(scenario_dir, 'scenario.json'), {
                    'name': scenario.name,
                    'description': scenario.description,
                    'category': scenario.category,
                })
        state = self.load_state()
        state['version'] = scenario_lists.version
        state['note'] = scenario_lists.note
        self.save_state(state)
        self.scenarios = scenario_lists
        if dialog is not None:
            U.save_json(U.pjoin(self.ckpt_dir, 'dialog.json'), dialog.to_dict())

    def new_personas(self, scenario: Scenario, persona_distributions: PersonaDistributions, dialog: Dialog = None):
        personas_dir = U.pjoin(self.scenario_dir(scenario), 'personas')
        U.mkdirs(personas_dir)
        U.clean_and_backup(personas_dir)
        U.save_json(U.pjoin(personas_dir, 'state.json'), {'reasoning': persona_distributions.reasoning})
        if dialog is not None:
            U.save_json(U.pjoin(personas_dir, 'dialog.json'), dialog.to_dict())
        for distribution in persona_distributions.distributions:
            distribution_dir = U.pjoin(personas_dir, distribution.id)
            U.mkdirs(distribution_dir)
            U.save_json(U.pjoin(distribution_dir, 'distribution.json'), distribution.to_dict())
        scenario.personas = persona_distributions

    def new_demands(self, scenario: Scenario, persona_distribution: PersonaDistribution, demands: DemandLists, dialog: Dialog = None):
        distribution_dir = U.pjoin(self.scenario_dir(scenario), 'personas', persona_distribution.id)
        U.mkdirs(distribution_dir)  # ensure dir exists (don't assume new_personas ran first)
        persona_distribution.set_demands(demands)
        U.save_json(U.pjoin(distribution_dir, 'distribution.json'), persona_distribution.to_dict())
        if dialog is not None:
            U.save_json(U.pjoin(distribution_dir, 'dialog.json'), dialog.to_dict())

    def load_scenarios(self) -> ScenarioLists:
        """
        Load scenarios from the checkpoint directory.
        """
        scenario_lists = []
        state_file = U.pjoin(self.ckpt_dir, 'state.json')
        if not os.path.exists(state_file):  
            return None
        state = U.load_json(state_file)
        for category in os.listdir(self.ckpt_dir):
            category_dir = U.pjoin(self.ckpt_dir, category)
            if not os.path.isdir(category_dir) or category == '.backups':
                continue
            metadata_file = U.pjoin(category_dir, 'metadata.json')
            if not U.pexists(metadata_file):
                continue
            category_metadata = U.load_json(metadata_file)
            scenarios = []
            for scenario in os.listdir(category_dir):
                scenario_dir = U.pjoin(category_dir, scenario)
                if not os.path.isdir(scenario_dir):
                    continue
                scenario_file = U.pjoin(scenario_dir, 'scenario.json')
                if not os.path.exists(scenario_file):
                    continue
                scenarios.append(U.load_json(scenario_file))
            scenario_list = ScenarioList.from_list(category_metadata['category'], scenarios, reasoning=category_metadata['reasoning'])
            for scenario in scenario_list.scenarios:
                self.load_personas(scenario)
            scenario_lists.append(scenario_list)

        self.scenarios = ScenarioLists(scenario_lists=scenario_lists, version=state['version'], note=state['note'])
        chunks_dir = U.pjoin(self.ckpt_dir, 'chunks.json')
        if U.pexists(chunks_dir):
            self.chunks = {int(i): chunk for i, chunk in U.load_json(chunks_dir).items()}
        else:
            U.cprint('No chunks found, skipping chunk loading.','r')
            self.chunks = None
        return self.scenarios
    
    def load_personas(self, scenario: Scenario) -> PersonaDistributions:
        """
        Load personas for the given scenario from the checkpoint directory.
        """
        personas_dir = U.pjoin(self.scenario_dir(scenario), 'personas')
        state_file = U.pjoin(personas_dir, 'state.json')
        if not U.pexists(state_file):  
            return None
        state = U.load_json(state_file)

        persona_distributions = []
        for distribution in os.listdir(personas_dir):
            if distribution == '.backups':
                continue
            distribution_dir = U.pjoin(personas_dir, distribution)
            if not os.path.isdir(distribution_dir):
                continue
            distribution_file = U.pjoin(distribution_dir, 'distribution.json')
            if not os.path.exists(distribution_file):
                U.cprint(f"Distribution file {distribution_file} does not exist, skipping.", 'r')
                continue
            persona_distribution = PersonaDistribution.from_dict(U.load_json(distribution_file))
            persona_distributions.append(persona_distribution)

        persona_distributions = PersonaDistributions(distributions=persona_distributions, reasoning=state['reasoning'])
        scenario.personas = persona_distributions
        return persona_distributions

    def scenario_dir(self, scenario: Scenario) -> str:
        """
        Find the path to the checkpoint for the given scenario and persona.
        """
        top_category = scenario.parent_category
        return U.pjoin(self.ckpt_dir, top_category, scenario.id)
    
    def pair_dir(self, scenario: Scenario, personas: PersonaDistribution) -> str:
        return U.pjoin(self.scenario_dir(scenario), 'personas', personas.id)

    def appspace_dir(self, scenario: Scenario, personas: PersonaDistribution, tag: str = '') -> str:
        """
        Find the path to the application for the given scenario and persona distribution.
        """
        _appspace = f'appspace_{tag}' if tag else 'appspace'
        return U.pjoin(self.pair_dir(scenario, personas), _appspace)

    @classmethod
    def from_dir(cls, ckpt_dir: str) -> 'Ckpt':
        """
        Load a checkpoint from the given directory.
        """
        return cls(ckpt_dir=ckpt_dir)



@dataclass
class ExpMonitor:
    """
    Set up temporary directories for monitoring experiments.
    .exp_monitor 
    ├── state_tracker.json
    ├── <monitor_dir>
    │   ├── <exp_name>
    """
    monitor_dir: str

    def log_state(self, scenario: Scenario, personas: PersonaDistribution, status: str, note: str = ''):
        key = f"{scenario.id}_{personas.id}"
        save_dir = U.pjoin(self.monitor_dir, key)
        U.mkdirs(save_dir, exist_ok=True)
        state_tracker_file = U.pjoin(save_dir, 'state_tracker.jsonl')
        # U.save_json(state_tracker_file, {"status": status, "scenario": scenario.id, "personas": personas.id, "timestamp": U.dt_now_str()})
        with open(state_tracker_file, 'a') as f:
            f.write(f'{{"status": "{status}", "timestamp": "{U.dt_now_str()}", "note": "{note}"}}\n')

    def new_build(self, scenario: Scenario, personas: PersonaDistribution):
        self.log_state(scenario, personas, status='running')

    def close_build(self, scenario: Scenario, personas: PersonaDistribution, status: str = 'closed'):
        self.log_state(scenario, personas, status=status)

    def read_logs(self):
        logs = {}
        for folder in os.listdir(self.monitor_dir):
            folder_path = U.pjoin(self.monitor_dir, folder)
            if not os.path.isdir(folder_path):
                continue
            state_tracker_file = U.pjoin(folder_path, 'state_tracker.jsonl')
            if not os.path.exists(state_tracker_file):
                continue
            with open(state_tracker_file, 'r') as f:
                logs[folder] = [json.loads(line) for line in f.readlines()]
        return logs
            

class SystemBase:
    """
    Apeiron Amorphware System Base
    
     - Library: the library binded
     - Agent: Agent to solve the task
    """
    def __init__(self, config, exp_name=None, stream=None):
        if exp_name is None:
            exp_name = U.dt_now_str() + '_' + U.random_str(6)
        # Coerce a missing/invalid stream (e.g. None or a bool from headless callers)
        # to PrintSystem so agent UI calls (st.expander/status/markdown) no-op safely.
        if stream is None or not hasattr(stream, 'expander'):
            stream = PrintSystem()
        # set log dir to pass to agent
        self.config = config
        self.optimizer_configs = config['optimizer_configs']
        self.experiment_configs = config['experiment_configs']
        self.builder_configs = config['builder_configs']
        self.set_path(exp_name)
        self.library = Library(config['bind_libraries'])
        self.framework = Frameworks(self.builder_configs['framework'])
        self.setup_builder_cfg()
        self.builder: BuilderBase = build_agent(config, self.ckpt_dir, stream, AgentType.BUILDER)
        self.helper: BuildHelper = build_agent(config, self.ckpt_dir, stream, AgentType.HELPER)
        self.cua: CUA = build_agent(config, self.ckpt_dir, stream, AgentType.CUA)
        self._set_exp_name(exp_name)
        self.exp_name = exp_name
        self.set_st(stream)
        if not U.pexists(self.ckpt_dir) or len(os.listdir(self.ckpt_dir)) == 0:
            dataset = self.config.get('dataset', 'NULL')
            data_dir = U.pjoin(os.getenv('DATA_DIR'), dataset)
            if U.pexists(data_dir):
                U.cprint(f"Checkpoint directory {self.ckpt_dir} does not exist, copying from dataset {data_dir}...", 'y')
                shutil.copytree(data_dir, self.ckpt_dir, dirs_exist_ok=True)
            else:
                U.cprint(f"Checkpoint directory {self.ckpt_dir} and dataset {data_dir} does not exist, initializing new checkpoint...", 'y')
        self.ckpt = Ckpt.from_dir(self.ckpt_dir)
        self.running_apps = {}  # to keep track of running applications
        self.monitor = ExpMonitor(self.monitor_dir)

        self.port_queue = asyncio.Queue()
        # Pre-populate the queue with a range of ports
        available_ports = U.get_available_ports()
        random.shuffle(available_ports)
        for port in available_ports:
            self.port_queue.put_nowait(port)

    def setup_builder_cfg(self):
        if self.framework == Frameworks.REFLEX:
            self.config['agent_configs']['builder']['system_prompt_path'] = 'builder/reflex_builder_system'
        elif self.framework == Frameworks.STREAMLIT:
            self.config['agent_configs']['builder']['system_prompt_path'] = 'builder/streamlit_builder_system'

    @property
    def scenario_dict(self) -> Dict[str, Scenario]:
        if self.ckpt.scenarios is None:
            return {}
        return self.ckpt.scenarios.scenarios
    
    @property
    def app_pairs(self) -> List[Tuple[str, str, str]]:
        """
        Get all application pairs (category, scenario_id, personas_id) from the checkpoint.
        """
        app_pairs = []
        for category, scenarios in self.scenario_dict.items():
            for scenario in scenarios:
                if scenario.personas is None:
                    continue
                for personas in scenario.personas.distributions:
                    app_pairs.append((category, scenario.id, personas.id))
        return app_pairs
    
    def get_app_pair(self, category: str, scenario_id: str, personas_id: str) -> Tuple[Scenario, PersonaDistribution]:
        """
        Get the application pair (scenario, personas) for the given category, scenario_id, and personas_id.
        """
        if category not in self.scenario_dict:
            raise ValueError(f"Category {category} not found in scenario_dict.")
        scenarios = self.scenario_dict[category]
        if scenario_id not in [s.id for s in scenarios]:
            raise ValueError(f"Scenario {scenario_id} not found in category {category}.")
        scenario: Scenario = next(s for s in scenarios if s.id == scenario_id)
        if scenario.personas is None:
            raise ValueError(f"No personas found for scenario {scenario.id}.")
        personas = next((p for p in scenario.personas.distributions if p.id == personas_id), None)
        if personas is None:
            raise ValueError(f"Personas {personas_id} not found for scenario {scenario.id}.")
        return scenario, personas

    
    def set_st(self, stream):
        """
        Set the stream for the system.
        """
        self.st = stream
        self.builder.st = stream
        self.helper.st = stream

    def unset_st(self):
        """
        Unset the stream for the system.
        """
        self.st = None
        self.builder.st = None
        self.helper.st = None
    
    def set_path(self, exp_name: str):
        self.ckpt_dir = U.pjoin(os.getenv('CKPT_DIR'), self.config['name'], exp_name)
        self.config['log_dir'] = U.pjoin(os.getenv('LOG_DIR'), self.config['name'], exp_name)
        U.mkdirs(self.ckpt_dir)

    def _set_exp_name(self, exp_name: str):
        self.exp_name = exp_name
        self.set_path(exp_name)
        self.builder.ckpt_dir = self.ckpt_dir
        self.helper.ckpt_dir = self.ckpt_dir

    def rebuild(self, agent_type: AgentType | str, exp_name: str = None):
        if isinstance(agent_type, str):
            agent_type = AgentType(agent_type)
        if exp_name is not None:
            self._set_exp_name(exp_name)
        self.builder = build_agent(self.config, self.ckpt_dir, self.st, agent_type)

    def clone_builder(self): # for safe multi-threading
        return build_agent(self.config, self.ckpt_dir, self.st, self.builder.agent_type)
    
    def clone_helper(self): # for safe multi-threading
        return build_agent(self.config, self.ckpt_dir, self.st, AgentType.HELPER)
    
    def create_scenarios(self, categories: Dict[str, int] = None, version: str = '1.0', note: str = '', return_dialog = True, force_recreate=False) -> ScenarioLists:
        """
        Create scenarios based on the provided categories.
        """
        if self.ckpt.scenarios_created and not force_recreate:
            U.cprint(f"Scenarios already created in {self.ckpt_dir}, skipping...", 'g')
            return
        scenario_lists, dialog = self.helper.synthesize_scenarios(self.library, categories, version, note)
        self.ckpt.new_scenarios(scenario_lists, dialog)
        return (scenario_lists, dialog) if return_dialog else scenario_lists

    def create_personas(self, scenario: Scenario, return_dialog = True, force_recreate=False) -> PersonaDistributions:
        """
        Create personas for the given scenario.
        """
        if self.ckpt.persona_created(scenario) and not force_recreate:
            U.cprint(f"Personas already created for scenario {scenario.id}, skipping...", 'g')
            return scenario.personas

        persona_distributions, dialog = self.helper.synthesize_personas(scenario)
        self.ckpt.new_personas(scenario, persona_distributions, dialog)
        return (persona_distributions, dialog) if return_dialog else persona_distributions
    
    def create_demands(self, scenario: Scenario, persona_distribution: PersonaDistribution, return_dialog = True, force_recreate=False) -> DemandLists:
        """
        Create demands for the given scenario and persona distribution.
        """
        if self.ckpt.demands_created(persona_distribution) and not force_recreate:
            U.cprint(f"Demands already created for persona distribution {persona_distribution.id} in scenario {scenario.id}, skipping...", 'g')
            return persona_distribution.demands
        
        demands, dialog = self.helper.synthesize_demands(scenario, persona_distribution)
        self.ckpt.new_demands(scenario, persona_distribution, demands, dialog)
        return (demands, dialog) if return_dialog else demands

    async def create_dataset(self, name, categories: Dict[str, int] = None, description: str = '', version: str = '1.0', force_recreate=False, max_workers: int = 20, launch_interval: float = 0.1, K: int = 10):
        save_dir = U.pjoin(os.environ['DATA_DIR'], name)
        if U.pexists(save_dir) and not force_recreate:
            U.cprint(f"Dataset {name} already exists in {save_dir}, skipping creation...", 'g')
            return
        
        self.create_scenarios(categories, version=version, note=description, force_recreate=force_recreate)

        scenarios = []
        for cat, _s in self.scenario_dict.items():
            scenarios.extend(_s)
        U.cprint(f"Creating personas for {len(scenarios)} scenarios...", 'y')
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            loop = asyncio.get_event_loop()
            tasks = [loop.run_in_executor(executor, self.create_personas, scenario, False, force_recreate) for scenario in scenarios]
            await asyncio.sleep(launch_interval)  # Ensure tasks are launched with a delay
        await asyncio.gather(*tasks)
        U.cprint(f"Created personas for {len(scenarios)} scenarios.", 'g')

        pairs = []
        for cat, scenarios in self.scenario_dict.items():
            for scenario in scenarios:
                assert scenario.personas is not None, f"Scenario {scenario.name} in category {cat} has no personas."
                for personas in scenario.personas.distributions:
                    pairs.append((scenario, personas))
        U.cprint(f"Creating demands for {len(pairs)} pairs...", 'y')
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            loop = asyncio.get_event_loop()
            tasks = [loop.run_in_executor(executor, self.create_demands, scenario, personas, False, force_recreate) for scenario, personas in pairs]
            await asyncio.sleep(launch_interval)  # Ensure tasks are launched with a delay
        await asyncio.gather(*tasks)
        U.cprint(f"Created demands for {len(pairs)} pairs.", 'g')

        metadata = {
            'version': version,
            'description': description,
        }
        U.mkdirs(save_dir)
        shutil.copytree(self.ckpt_dir, save_dir, dirs_exist_ok=True)
        U.save_json(U.pjoin(save_dir, 'metadata.json'), metadata)

        # Chunk the dataset into K chunks
        pairs_by_cat = {}
        for cat, scenario, persona in pairs:
            if cat not in pairs_by_cat:
                pairs_by_cat[cat] = []
            pairs_by_cat[cat].append((scenario, persona))

        random.seed(42)
        N_chunks = len(pairs) // (len(pairs_by_cat)*K)
        N = N_chunks -1
        chunks = {}
        for cat in pairs_by_cat:
            pairs = pairs_by_cat[cat]
            random.shuffle(pairs)
            for i in range(N):
                if i not in chunks:
                    chunks[i] = []
                chunks[i] += [(cat, s, p ) for s, p in pairs[i*K:(i+1)*K]]
            if N not in chunks:
                chunks[N] = []
            chunks[N] += [(cat, s, p ) for s, p in pairs[N*K:]]  # Remaining pairs go to chunk N

        U.save_json(U.pjoin(save_dir, 'chunks.json'),chunks)



    """    Core Build Functions     """

    def load_feedbacks(self, scenario: Scenario, personas: PersonaDistribution, tag: str = '') -> List[Feedback]:
        feedbacks_dir = U.pjoin(self.ckpt.appspace_dir(scenario, personas, tag), 'feedbacks')
        if not U.pexists(feedbacks_dir):
            U.cprint(f"No feedbacks found in {feedbacks_dir}, returning empty list.", 'y')
            return []
        feedback_files = os.listdir(feedbacks_dir)
        # sort by i.e., feedback_i.json
        feedback_files.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]))
        feedbacks = []
        for feedback_file in feedback_files:
            feedback_file = U.pjoin(feedbacks_dir, feedback_file)
            feedback = Feedback.from_dict(U.load_json(feedback_file))
            feedbacks.append(feedback)
        return feedbacks

    def get_build_state(self, scenario: Scenario, personas: PersonaDistribution, tag: str = '') -> BuildState:
        appspace_dir = self.ckpt.appspace_dir(scenario, personas, tag)
        U.mkdirs(appspace_dir)
        feedbacks = self.load_feedbacks(scenario, personas, tag)
        state = BuildState(
            scenario=scenario,
            personas=personas,
            appspace_dir=appspace_dir,
            bind_libraries=self.config['bind_libraries'],
            framework=self.framework,
            feedbacks=feedbacks,
        )
        state.load_sessions(self.builder._log_base)  # load the sessions from the session directory
        return state


    def get_schedule(self, state: BuildState) -> Dict[int, Any]:
        scenario, personas = state.scenario, state.personas
        schedule_dir = U.pjoin(self.ckpt.pair_dir(scenario, personas), 'schedule.json')
        if not U.pexists(schedule_dir):
            U.cprint(f"Creating schedule for scenario {scenario.id} and personas {personas.id}...", 'y')
            init_samples = self.experiment_configs['init_samples']
            cicd_samples = self.experiment_configs['cicd_samples']
            schedule = state.schedule_task_cicd(init_samples, cicd_samples, self.config['random_seed'])
            U.save_json(schedule_dir, schedule)
        else:
            # U.cprint(f"Schedule already exists for scenario {scenario.id} and personas {personas.id}, loading...", 'y')
            schedule = {int(k): v for k, v in U.load_json(schedule_dir).items()}
        return schedule

    def init_build(self, scenario: Scenario, personas: PersonaDistribution, force_rebuild=False, cicd_step: int = 0) -> BuildState:
        tag = self.gen_tag(cicd_step)
        appspace_dir = self.ckpt.appspace_dir(scenario, personas, tag)
        app_dir = U.pjoin(appspace_dir, 'app')
        state_dir = U.pjoin(appspace_dir, 'state.json')
        if U.pexists(state_dir) and force_rebuild: # be careful, this will reset the appspace
            U.cprint(f"Force rebuilding: App already exists in {app_dir}, moving things to backup and rebuilding...", 'y')
            U.clean_and_backup(appspace_dir) # reset the appspace
        if cicd_step > 0 and not U.pexists(app_dir):
            U.cprint(f"Copying previous app for CICD step {cicd_step}...", 'y')
            tag_prev = self.gen_tag(cicd_step - 1)
            appspace_dir_prev = self.ckpt.appspace_dir(scenario, personas, tag_prev)
            app_prev_dir = U.pjoin(appspace_dir_prev, 'app')
            shutil.copytree(app_prev_dir, app_dir, dirs_exist_ok=True) if U.pexists(app_prev_dir) else None
        U.cprint(f"Initializing build state for scenario {scenario.id} and personas {personas.id}...", 'y')
        if not personas.demands_set:
            U.cprint(f"Creating demands for scenario {scenario.id} and personas {personas.id}...", 'y')
            self.create_demands(scenario, personas) 
        state = self.get_build_state(scenario, personas, tag)
        schedule = self.get_schedule(state)
        return state, schedule

    def gen_tag(self, cicd_step: int = 0) -> str:
        """
        Generate a tag for the build, used for CICD steps.
        """
        if cicd_step > 0:
            return f"{_CICD_TAG}_{cicd_step}"
        return ''

    async def build_app(self, builder_state: BuildState, training_pairs: list = None, old_pairs: list = None, log_fn = None)  -> BuildState:
        return await self.builder.build(builder_state, self.library, training_pairs=training_pairs, old_pairs=old_pairs, log_fn=log_fn)

    async def optimize_app(self, build_state: BuildState, training_pairs: list = None, old_pairs: list = None, log_fn = None) -> BuildState:
        return await self.builder.optimize(build_state, self.library, training_pairs=training_pairs, old_pairs=old_pairs, log_fn=log_fn)

    def ensure_personas(self, category: str = None):
        unfinished_scenarios = []
        if category is not None:
            all_scenarios = self.scenario_dict.get(category, [])
        else:
            all_scenarios = self.scenario_dict.values()
        for s in all_scenarios:
            unfinished_scenarios.extend([i for i in s if i.personas is None])
        print(f'Found {len(unfinished_scenarios)} scenarios without personas.')
        for scenario in unfinished_scenarios:
            U.cprint(f"Creating personas for scenario {scenario.id}...", 'y')
            self.create_personas(scenario)

    def app_running(self, scenario: Scenario, personas: PersonaDistribution) -> bool:
        _hash = U.hash_str(scenario.id + personas.id)
        return _hash in self.running_apps and self.running_apps[_hash]['pid'] is not None

    async def run_app(self, scenario: Scenario, personas: PersonaDistribution, tag: str = '', **kwargs) -> BuildState:
        """
        Run the application for the given scenario and persona distribution.
        """
        _hash = U.hash_str(scenario.id + personas.id + tag)
        if _hash in self.running_apps:
            return self.running_apps[_hash]['state']
        build_state = self.get_build_state(scenario, personas, tag=tag)
        pid, output_handle = await build_state.run_app(**kwargs)
        if psutil.pid_exists(pid):
            self.running_apps[_hash] = {
                'scenario': scenario,
                'personas': personas,
                'pid': pid,
                'appspace_dir': build_state.appspace_dir,
                'state': build_state,
                'output_handle': output_handle
            }
        else:
            U.cprint(f"Failed to start application for scenario {scenario.id} and personas {personas.id}, process with PID {pid} does not exist.", 'r')
            raise RuntimeError(f"Failed to start application for scenario {scenario.id} and personas {personas.id}, process with PID {pid} does not exist.")
        return build_state

    async def build(self, scenario: Scenario, personas: PersonaDistribution, force_rebuild: bool = False, cicd_step: int = 0, cua_semaphore = None) -> BuildState:
        # the basic loop, [build_app -> test_app -> determine] x N
        _locality_control = self.config['optimizer_configs']['locality_control']
        build_state, schedule = self.init_build(scenario, personas, force_rebuild=force_rebuild, cicd_step=cicd_step)
        _task_pairs = schedule[cicd_step]
        task_pairs = _task_pairs['new_tasks'] + _task_pairs['old_tasks']
        if self.optimizer_configs['do_split']:
            splits = self.optimizer_configs['splits']
            task_slices = build_state.slice_task_pairs(task_pairs, splits['train'], splits['test'], splits['dev'], random_seed=self.config['random_seed'])
            training_set = task_slices['train']
        else:
            training_set = task_pairs
        batch_size = self.optimizer_configs['batch_size']
        feedback = build_state.last_feedback
        # assert build_state.version >= build_state.opt_step, \
        #     f"Build state version {build_state.version} is less than optimization step {build_state.opt_step}, should never happen."
        locality_policy = self.optimizer_configs['locality_policy']
        if cicd_step > 0:
            old_pairs = schedule[cicd_step - 1]['new_tasks'] + schedule[cicd_step - 1]['old_tasks']
        else:
            old_pairs = None
        self.monitor.log_state(scenario, personas, status='running', note=f"Building for cicd step {cicd_step+1}, locality policy: {locality_policy}, training set size: {len(training_set)}, from opt step: {build_state.opt_step + 1}/{self.optimizer_configs['max_optimize_steps']}")
        U.cprint(f"Starting build for scenario {scenario.id} and personas {personas.id} with {len(training_set)} training pairs, opt step {build_state.opt_step+1}/{self.optimizer_configs['max_optimize_steps']}...", 'y')
        log_fn = ft.partial(self.monitor.log_state, scenario=scenario, personas=personas)
        for step in range(build_state.opt_step, self.optimizer_configs['max_optimize_steps']):
            U.cprint(f"Step {step + 1}/{self.optimizer_configs['max_optimize_steps']}: Building application for scenario {scenario.id} and personas {personas.id}...", 'y')
            self.monitor.log_state(scenario, personas, status='running', note=f"Start building for cicd step {cicd_step+1}, opt step: {build_state.opt_step + 1}/{self.optimizer_configs['max_optimize_steps']}.")
            if cicd_step == 0:
                if step == 0:
                    self.config['optimizer_configs']['locality_control'] = 'none' 
                else:
                    if locality_policy == 'cicd':
                        self.config['optimizer_configs']['locality_control'] = 'none' 
                    else:
                        self.config['optimizer_configs']['locality_control'] = _locality_control
            else:
                if locality_policy == 'init':
                    self.config['optimizer_configs']['locality_control'] = 'none' 
                else:
                    self.config['optimizer_configs']['locality_control'] = _locality_control 

            if step == 0:
                def _log_fn(note):
                    log_fn(status='building', note=f'Step {step+1}/{self.builder_configs['max_build_steps']}:{note}')
                build_state = await self.build_app(build_state, training_pairs=training_set, old_pairs=old_pairs, log_fn=_log_fn)
            else:
                self.config['optimizer_configs']['locality_control'] = _locality_control
                def _log_fn(note):
                    log_fn(status='optimizing', note=f'Step {step+1}/{self.builder_configs['max_build_steps']}:{note}')
                build_state = await self.optimize_app(build_state, training_pairs=training_set, old_pairs=old_pairs, log_fn=_log_fn)
            random.shuffle(training_set)
            batch = np.random.choice(list(range(len(training_set))), batch_size)
            training_batch = [training_set[i] for i in batch]
            self.monitor.log_state(scenario, personas, status='running', note=f"CUA tests for opt step: {build_state.opt_step+1}/{self.optimizer_configs['max_optimize_steps']}.")
            cua_sessions = await self.async_cua_tests(build_state, training_batch, cua_semaphore=cua_semaphore)
            # if build_state.n_traces != step+1:
            #     U.cprint(f"Warning: Number of traces {build_state.n_traces} does not match step {step + 1}, this may cause issues.", 'r')
            act = build_state.load_act()
            feedback = Feedback(cua_sessions=cua_sessions, act=act)
            build_state.new_feedback(feedback)  # add the feedback to the build state
            build_state.save()

    async def build_cicd(self, scenario: Scenario, personas: PersonaDistribution, force_rebuild: bool = False, cua_semaphore = None) -> BuildState:
        state = self.get_build_state(scenario, personas) # just to get schedule
        schedule = self.get_schedule(state)
        for step in schedule:
            await self.build(scenario, personas, force_rebuild=force_rebuild, cicd_step=step, cua_semaphore=cua_semaphore)

    @property
    def monitor_dir(self) -> str:
        return U.pjoin(os.getenv('TMP_DIR', './.tmp'), '.exp_monitor', self.config['name'], self.exp_name)

    async def xbuild(self, pairs: List[Tuple[str, str, str]] = None):
        if pairs is None:
            if self.ckpt.chunks is not None:
                pairs = []
                chunks = str(self.config['experiment_configs']['chunks'])
                U.cprint(f"Building on dataset chunks: {chunks}", 'y')
                if chunks == 'all':
                    pairs = [self.ckpt.chunks.get(i, []) for i in range(len(self.ckpt.chunks))]
                elif '-' in chunks:
                    start, end = map(int, chunks.split('-'))
                    for i in range(start, end+1):
                        pairs.append(self.ckpt.chunks[i])
                elif ',' in chunks: 
                    for chunk in chunks.split(','):
                        pairs.append(self.ckpt.chunks[int(chunk)])
                else:
                    pairs = [self.ckpt.chunks[int(chunks)]]
                _total_pairs = sum([len(p) for p in pairs])
                U.cprint(f"Running on dataset chunks: {chunks} ({len(pairs)} chunks), total pairs {_total_pairs}", 'y')
            else:
                pairs = [self.app_pairs]
        assert sum([len(p) for p in pairs]) > 0, "No pairs to build, please provide a list of (category, scenario_id, personas_id) tuples."
        for idx, _pairs in enumerate(pairs):
            U.cprint(f"Building {len(_pairs)} pairs for chunk {idx}...", 'y')
            await self._xbuild(_pairs)

    async def _xbuild(self, pairs: List[Tuple[str, str, str]]) -> List[BuildState]:
        pairs = [(self.get_app_pair(cat, scenario_id, personas_id)) for cat, scenario_id, personas_id in pairs]
        workers = self.experiment_configs['num_workers']
        interval = self.experiment_configs['launch_interval']
        U.cprint(f"Building {len(pairs)} pairs with {workers} workers at {interval}s intervals...", 'y')
        build_states = []
        semaphore = asyncio.Semaphore(workers)
        cua_semaphore = asyncio.Semaphore(self.config['cua_configs']['global_cua_lock'])
        # run self.build_cicd in parallel
        async def build_pair(scenario: Scenario, personas: PersonaDistribution):
            async with semaphore:
                try:
                    self.monitor.new_build(scenario, personas)
                    build_state = await self.build_cicd(scenario, personas, force_rebuild=False, cua_semaphore=cua_semaphore)
                    build_states.append(build_state)
                    await asyncio.sleep(interval)  # to control the concurrency
                except Exception as e:
                    traceback_str = traceback.format_exc()
                    U.log_error(f'Error while building {scenario.id} and {personas.id}: {e}\n{traceback_str}', 'xbuild')
                    U.cprint(f"Error while building {scenario.id} and {personas.id}: {e}", 'r')
                finally:
                    self.monitor.close_build(scenario, personas, status='closed')

        await asyncio.gather(*(build_pair(scenario, personas) for scenario, personas in pairs), return_exceptions=True)
        return build_states


    async def eval(self, scenario: Scenario, personas: PersonaDistribution, cicd_step: int = 0) -> BuildState:
        raise NotImplementedError("eval is not implemented in the base class, please implement it in the derived class.")

    async def eval_cicd(self, scenario: Scenario, personas: PersonaDistribution) -> BuildState:
        eval_configs = self.config['eval_configs']
        raise NotImplementedError("eval_cicd is not implemented in the base class, please implement it in the derived class.")

    async def async_cua_tests(self, build_state: BuildState, task_batch, cua_semaphore = None) -> List[CUASession]:
        assert isinstance(task_batch, list) and all(len(task_pair) == 2 for task_pair in task_batch), \
            "task_batch must be a list of tuples (persona, demand) pairs."
        assert len(task_batch) > 0, "task_batch cannot be empty."
        assert build_state is not None, "build_state cannot be None."
        assert isinstance(build_state, BuildState), "build_state must be an instance of BuildState."
        if all(isinstance(task_pair[0], str) and isinstance(task_pair[1], str) for task_pair in task_batch):
            task_batch = [build_state.get_task_pair(*task_pair) for task_pair in task_batch]
        assert all(isinstance(task_pair[0], Persona) and isinstance(task_pair[1], Demand) for task_pair in task_batch), \
            "task_batch must contain tuples of (Persona, Demand) pairs or (PersonaID, DemandID) str pairs."
        traces_dir = build_state.new_traces()  
        U.cprint(f"Starting CUA tests for {len(task_batch)} tasks, traces will be saved to {traces_dir}", 'y')
        async def call_with_progress(persona, demand, progress_queue):
            # try:
            # Keep the trace dir name short to avoid exceeding the Windows MAX_PATH
            # limit (260 chars): persona.id/demand.id are long slugs and this dir is
            # nested deep under ckpt/appspace/traces + a '.cua' subdir. Truncate the
            # slug and append a short hash for uniqueness; timestamp preserves ordering.
            import hashlib
            _slug = f"{persona.id}_{demand.id}"
            if len(_slug) > 40:
                _slug = _slug[:40] + "_" + hashlib.md5(_slug.encode()).hexdigest()[:6]
            trace_dir = U.pjoin(traces_dir, f"{_slug}_{U.dt_now_str()}")
            cua_session = await self.test_app_cua(build_state, persona, demand, trace_dir=trace_dir)
            await progress_queue.put((persona, demand, cua_session, None, None))
            # except Exception as e:
            #     _traceback = traceback.format_exc()
            #     await progress_queue.put((persona, demand, None, e, _traceback))

        progress_queue = asyncio.Queue()
        tasks = [call_with_progress(persona, demand, progress_queue) for persona, demand in task_batch]
        semaphore = asyncio.Semaphore(self.optimizer_configs['cua_max_workers']) if cua_semaphore is None else cua_semaphore

        async def gather_with_concurrency(tasks):
            async def run_task(task):
                async with semaphore:
                    await asyncio.sleep(self.optimizer_configs['cua_launch_interval'])  # to control the concurrency
                    return await task
            return await asyncio.gather(*(run_task(task) for task in tasks))

        gather_task = asyncio.create_task(gather_with_concurrency(tasks))
        
        completed = 0
        cua_sessions = []
        while completed < len(task_batch):
            try:
                persona, demand, cua_session, error, _traceback = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                completed += 1
                if error is not None:
                    continue
                cua_sessions.append(cua_session)
            except asyncio.TimeoutError:
                if gather_task.done() and progress_queue.empty():
                    break

        await gather_task
        assert len(cua_sessions) > 0, "No CUA sessions were created, check the test_app_cua method."
        return cua_sessions

    async def test_app_cua(self, build_state: BuildState, persona: Persona, demand: Demand, use_venv = True, max_init_time = 30, trace_dir: str = None, **kwargs) -> CUASession:
        temp_output = build_state.get_temp_output_file(flush=True)  # flush the output file before running the app
        pid, output_handle = await build_state.run_app(output_file=temp_output, use_venv=use_venv, trace_dir=trace_dir, **kwargs)
        try:
            for _ in range(max_init_time):
                psutil.Process(pid)  # check if the process is still running
                if build_state.app_running(temp_output):  # if the app is running, we can stop checking
                    break
                await asyncio.sleep(1) # <-- NON-BLOCKING CALL
            url = build_state.running_url(temp_output)
        except psutil.NoSuchProcess:
            # U.cprint(f"Application with PID {pid} does not exist.", 'r')
            raise RuntimeError(f"Application with PID {pid} does not exist.")
        # try:
        # ckpt_dir = build_state.cua_ckpt_dir(persona, demand)
        # U.clean_and_backup(ckpt_dir)
        task = build_state.prompt_task(persona, demand)
        metadata = {
            'persona': persona.to_dict(include_demands=False),  # include_demands=False to avoid circular reference
            'demand': demand.to_dict(),
        }
        ckpt_dir = U.pjoin(trace_dir, '.cua')
        session = await self.cua.call(url, task, ckpt_dir=ckpt_dir, metadata=metadata, trace_dir=trace_dir)
        if output_handle:
            output_handle.close()
        # except Exception as e:
        #     U.cprint(f"Error while testing application: {e}", 'r')
        #     raise e
        # finally:
        #     if psutil.pid_exists(pid):
        #         U.cprint(f"Stopping application with PID {pid} after testing.", 'y')
        #         U.kill_process(pid)
        session.metadata['output'] = build_state.read_output(temp_output)
        return session

    
    @property
    def running_apps_df(self) -> pd.DataFrame:
        """
        Get a DataFrame of running applications.
        """
        data = []
        for _hash, app_info in self.running_apps.items():
            data.append({
                # 'hash': _hash,
                'pid': app_info['pid'],
                'scenario': app_info['scenario'].id,
                'personas': app_info['personas'].id,
                'appspace_dir': app_info['appspace_dir'],
            })
        return pd.DataFrame(data)
    

    def stop_app(self, scenario: Scenario, personas: PersonaDistribution):
        """
        Stop the application for the given scenario and persona distribution.
        """
        # FIXME: this may not kill the app, just killed the runner
        _hash = U.hash_str(scenario.id + personas.id)
        if _hash in self.running_apps:
            app_info = self.running_apps[_hash]
            pid = app_info['pid']
            if pid is not None:
                U.kill_process(pid)
            output_handle = app_info['output_handle']
            if output_handle:
                output_handle.close()
            del self.running_apps[_hash]
            U.cprint(f"Stopped application for scenario {scenario.id} and personas {personas.id}.", 'g')
        else:
            U.cprint(f"No running application found for scenario {scenario.id} and personas {personas.id}.", 'r')
        




class BasicSystem(SystemBase):
    pass





def build_system(config: Dict[str, Any] = None, exp_name: str = None, stream=None) -> SystemBase:
    """ Build a system based on the provided configuration.
    If no configuration is provided, it will load the default configuration from 'configs/base.yaml'.
    """ 
    if config is None:
        U.cprint("No configuration provided, loading default configuration from 'configs/default.yaml'", 'y')
        config = U.load_config()
    system_type = config['system_type']
    if system_type == 'basic':
        system = BasicSystem(config, exp_name, stream)
    else:
        raise ValueError(f'Invalid system type: {system_type}')
    return system
