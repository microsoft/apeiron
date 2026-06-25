from matplotlib.pyplot import step
from sllm.llm import Agent, LLMCaller, Dialog, Prompts, find_model_card, LLMResponder
from sllm.const import APITypes
from sllm.llm import PROMPT_REGISTRY as PR
from sllm.tools.cua import OpenAICUA, CUASession
from playwright.async_api import async_playwright
from sllm.log import ReplayableLogBase, build_log_base, LogBase
from typing import Callable, Dict, Any, List, Tuple, Union
from enum import Enum
from dataclasses import dataclass, field, asdict
from sllm.models import Prompt, ParseError
from apeiron.library.re import Library
from apeiron.const import DemandList, DemandLists, Frameworks, PersonaDistributions, Scenario, ScenarioList, ScenarioLists, Persona, PersonaDistribution, Demand
import datetime as dt
import apeiron.utils as U
import os, sys, shutil
import subprocess
from sllm.utils import PrintSystem, StreamWrapper
import asyncio
from apeiron.btool.compilers import ReflexCompiler, CheckReport, StreamlitCompiler
from apeiron.agent.prompts.builder import bun_install_func
from apeiron.agent.prompts.cua import cua_conclude_parser
from apeiron.btool.ir import ACT
import numpy as np
from openai import OpenAI
import functools as ft
import copy


class AgentType(Enum):
    HELPER = 'helper'
    BUILDER = 'builder'
    CUA = 'cua'  # Computer Use Agent, used for testing the app
    JUDGE = 'judge'


def is_builder_agent(agent_type: Union[AgentType, str]) -> bool:
    if isinstance(agent_type, str):
        agent_type = AgentType(agent_type)
    return agent_type == AgentType.BUILDER

class AgentBase:
    agent_type: AgentType = None
    agent_group: List[str] = None # it maps to the agent_configs in config for better reuse 
    is_async: bool = False

    def __init__(self, config: Dict[str, Any], ckpt_dir: str, stream = None): # use a name extension to distinguish different runs
        if stream is None:
            stream = PrintSystem()
        self.config = config
        assert self.agent_group is not None, f"Agent group is not set for {self.agent_type}"
        _agent_configs = config['agent_configs']
        self.agent_configs = {}
        for agent_name in self.agent_group:
            assert agent_name in _agent_configs, f"Agent {agent_name} not found in agent configs"
            self.agent_configs[agent_name] = _agent_configs[agent_name]
        self._stream = stream
        self._stream_backup = stream
        self.st = None # to be initialized when calling __call__
        self.ckpt_dir = ckpt_dir
        self._log_base = build_log_base(config)
        self.agents = {}
        self.llm_caller = LLMCaller(self.config)
        self.llm_responder = LLMResponder(self.config)
        for agent_name, model_config in self.agent_configs.items():
            model_config = model_config.copy()
            model_name = model_config.pop('model_name')
            self.model = find_model_card(model_name)
            system_prompt_path = model_config.pop('system_prompt_path')
            _api_type = APITypes(model_config.pop('api_type', 'completion'))
            if _api_type == APITypes.COMPLETION:
                _caller = self.llm_caller
            elif _api_type == APITypes.RESPONSE:
                _caller = self.llm_responder
            else:
                raise ValueError(f"Unsupported API type: {_api_type}")
            self.agents[agent_name] = Agent(
                name=agent_name,
                system_prompt=PR[system_prompt_path],  # TODO: directly from prompt
                model=model_name,
                llm_caller=_caller,
                model_args=model_config,
                log_base=self._log_base,
                max_exception_retry=self.config.get('max_exception_retry', 3),
                max_interrupt_times=self.config.get('max_interrupt_times', 5),
                max_llm_recall=self.config.get('max_llm_recall', 3),
            )
        assert self.agent_type is not None, "Agent type is not set"

    def set_st(self, session_name: str):
        self.st = StreamWrapper(self._stream, self._log_base, session_name)

    def restore_st(self):
        self.st = None

    def silent(self):
        self._stream = PrintSystem(silent=True)

    def restore(self):
        self._stream = self._stream_backup  





####################################################################
# Helper Agents
####################################################################




class BuildHelper(AgentBase):
    agent_type = AgentType.HELPER
    agent_group = ['scenario_helper', 'demand_helper', 'persona_helper']

    def __init__(self, config: Dict[str, Any], ckpt_dir: str, stream=None):
        super().__init__(config, ckpt_dir, stream)
        self.scenario_helper: Agent = self.agents['scenario_helper']
        self.demand_helper: Agent = self.agents['demand_helper']
        self.persona_helper: Agent = self.agents['persona_helper']
        self.helper_configs = config['helper_configs']
        self.prompts = Prompts('helper')

    def synthesize_scenarios(self, library: Library, categories: Dict[str, int] = None,
                             version: str = '1.0', note: str = '', return_dialog = True) -> ScenarioLists:
        """
        Generate a list of scenarios based on the provided categories.
        """
        if categories is None:
            categories = self.helper_configs.get('scenario_categories', {})
            assert categories, "No categories provided for scenario generation"
        dialog = self.scenario_helper.init_dialog({'api_directory': library.api_directory}) # binds the library 
        step = 0
        scenario_lists = []
        cat_num = [f'{category}: {number}' for category, number in categories.items()]
        U.cprint(f"Generating scenarios for categories: {', '.join(cat_num)}", 'y')
        for category, number in categories.items():
            assert isinstance(number, int), f"Invalid number of scenarios for category {category}: {number}"
            if number <= 0:
                U.cprint(f"No scenarios to generate for category {category}, given nummber {number}, skipping.", 'y')
                continue
            ppath = 'scenario_helper_initial' if step == 0 else 'scenario_helper_followup'
            message = self.scenario_helper.send_message(
                dialog, self.prompts(ppath), {'number': number, 'category': category.replace('_', ' ')})
            print(f"Request sent to the Scenario Helper for category {category}...")
            _response, dialog, _ = self.scenario_helper.call(dialog)
            parsed = _response.parsed
            scenario_lists.append(ScenarioList.from_list(category,parsed['scenarios'], reasoning=parsed['analysis']))
            U.cprint(f"Generated {len(parsed['scenarios'])} scenarios for category {category}.", 'g')
            step += 1
        scenario_lists = ScenarioLists(scenario_lists=scenario_lists, version=version, note=note)
        return (scenario_lists, dialog) if return_dialog else scenario_lists
    
    def synthesize_personas(self, scenario: Scenario, num_distributions: int = None, num_personas:int = None, return_dialog = True) -> PersonaDistributions:
        """
        Generate a list of user personas for the given scenario.
        """
        if num_distributions is None:
            num_distributions = self.helper_configs['num_distributions']
        if num_personas is None:
            num_personas = self.helper_configs['num_personas']
        assert num_distributions > 0, f"Invalid number of persona distributions: {num_distributions}"
        assert num_personas > 0, f"Invalid number of personas: {num_personas}"
        dialog = self.persona_helper.init_dialog() 
        with self.st.expander('Persona Distribution Helper System Prompt', expanded=False):
            self.st.markdown(dialog.tail.content)
        message = self.persona_helper.send_message(dialog, self.prompts('persona_helper_request'), 
            {'num_distributions': num_distributions, 'num_personas': num_personas, 'scenario': scenario.json})
        with self.st.expander('Request sent to the Persona Distribution Helper', expanded=False):
            self.st.markdown(message.content)
        with self.st.status('Calling Persona Distribution Helper...', expanded=True):
            _response, dialog, _ = self.persona_helper.call(dialog)
            parsed = _response.parsed
            self.st.markdown(parsed['raw'])
        distributions = [PersonaDistribution.from_dict(pd) for pd in parsed['persona_distributions']]
        persona_distributions = PersonaDistributions(distributions = distributions, reasoning=parsed['analysis'])
        U.cprint(f"Generated {len(distributions)} persona distributions for scenario {scenario.name}.", 'g')
        return (persona_distributions, dialog) if return_dialog else persona_distributions

    def synthesize_demands(self, scenario: Scenario, persona_distribution: PersonaDistribution, num_demands: int = None, return_dialog = True) -> DemandLists:
        """
        Generate a list of user personas for the given scenario.
        """
        if num_demands is None:
            num_demands = self.helper_configs['num_demands']
        assert num_demands > 0, f"Invalid number of demands: {num_demands}"
        dialog = self.demand_helper.init_dialog() # binds the library
        with self.st.expander('Demand Helper System Prompt', expanded=False):
            self.st.markdown(dialog.tail.content)
        message = self.demand_helper.send_message(dialog, self.prompts('demand_helper_request'), 
            {'scenario': scenario.json, 'num_demands': num_demands, 'persona_distribution': persona_distribution.json})
        with self.st.status('Request sent to the Demand Helper', expanded=False):
            self.st.markdown(message.content)
        with self.st.status('Calling Demand Helper...', expanded=True):
            _response, dialog, _ = self.demand_helper.call(dialog, parser_args={'personas': list(persona_distribution.personas.keys())})
            parsed = _response.parsed
            self.st.markdown(parsed['raw'])
        demands = {}
        for _persona, _demands in parsed['demands'].items():
            demands[_persona] = DemandList.from_list(_demands)
        demand_lists = DemandLists(demand_lists=demands, reasoning=parsed['analysis'])
        U.cprint(f"Generated {len(demands)} demand distributions for scenario {scenario.name}.", 'g')
        return (demand_lists, dialog) if return_dialog else demand_lists
    



####################################################################
# Builder Agents
####################################################################


class OperationType(Enum):
    WRITE = 'write'
    DELETE = 'delete'
    WRITE_COMPONENT = 'write_component'  # write a component, e.g., a page or a widget

@dataclass
class Operation:
    target: str  # the file to be modified, e.g., 'app/main.py', default to be RELATIVE path
    type: OperationType  # the type of operation, e.g., 'read', 'write', 'delete'
    content: str = None  # the content to be written, if applicable

    def __post_init__(self):
        if isinstance(self.type, str):
            self.type = OperationType(self.type)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'target': self.target,
            'type': self.type.value,
            'content': self.content,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Operation':
        _type = OperationType(data['type'])
        return cls(
            target=data['target'],
            type=_type,
            content=data.get('content', None)
        )
    
    def execute(self, base_dir: str) -> str:
        path = U.pjoin(base_dir, self.target)
        if self.type == OperationType.WRITE:
            U.mkdirs(os.path.dirname(path))  # ensure the directory exists
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.content)
            return f"Wrote content to {self.target}"
        elif self.type == OperationType.DELETE:
            # delete the file or directory
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return f"Deleted {self.target}"

@dataclass
class OperationSequence:
    operations: List[Operation]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'operations': [operation.to_dict() for operation in self.operations],   
        }
    
    @classmethod
    def from_list(cls, data: List[Dict[str, Any]]) -> 'OperationSequence':
        operations = [Operation.from_dict(op_data) for op_data in data]
        return cls(operations=operations)
    
    def execute(self, base_dir: str) -> List[str]:
        """
        Execute the operations in the sequence.
        Returns a summary of the execution.
        """
        record = []
        for operation in self.operations:
            record.append(operation.execute(base_dir))
        return record


class SessionStatus(Enum):
    OPEN = 'open' # the session is remain open, operations can be added
    CLOSED = 'closed'  # the session is closed, no more operations can be added
    SUCCEEDED = 'succeeded'  # the session is closed with success, no more operations can be added
    FAILED = 'failed'  # the session failed, no more operations can be added


@dataclass
class BuildSession: # one session, one dialog
    appspace_dir: str  # the directory of the appspace, including the app dir, state.json
    session_id: int = None # a unique identifier for the session, if not set, it will be generated
    operations: List[OperationSequence] = field(default_factory=list)  # a list of operation sequences, each sequence is a list of operations   
    created_at: dt.datetime = field(default_factory=dt.datetime.now)
    status: SessionStatus = SessionStatus.OPEN  
    instructions: str = None  # instructions for the session, can be used to guide the builder agent
    testcases = None # TODO
    check_record: List[CheckReport] = field(default_factory=list)  # a list of test reports, each report is a CheckReport object
    _deliverable: bool = False  # whether the app is deliverable, decided by the builder agent
    _parent_id: int = None  # the id of the parent session, if any, used for linking sessions
    dialog: Dialog = None  # the dialog of the session, used for communication with the builder agent
    journal: str = None  # a journal of the session, be provided in concluding, what the builder agent has done, what the app looks like, what to do next, etc.

    def __post_init__(self):
        session_path = U.pjoin(self.appspace_dir, 'sessions')
        if self._parent_id is None:
            self._parent_id = 0
        U.mkdirs(session_path)
        if not self.session_id:
            self.session_id = int(len(os.listdir(session_path)))+1 # start from 1, 0 is reserved for the initial state
        self.save_checkpoint(self._parent_id)
            
    @property
    def deliverable(self) -> bool:
        return self._deliverable and self.status == SessionStatus.SUCCEEDED

    @property
    def app_dir(self) -> str:
        return U.pjoin(self.appspace_dir, 'app')
    
    @property
    def traces_dir(self) -> str:
        return U.pjoin(self.appspace_dir, 'traces')

    @property
    def session_dir(self) -> str:
        return U.pjoin(self.appspace_dir, 'sessions', str(self.session_id))

    def to_dict(self) -> Dict[str, Any]:
        _dict = asdict(self)
        _dict['status'] = self.status.value
        _dict['operations'] = [operation_sequence.to_dict() for operation_sequence in self.operations]
        _dict['created_at'] = self.created_at.isoformat()
        _dict['check_record'] = [check_report.to_dict() for check_report in self.check_record]
        if self.dialog:
            _dict['dialog'] = self.dialog.to_dict()
        return _dict
    

    def execute_ops(self, op_sequence: OperationSequence, warnings: List[str] = None) -> str:
        record = op_sequence.execute(self.app_dir)
        if record:
            result = f"Successfully executed {len(op_sequence.operations)} operations:\n"
            result += '\n'.join(record) 
        else:
            result = "No operations executed."
        if warnings:
            result += '\n\nWarnings:\n' + '\n'.join(warnings)
        return result

    @property
    def session_state_dir(self) -> str:
        return U.pjoin(self.session_dir, 'state.json')

    def save(self):
        """
        Save the state of the session to a JSON file.
        """
        U.mkdirs(self.session_dir)
        U.save_json(self.session_state_dir, self.to_dict())

    @classmethod
    def from_dict(cls, json_data: Dict[str, Any], appspace_dir: str = None, log_base: LogBase = None) -> 'BuildSession':
        """
        Create a BuildSession from a JSON state.
        """
        created_at = dt.datetime.fromisoformat(json_data.pop('created_at'))
        status = SessionStatus(json_data.pop('status'))
        operations = [OperationSequence.from_list(seq) for seq in json_data.pop('operations', [])]
        _appspace_dir = json_data.pop('appspace_dir')
        _check_record = json_data.pop('check_record', [])
        dialog = None
        if 'dialog' in json_data:
            _dialog = json_data.pop('dialog')
            if _dialog is not None:
                assert log_base is not None, "Log base must be provided when loading a dialog."
                dialog = Dialog.from_dict(_dialog, log_base, PR)
        return cls(
            appspace_dir=appspace_dir if appspace_dir else _appspace_dir,
            created_at=created_at,
            status=status,
            operations=operations,
            check_record=[CheckReport.from_dict(cr) for cr in _check_record],
            dialog=dialog,
            **json_data
        )
    
    def save_checkpoint(self, session_id: int):
        ckpt_dir = U.pjoin(self.appspace_dir, 'ckpts', str(session_id))
        ckpt_app_dir = U.pjoin(ckpt_dir, 'app')
        ckpt_traces_dir = U.pjoin(ckpt_dir, 'traces') 
        if not U.pexists(ckpt_app_dir):
            # ignore = [
            #     U.pjoin(self.app_dir, '.web', '.next', 'trace'),  # sometimes cause error when copying, ignore it
            # ]
            shutil.copytree(self.app_dir, ckpt_app_dir)#, ignore=U.ignore_by_abspaths(ignore))  # copy the app directory to the checkpoint directory
            if U.pexists(self.traces_dir):
                shutil.copytree(self.traces_dir, ckpt_traces_dir)  # copy the traces directory
            ckpt_meta = {
                'session_id': session_id  # who created this checkpoint, if it is the first session, it will be 0
            }
            U.save_json(U.pjoin(ckpt_dir, 'metadata.json'), ckpt_meta)  # save the checkpoint metadata

    def conclude(self):
        if self.status == SessionStatus.SUCCEEDED:
            self.save_checkpoint(self.session_id)  # save the current state as a checkpoint

    # def read_file(self, target: str) -> str:
    #     """
    #     Read the content of a file in the app directory.
    #     """
    #     path = U.pjoin(self.app_dir, target)
    #     if not U.pexists(path):
    #         raise FileNotFoundError(f"File {target} not found. Remember to provide the relative path from the project directory.")
    #     with open(path, 'r', encoding='utf-8') as f:
    #         return f.read()
        
    # def read_files(self, paths: List[str]) -> Dict[str, str]:
    #     """
    #     Read the content of multiple files in the app directory.
    #     Returns a dictionary mapping file names to their content.
    #     """
    #     if isinstance(paths, str):
    #         paths = [paths]
    #     _prompt = ''
    #     for target in paths:
    #         _prompt += f'File {target}:\n\n{self.read_file(target)}\n\n'
    #     return _prompt

    def bun_install(self, packages: List[str]) -> str:
        """
        Install a package using bun.
        """
        command = ['bun', 'add'] + packages
        result = subprocess.run(command, cwd=self.app_dir, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to install packages: {result.stderr}")
        return f"Successfully installed packages: {', '.join(packages)}.\n\n{result.stdout}"


@dataclass
class BuildState:
    scenario: Scenario  # the scenario of the app to be built
    personas: PersonaDistribution  # the target user personas of the app to be built
    appspace_dir: str # the directory of the appspace, including the app dir, state.json
    framework: Frameworks 
    sessions: List[BuildSession] = field(default_factory=list)  # a list of build sessions, each session is a BuildSession object
    bind_libraries: List[str] = field(default_factory=list)  # libraries to bind, e.g., ['apeiron.library.re', 'apeiron.library.ui']
    feedbacks: List['Feedback'] = field(default_factory=list)  # feedback from the user or the builder agent, can be used to improve the app

    def __post_init__(self):
        if self.framework == Frameworks.REFLEX:
            self.compiler = ReflexCompiler(build_state=self, bind_libraries=self.bind_libraries)
        elif self.framework == Frameworks.STREAMLIT:
            self.compiler = StreamlitCompiler(build_state=self, bind_libraries=self.bind_libraries)
        if not self.initialized:
            self.compiler.init()
            self.save()
        self.run_app = self.compiler.run_app  
        self.app_running = self.compiler.app_running
        self.check = self.compiler.check  
        self.read_output = self.compiler.read_output  # read the output of the app
        self.app_output_file = self.compiler.app_output_file  # the output file of the app, used for reading the output
        self.running_url = self.compiler.running_url  # the URL of the running app, used for accessing the app
        self.get_temp_output_file = self.compiler.get_temp_output_file  # get the temporary output file of the app, used for reading the output

    def new_feedback(self, feedback: 'Feedback'):
        """
        Add a new feedback to the build state.
        """
        if not isinstance(feedback, Feedback):
            raise TypeError(f"Feedback must be an instance of Feedback, got {type(feedback)}")
        self.feedbacks.append(feedback)

    @property
    def last_feedback(self) -> 'Feedback':
        """
        Get the last feedback from the build state.
        """
        if not self.feedbacks:
            return None
        return self.feedbacks[-1]

    def find_session(self, session_id: int) -> BuildSession:
        """
        Find a build session by its session_id.
        """
        for session in self.sessions:
            if str(session.session_id) == str(session_id):
                return session
        return None
    
    @property
    def task_pairs(self) -> List[Tuple[str, str]]:
        # (persona_idx, demand_idx)
        task_pairs = []
        for persona in self.personas._personas:
            for demand in persona.demands.demands:
                task_pairs.append((persona.id, demand.id))
        return task_pairs

    def get_task_pairs(self, random_seed: int) -> List[Tuple[str, str]]:
        np.random.seed(random_seed)
        task_pairs = self.task_pairs
        np.random.shuffle(task_pairs)
        return task_pairs

    def slice_task_pairs(self, task_pairs: list = None, train_ratio: float = 0.6, test_ratio: float = 0.2, dev_ratio: float = 0.2, random_seed: int = 42):
        """
        Slice the task pairs into train, dev, and test sets based on the given ratios.
        """
        assert train_ratio + dev_ratio + test_ratio == 1.0, "The sum of train, dev, and test ratios must be 1.0"
        if task_pairs is None:
            task_pairs = self.get_task_pairs(random_seed)
        n = len(task_pairs)
        train_end = int(n * train_ratio)
        dev_end = int(n * (train_ratio + dev_ratio))
        return {
            'train': task_pairs[:train_end],
            'dev': task_pairs[train_end:dev_end],
            'test': task_pairs[dev_end:]
        }

    def get_task_pair(self, persona_idx: str, demand_idx: str) -> Tuple[Persona, Demand]:
        """
        Get the task pair for the given persona and demand indices.
        """
        persona = next((p for p in self.personas._personas if p.id == persona_idx), None)
        if persona is None:
            raise ValueError(f"Persona {persona_idx} not found.")
        demand = next((d for d in persona.demands.demands if d.id == demand_idx), None)
        if demand is None:
            raise ValueError(f"Demand {demand_idx} not found for persona {persona.name}.")
        return persona, demand  
    
    def schedule_task_cicd(self, init_samples, cicd_samples, random_seed: int = 42):
        task_pairs = self.get_task_pairs(random_seed)
        if isinstance(cicd_samples, list):
            N_cicd = len(cicd_samples)
        else:
            N_cicd = (len(task_pairs) - init_samples) // cicd_samples
            cicd_samples = [cicd_samples] * N_cicd
        if N_cicd < 0:
            N_cicd = 0  # no cicd tasks, only initial tasks
        samples = {}
        _old_tasks = []
        _new_tasks = task_pairs[:init_samples]
        _init_samples = init_samples
        for i in range(N_cicd+1):
            if i > 0:
                _tasks = copy.deepcopy(_old_tasks+_new_tasks)  # task list for last round
                _old_tasks = []  # reset old tasks for this cicd step
                _new_tasks = task_pairs[_init_samples : _init_samples + cicd_samples[i-1]]
                _init_samples += cicd_samples[i-1]  # update the initial samples for this cicd step
                # randomly replace cicd_samples tasks with new tasks
                n_to_sample = min(_init_samples - cicd_samples[i-1], len(_tasks))
                for idx in np.random.choice(len(_tasks), n_to_sample, replace=False):
                    _old_tasks.append(_tasks[idx])  # preserve the old tasks
            samples[i] = {
                'old_tasks': copy.deepcopy(_old_tasks),  # initial tasks
                'new_tasks': copy.deepcopy(_new_tasks),  # new tasks for this cicd step
            }
        return samples

    @property
    def version(self) -> int: # every version must have a feedback
        version = 0
        for session in self.sessions:
            if session.deliverable:
                version += 1
        return version
    
    @property
    def opt_step(self) -> int: # a finished step is closed with feedback
        return len(self.feedbacks) # marks the fully finished op steps
    

    @property
    def app_dir(self) -> str:
        return U.pjoin(self.appspace_dir, 'app')
    
    @property
    def traces_dir(self) -> str:
        return U.pjoin(self.appspace_dir, 'traces')
    
    @property
    def n_traces(self) -> int:
        """
        Get the number of traces in the traces directory.
        """
        if not U.pexists(self.traces_dir):
            return 0
        return len(os.listdir(self.traces_dir))
    
    @property
    def latest_trace_dir(self) -> str:
        n_traces = self.n_traces
        if n_traces == 0:
            return None
        return U.pjoin(self.traces_dir, f'trace_{n_traces-1}')
    
    def load_act(self, trace_dir: str = None) -> ACT:
        if trace_dir is None:
            trace_dir = self.latest_trace_dir
            if trace_dir is None:
                raise ValueError("No trace directory found.")
        act = ACT.from_trace_dir(trace_dir)
        return act

    def new_traces(self) -> str:
        U.mkdirs(self.traces_dir)
        n_traces = len(os.listdir(self.traces_dir))
        return U.pjoin(self.traces_dir, f'trace_{n_traces}')

    @property
    def state_path(self) -> str:
        return U.pjoin(self.appspace_dir, 'state.json')
    
    @property
    def session_dir(self) -> str:
        return U.pjoin(self.appspace_dir, 'sessions')

    def load_sessions(self, log_base: LogBase):
        """
        Load all build sessions from the session directory.
        """
        if not U.pexists(self.session_dir):
            return
        self.sessions = []
        for session_file in os.listdir(self.session_dir):
            try:
                session_path = U.pjoin(self.session_dir, session_file, 'state.json')
                data = U.load_json(session_path, None)
                session = BuildSession.from_dict(data, appspace_dir=self.appspace_dir, log_base=log_base)
                self.sessions.append(session)
            except Exception as e:
                U.cprint(f"Error loading session {session_file}, skip it: {e}", 'r')
        self.sessions.sort(key=lambda s: s.created_at)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'scenario': self.scenario.to_dict(save_personas=False),  # save without personas to avoid circular reference
            'personas': self.personas.to_dict(),
            'appspace_dir': self.appspace_dir,
            'bind_libraries': self.bind_libraries,
            'framework': self.framework.value,
            'feedbacks': []#feedback.to_dict() for feedback in self.feedbacks],
        }

    @property
    def feedback_dir(self):
        return U.pjoin(self.appspace_dir, 'feedbacks')

    def save(self):
        U.save_json(self.state_path, self.to_dict())
        U.mkdirs(self.feedback_dir)
        for idx, feedback in enumerate(self.feedbacks):
            _path = U.pjoin(self.feedback_dir, f'feedback_{idx}.json')
            if not U.pexists(_path):
                U.save_json(_path, feedback.to_dict())

    @property
    def initialized(self) -> bool:
        return U.pexists(self.app_dir) and len(os.listdir(self.app_dir)) > 0 and U.pexists(self.state_path)

    def app_directory(self, read_files = False) -> str:
        if self.framework == Frameworks.STREAMLIT:
            filter_by_path = ['streamlit.py']
        app_dir, file_contents = U.directory_tree(self.app_dir, filter_by_path=filter_by_path, read_files=True)
        if read_files:
            for file, content in file_contents.items():
                file = file.replace(self.app_dir+'/', '')  # make the path relative to the app directory
                app_dir += f'\n\n---\n\nFile: {file}\n\n{content}'
        return app_dir

    def prompt(self, include_traces: bool, pairs: list = None, old_pairs: list = None) -> str:
        """
        Get the prompt for the build state. 
        It prompts the scenario, personas, demands, and the directory of the app now.
        """
        prompt = 'The scenario and the personas for the app to be built are as follows:\n\n'
        prompt += self.scenario.prompt + '\n\n'
        prompt += self.personas.prompt_with_demands(pairs)
        if old_pairs is not None:
            prompt += f'\n\n## Additional background\n\n'
            prompt += f'You are not working on an old version of the app, which has been built with the following demands:\n\n'
            prompt += self.personas.prompt_with_demands(old_pairs)
            prompt += '''
The demands have been shifted so you are working on modifying the app to best meet the new, shifted demands.
'''
        prompt += '\n\n## App Directory'
        prompt += f'\n\nThe current app directory is:\n\n{self.app_directory(read_files=True)}\n\n'
        if self.last_feedback:
            prompt += f'\n\n{self.last_feedback.prompt(include_traces=include_traces)}\n\n'
        prompt += self.journals_prompt
        return prompt  

    @classmethod
    def from_dict(cls, json_data: Dict[str, Any], feedbacks, log_base: LogBase, appspace_dir = None) -> 'BuildState':
        appspace_dir = json_data['appspace_dir'] if appspace_dir is None else appspace_dir
        inst = cls(
            scenario=Scenario.from_dict(json_data['scenario'], load_personas=False),
            personas=PersonaDistribution.from_dict(json_data['personas']),
            appspace_dir=appspace_dir,
            bind_libraries=json_data['bind_libraries'],
            framework=Frameworks(json_data.get('framework','streamlit')),
            feedbacks=[Feedback.from_dict(feedback) for feedback in feedbacks],
        )
        inst.load_sessions(log_base)  # load the sessions from the session directory
        return inst

    def prompt_task(self, persona: Persona, demand: Demand) -> str:
        return f'''### User persona:

{persona.prompt}

### Task to perform from this user persona:

{demand.prompt}
''' 

    @property
    def deliverable(self) -> bool:
        return self.last_session and self.last_session.deliverable
    
    @property
    def sorted_sessions(self) -> List[BuildSession]:
        """
        Get the list of build sessions sorted by creation time. From oldest to newest.
        """
        return sorted(self.sessions, key=lambda s: s.created_at)

    @property
    def last_session(self) -> BuildSession:
        """
        Get the last build session.
        """
        if not self.sessions:
            return None
        return self.sorted_sessions[-1]
    
    @property
    def last_successful_session(self) -> BuildSession:
        for session in reversed(self.sorted_sessions):
            if session.status == SessionStatus.SUCCEEDED:
                return session
        return None
    
    @property
    def last_successful_ckpt_dir(self):
        """
        Get the directory of the last successful checkpoint.
        """
        if not self.last_successful_session:
            return None
        return U.pjoin(self.appspace_dir, 'ckpts', str(self.last_successful_session.session_id))
    
    @property
    def last_version_app_dir(self) -> str:
        """
        Get the directory for the old version app.
        """
        if not self.last_successful_ckpt_dir:
            return None
        return U.pjoin(self.last_successful_ckpt_dir, 'app')

    @property
    def last_version_trace_dir(self) -> str:
        """
        Get the directory for the old version traces.
        This is used to compare the current app with the previous version.
        """
        if not self.last_successful_ckpt_dir:
            return None
        traces_dir = U.pjoin(self.last_successful_ckpt_dir, 'traces')
        n_traces = len(os.listdir(traces_dir)) if U.pexists(traces_dir) else 0
        if n_traces == 0:
            return None
        last_traces = U.pjoin(traces_dir, str(n_traces - 1))
        return last_traces

    def revert_to(self, session_id: int) -> BuildSession:
        ckpt_dir = U.pjoin(self.appspace_dir, 'ckpts', str(session_id))
        if not U.pexists(ckpt_dir):
            raise ValueError(f"Checkpoint with id {session_id} not found in {ckpt_dir}.")
        shutil.rmtree(self.app_dir)
        ckpt_app_dir = U.pjoin(ckpt_dir, 'app')
        shutil.copytree(ckpt_app_dir, self.app_dir)
        return U.load_json(U.pjoin(ckpt_dir, 'metadata.json'))

    def revert_to_last_successful(self) -> BuildSession:
        if not self.last_successful_session:
            return self.revert_to(0)
        last_successful_session = self.last_successful_session
        while True:
            try:
               sess_id = last_successful_session.session_id
               print(f"+++ Reverting to last successful session {sess_id}...")
               return self.revert_to(sess_id)
            except Exception as e:
                if not last_successful_session:
                    return self.revert_to(0)
                _parent_id = last_successful_session._parent_id
                last_successful_session = self.find_session(_parent_id) if _parent_id else self.find_session(0)  # revert to the initial state if no parent session found
                U.cprint(f"+++ Error reverting to last successful session: {e}, try revert to session {_parent_id}", 'r')

    
    def cua_ckpt_dir(self, ckpt_dir: str, persona: Persona, demand: Demand) -> str:
        return U.pjoin(ckpt_dir, persona.id, demand.id)

    def get_cua_ckpt(self, ckpt_dir: str, persona: Persona, demand: Demand) -> CUASession:
        """
        Get the checkpoint for the CUA agent for the given persona and demand.
        """
        ckpt_dir = self.cua_ckpt_dir(ckpt_dir, persona, demand)
        ckpt_file = U.pjoin(ckpt_dir, 'cua_session.json')
        if not U.pexists(ckpt_file):
            return None
        return CUASession.from_dict(U.load_json(ckpt_file))

    @property
    def journals(self) -> List[str]:
        """
        Get the journals of the build sessions.
        """
        journals = {}
        _parent = self.last_successful_session
        while _parent:
            assert _parent.status == SessionStatus.SUCCEEDED, "Cannot get journals from a session that is not successful."
            assert _parent.journal is not None, "Cannot get journals from a session that has no journal."
            journals[_parent.created_at] = _parent.journal
            if _parent._parent_id == 0:  # if the parent id is 0, it means it is the initial state
                break
            _parent = self.find_session(_parent._parent_id) if _parent._parent_id else None
        journals = sorted(journals.items(), key=lambda x: x[0])  # sort by creation time, from oldest to newest
        return journals 

    @property
    def journals_prompt(self) -> str:
        prompt = '# Work Journals\n\n'
        if self.last_successful_session is None:
            return prompt + "The app has just been initialized empty with reflex. The work journals are empty."
        prompt += "The work journals of the previous build sessions are as follows:\n\n"
        for created_at, journal in self.journals:
            prompt += f"**Session at {created_at}:**\n\n{journal}\n\n"
        return prompt

    def new_session(self, instructions: str = None, revert_to_success: bool = True) -> BuildSession:
        """
        Create a new build session for the current build state.
        Always start from the lastest successful state of the app.
        """
        if revert_to_success:
            if self.last_session and self.last_session.status != SessionStatus.SUCCEEDED:
                if self.last_session.status == SessionStatus.OPEN:
                    self.last_session.status = SessionStatus.CLOSED  # mark the last session as failed
                    self.last_session.save()  # save the last session state
                self.revert_to_last_successful()  # revert the app to the last successful state
            parent_id = self.last_successful_session.session_id if self.last_successful_session else None
        else:
            parent_id = self.last_session.session_id if self.last_session else None
        session = BuildSession(appspace_dir=self.appspace_dir, instructions=instructions, _parent_id=parent_id)
        self.sessions.append(session)
        self.save()
        return session
    
    


perplexty_client = None


def _get_perplexity_client():
    global perplexty_client
    if perplexty_client is None:
        perplexty_client = OpenAI(
            api_key=os.environ['PERPLEXITY_API_KEY'],
            base_url="https://api.perplexity.ai",
        )
    return perplexty_client


def search_perplexity(query: str, framework, max_completion_tokens: int = 5000, model = 'sonar') -> str:
    messages = [
        {
            "role": "system",
            "content": f'''You are an expert AI assistant working for a software engineer. The engineer is building a new app using the {framework} framework.
Your task is to assist the engineer in building the app, answering questions about the framework and helping with debugging.
'''
        },
        {   
            "role": "user",
            "content": query,
        },
    ]
    # chat completion without streaming
    response = _get_perplexity_client().chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=max_completion_tokens,
    )
    return response.choices[0].message.content

    
class BuilderBase(AgentBase):
    def __init__(self, config: Dict[str, Any], ckpt_dir: str, stream=None):
        super().__init__(config, ckpt_dir, stream)
        self.builder_configs = config['builder_configs']
        self.optimizer_configs = config['optimizer_configs']
        self.prompts = Prompts('builder')
        self.revert_to_success = self.builder_configs['revert_to_success']
        self.framework = Frameworks(self.builder_configs['framework'])
        self.search_perplexity = ft.partial(
            search_perplexity,
            framework=self.framework.value,
            max_completion_tokens=self.config['perplexity_max_completion'],
            model=self.config['perplexity_model']
        )
        self.test_in_venv = self.builder_configs['test_in_venv']


    def build(self, state: BuildState, library: Library, training_pairs: list = None, old_pairs: list = None, log_fn = None) -> BuildState:
        raise NotImplementedError("Subclass must implement this method")

    def optimize(self, state: BuildState, library: Library, training_pairs: list = None, old_pairs: list = None, log_fn = None) -> BuildState:
        """
        Optimize the build state based on the feedback.
        This method can be used to improve the app based on the feedback from the user or the builder agent.
        """
        raise NotImplementedError("Subclass must implement this method")
    


@dataclass
class Feedback:
    cua_sessions: List[CUASession] = field(default_factory=list)  # a list of CUA sessions, each session is a CUASession object
    act: ACT = None

    def content(self, include_traces: bool) -> str:
        if include_traces:
            assert self.act, "ACT must be provided to include traces in the feedback."
            return self.act.prompt
        else:
            assert self.cua_sessions, "No CUA sessions available to provide feedback."
            return '\n\n'.join([f"### CUA Session {i+1}\n\n{session.prompt}" for i, session in enumerate(self.cua_sessions)])

    def prompt(self, include_traces: bool) -> str:
        return f'''## Additional context

This app has been built and delivered to the user test previously, but it does not meet the user's requirements.
Now your team is working on improving the app based on the user test results (you might not be the first person to work on this, please refer to the work journal if available).
Here are the details of the user test results:

{self.content(include_traces=include_traces)}

Please try to improve the app based on the feedback.
'''

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the feedback to a dictionary.
        """
        _dict = {}
        _dict['cua_sessions'] = [session.to_dict() for session in self.cua_sessions]
        _dict['act'] = self.act.to_dict() if self.act else None
        return _dict
    
    @classmethod
    def from_dict(cls, json_data: Dict[str, Any]) -> 'Feedback':
        """
        Create a Feedback from a JSON state.
        """
        cua_sessions = [CUASession.from_dict(session) for session in json_data['cua_sessions']]
        act = ACT.from_dict(json_data['act']) 
        return cls(cua_sessions=cua_sessions, act=act)


class Builder(BuilderBase):
    agent_type = AgentType.BUILDER
    agent_group = ['builder']

    def __init__(self, config: Dict[str, Any], ckpt_dir: str, stream=None):
        super().__init__(config, ckpt_dir, stream)
        self.builder: Agent = self.agents['builder']
        self.include_traces = self.builder_configs['include_traces']  # whether to include traces in the build prompt

    def init_session(self, state: BuildState, library: Library, training_pairs: list = None, old_pairs: list = None) -> BuildSession:
        session = state.new_session(revert_to_success=self.revert_to_success) # backup, prepare dialog, also revert if needed
        session.dialog = self.builder.init_dialog({'api_directory': library.api_directory}) # binds the library
        _additional_instructions = ''
        if session.instructions:
            _additional_instructions = f'\n\nAdditional instructions:\n\n{session.instructions}'
        session.dialog.send_message(
            self.prompts('build_session_input'), 
            {'build_state': state.prompt(include_traces=self.include_traces, pairs=training_pairs, old_pairs=old_pairs) + _additional_instructions}
        )
        return session
    
    def _prep_build_prompt(self, _build_prompt: Prompt, session: BuildSession, library: Library) -> Prompt:
        _build_prompt.link_function('retrieve_api_doc', library.retrieve_api_docs)  
        # _build_prompt.link_function('read_files', session.read_files) 
        if self.framework == Frameworks.REFLEX:
            _build_prompt._functions.append(bun_install_func)
            _build_prompt.link_function('bun_install', session.bun_install) 
        # _build_prompt.link_function('websearch_agent', self.search_perplexity)  # link the search function to the prompt
        return _build_prompt

    async def step(self, state: BuildState, library: Library, training_pairs: list = None, old_pairs: list = None, log_fn: callable = None) -> bool:
        """
        Updating the app. Fulfill a build session.
        """
        session = self.init_session(state, library, training_pairs=training_pairs, old_pairs=old_pairs)  # create a new session for the current build state

        report = None  # initialize the report
        buggy = False  # whether the app is buggy, if True, the session will be closed
        exec_results = None  # the results of executing the operations
        debug_rounds = 0
        for i in range(self.builder_configs['max_session_steps']):
            if not buggy:
                ppath = 'build_act_start' if i == 0 else 'build_act_followup'
                prompt_args = {} if i == 0 else {'execution_result': exec_results}
            else:
                ppath = 'build_debug_start' if debug_rounds == 0 else 'build_debug_followup'
                prompt_args = {'bug_info': report.message} if debug_rounds == 0 else {'execution_result': exec_results}
                debug_rounds += 1
            U.cprint(f'Step {i}, prompt path: {ppath}')
            log_fn(f'Session step {i+1}/{self.builder_configs['max_session_steps']} calling')
            _build_prompt = self._prep_build_prompt(self.prompts(ppath), session, library)
            session.dialog.send_message(_build_prompt, prompt_args)
            # _response, session.dialog, _ = self.builder.call(session.dialog, parser_args = {'app_dir': session.app_dir})
            loop = asyncio.get_running_loop()
            _response, session.dialog, _ = await loop.run_in_executor(
                None,  # Use the default thread pool
                ft.partial(self.builder.call, session.dialog, parser_args={'app_dir': session.app_dir})
            )
            parsed = _response.parsed
            raw, ops, warnings, submit = parsed['raw'], parsed['operations'], parsed['warnings'], parsed['compile']
            operation_sequence = OperationSequence.from_list(ops)  # parse the operation sequence
            exec_results = session.execute_ops(operation_sequence, warnings)  # execute the operations
            U.cprint(exec_results, 'y')
            log_fn(f'Session step {i+1}/{self.builder_configs['max_session_steps']} checking')
            if submit:
                U.cprint('Start compiling and checking...', 'y')
                report = await state.check(
                    use_venv=self.test_in_venv,
                    max_cua_iterations=self.builder_configs['check_cua_steps'],
                    locality_control=self.optimizer_configs['locality_control'],
                    locality_thresholds=self.optimizer_configs['locality_threshold'],
                )  # check the app state
                if report.passed:
                    U.cprint(f"Build succeeded", 'g')
                    print(f"{report.message}")
                    session.status = SessionStatus.SUCCEEDED
                    session.dialog.send_message(self.prompts('build_session_conclude'))
                    _response, session.dialog, _ = self.builder.call(session.dialog)
                    parsed = _response.parsed
                    session.journal = parsed['raw']
                    session._deliverable = parsed['deliver'] 
                    session.save()
                    session.conclude()  # conclude the session, save the checkpoint
                    return True
                else:
                    U.cprint(f"Build failed", 'r')
                    print(f"{report.message}")
                    debug_rounds = 0  # reset the debug rounds
                    buggy = True  # if the report is not passed, the app is buggy, we need to debug it
            session.save()  # save the session state
        if session.status != SessionStatus.SUCCEEDED:
            session.status = SessionStatus.FAILED
            session.dialog.send_message(self.prompts('build_session_conclude_failed'))
            _response, session.dialog, _ = self.builder.call(session.dialog)
            session.journal = _response.parsed['raw']
            session.save()
            return False
        

    async def build(self, state: BuildState, library: Library, training_pairs: list = None, old_pairs: list = None, log_fn: Callable = None) -> BuildState:
        log_fn = log_fn or (lambda *a, **k: None)  # no-op when called standalone (e.g. via build_app without a monitor)
        for step in range(self.builder_configs['max_build_steps']):
            if state.deliverable:  # if the app is deliverable, stop building, for optimization, it need to be deliverable and converged
                U.cprint(f"Build deliverable", 'g')
                break
            _step = f"Build Step {step+1}/{self.builder_configs['max_build_steps']} (CICD: {state.opt_step+1}/{self.optimizer_configs['max_optimize_steps']})"
            U.cprint(_step, 'y')
            log_fn(note=_step)
            def _log_fn(note):
                log_fn(note=f'{_step}:{note}')
            await self.step(state, library, training_pairs=training_pairs, old_pairs=old_pairs, log_fn=_log_fn)  # perform a build step

        return state

    async def optimize(self, state: BuildState, library: Library, training_pairs: list = None, old_pairs: list = None, log_fn: Callable = None) -> BuildState:
        log_fn = log_fn or (lambda *a, **k: None)  # no-op when called standalone (e.g. via optimize_app without a monitor)
        assert state.last_session is not None, "No last session found in the build state. Please run the build method first."
        last_session_id = state.last_session.session_id if state.last_session else None
        try:
            if state.version > state.opt_step: # if the version is already advanced, return the state to get the feedback
                return state
            # if state.last_session is not None:
            # if state.version == state.opt_step:  # need to advance version by new delivery from building
            else:
                state.last_session._deliverable = False  # reset the deliverable flag
                _step = f"(V.{state.version}, CICD: {state.opt_step+1}/{self.optimizer_configs['max_optimize_steps']})"
                def _log_fn(note):
                    log_fn(note=f'{_step}:{note}')
                state = await self.build(state, library, training_pairs=training_pairs, old_pairs=old_pairs, log_fn=_log_fn)  # use the build method to optimize the app
        except Exception as e:
            raise RuntimeError(f"Failed to optimize the app: {e}") from e
        finally:
            for session in state.sessions:
                if session.session_id == last_session_id:
                    session._deliverable = True  # mark the last session as deliverable
        return state  # return the optimized build state

####################################################################
# Computer Use Agents
####################################################################



class CUA(AgentBase):
    agent_type = AgentType.CUA
    agent_group = []

    def __init__(self, config: Dict[str, Any], ckpt_dir: str, stream=None):
        super().__init__(config, ckpt_dir, stream)
        self.cua_configs = config['cua_configs']
        self.cua = OpenAICUA(self.cua_configs)
        self.prompts = Prompts('cua')

        self.cua_system = self.prompts('computer_use_agent_system')
        self.cua_task = self.prompts('computer_use_agent_task')
        self.cua_conclude = self.prompts('computer_use_agent_conclude')

    async def call(self, url: str, task: str, headless: bool = True, ckpt_dir = None, metadata: dict = None, trace_dir: str = None) -> CUASession:
        sess = await self.cua.call(
            url=url,
            user_input=self.cua_task(task=task),
            system=self.cua_system(),
            conclude=self.cua_conclude(),
            conclude_parser=cua_conclude_parser,
            metadata=metadata,
            headless=headless,
            ckpt_dir=ckpt_dir,
            trace_dir=trace_dir,
        )
        return sess
    

class Judge(AgentBase):
    agent_type = AgentType.JUDGE
    agent_group = ['judge']

    def __init__(self, config: Dict[str, Any], ckpt_dir: str, stream=None):
        super().__init__(config, ckpt_dir, stream)
        self.judge: Agent = self.agents['judge']
        
    




####################################################################
# Agent Registry
####################################################################



AGENT_REGISTRY: Dict[AgentType, AgentBase] = {}

# add all classes in this file to AGENT_REGISTRY if it is a subclass or subsubclass or subsubsubclass... of AgentBase

# traverse all classes in this file

def traverse_agentbase_classes(cls):
    for subcls in cls.__subclasses__():
        # check if subcls is a subclass of AgentBase
        if subcls.__name__ == 'AgentBase':
            continue
        if issubclass(subcls, AgentBase):
            assert subcls.agent_type not in AGENT_REGISTRY, f"Agent {subcls.agent_type} already exists"
            AGENT_REGISTRY[subcls.agent_type] = subcls
        traverse_agentbase_classes(subcls)

traverse_agentbase_classes(AgentBase)

U.cprint(f'{len(AGENT_REGISTRY)} agents registered: {", ".join([str(agent_type) for agent_type in AGENT_REGISTRY.keys()])}', 'g')

def build_agent(config: Dict[str, Any], ckpt_dir: str, stream, agent_type: AgentType) -> AgentBase:
    assert 'log_dir' in config, "log_dir is not set"
    # if agent_type is None:
    #     agent_type = AgentType(config['agent_type'])
    if isinstance(agent_type, str):
        agent_type = AgentType(agent_type)
    return AGENT_REGISTRY[agent_type](config, ckpt_dir, stream)




