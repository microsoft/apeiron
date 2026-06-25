import os
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any
import datetime as dt
import tiktoken
from tiktoken.model import encoding_name_for_model




class ParseError(Exception):
    def __init__(self, message: str, context: str = ""):
        self.message = message
        self.context = context
        super().__init__(self.message)


class Roles(Enum):
    SYSTEM = 'system'
    ASSISTANT = 'assistant'
    USER = 'user'
    TOOL = 'tool'

    @property
    def openai(self):
        # https://cdn.openai.com/spec/model-spec-2024-05-08.html#definitions
        if self == Roles.SYSTEM:
            return 'developer'
        elif self == Roles.ASSISTANT:
            return 'assistant'
        elif self == Roles.USER:
            return 'user'
        elif self == Roles.TOOL:
            return 'tool'

class RCollections(Enum):
    DIALOGS = 'dialogs' # To track the dialogs created in a session, and context for each llm call
    FRONTEND = 'frontend' # To track the frontend info in between for replay in Streamlit
    MESSAGES = 'messages' # To track the messages created in a session 


class Providers(Enum):
    OPENAI = 'openai'
    DATABRICKS = 'databricks'
    COPILOT = 'copilot'  # Claude (and others) via the GitHub Copilot SDK


class APITypes(Enum):
    COMPLETION = 'completion'
    RESPONSE = 'response'  


class Modalities(Enum):
    TEXT = 'text'
    IMAGE = 'image'
    AUDIO = 'audio' 
    FUNCTION_CALL = 'function_call'
    # pdf?
    
class Roles(Enum):
    USER = 'user'
    ASSISTANT = 'assistant'
    SYSTEM = 'system'
    TOOL = 'tool'
    TOOL_CALL = 'tool_call'

LLM_SIDE_ROLES = [Roles.ASSISTANT, Roles.TOOL_CALL]
    

class Features(Enum):
    FUNCTION_CALL = 'function_call'
    STRUCTURED_OUTPUT = 'structured_output'
    STREAMING = 'streaming'
    FINETUNING = 'finetuning'
    DISTILLATION = 'distillation'
    PREDICTED_OUTPUT = 'predicted_output'
    CLASSIFICATION = 'classification'
    WEB_SEARCH = 'web_search'
    COMPUTER_USE = 'computer_use'  # for computer use agent


MODEL_CARDS = {}


@dataclass
class Snapshot:
    name: str
    date: str 

    @property
    def dt(self):
        return dt.datetime.strptime(self.date, '%Y-%m-%d')


# See more in https://platform.openai.com/docs/api-reference/chat/create
OPENAI_ARGS = [
    'temperature', 
    'max_completion_tokens',
    'presence_penalty',
    'reasoning_effort', # o series only
    'response_format', # for structured output
    'tools', # for function calling
    'tool_choice', # for function calling
    'logit_bias', # for classification
    'top_logprobs', # for classification
]

# Args accepted on the Copilot/Claude path (consumed by LLMCaller._call_copilot).
COPILOT_ARGS = [
    'timeout',          # per-turn wait (seconds) for the Copilot session
    'copilot_provider', # optional BYOK provider, e.g. 'anthropic'
]


OPENAI_ENCODINGS = {
    'gpt-4.1': 'o200k_base',
    'o4-mini': 'o200k_base',
    'gpt-4.1-mini': 'o200k_base',
}

@dataclass
class CompletionCost:
    prompt_tokens: int
    completion_tokens: int
    cached_prompt_tokens: int
    cost: float

    def __str__(self):
        return f'''
Prompt tokens: {self.prompt_tokens}, 
Completion tokens: {self.completion_tokens}, 
Cached prompt tokens: {self.cached_prompt_tokens}, 
Cost: {self.cost:.4f} USD
        '''


@dataclass
class ModelCard:
    name: str
    provider: Providers
    snapshots: List[Snapshot]
    max_tokens: int
    max_output_tokens: int
    input_price: float # per 1M tokens
    cached_input_price: float # per 1M tokens
    output_price: float # per 1M tokens
    knowledge_cutoff: str # YYYY-MM-DD, one day after
    features: List[Features]
    input_modalities: List[Modalities] = field(default_factory=lambda: [Modalities.TEXT])
    is_reasoning: bool = False
    endpoint: str = None 
    apikey_varname: str = None 

    @property
    def snapshot_dict(self):
        return {s.name: s for s in self.snapshots}

    def __post_init__(self):
        self.snapshots = sorted(self.snapshots, key=lambda x: x.dt)
        MODEL_CARDS[self.name] = self

    @property
    def latest_snapshot(self):
        return self.snapshots[-1]

    def check_args(self, args: Dict[str, Any]):
        if self.provider in [Providers.OPENAI, Providers.DATABRICKS]:
            supported_args = OPENAI_ARGS
        elif self.provider == Providers.COPILOT:
            supported_args = COPILOT_ARGS
        else:
            raise NotImplementedError(f"Provider {self.provider} not supported")

        for arg in args:
            if arg not in supported_args:
                raise ValueError(f"Argument {arg} not supported")

    def cost(self, usage: Dict[str, float]) -> CompletionCost:
        if self.provider in [Providers.OPENAI, Providers.DATABRICKS]:
            return openai_model_usage(self, usage)
        
    def tokenize(self, text: str) -> List[int]:
        if self.provider in [Providers.OPENAI, Providers.DATABRICKS]:
            return tokenize_openai(text, self.name)
        
    def make_classifier(self, classes: List[str], strength: int = 10) -> Dict[str, Any]:
        assert Features.CLASSIFICATION in self.features, f'Model {self.name} does not support classification'
        token_ids = self.tokenize(' '.join(classes))
        assert len(token_ids) == len(classes), f'Classes {classes} cannot be tokenized into single tokens'
        logit_bias = {i: strength for i in token_ids}
        if self.provider in [Providers.OPENAI, Providers.DATABRICKS]:
            return classifier_args_openai(logit_bias)




def tokenize_openai(text: str, encoding: str = 'o200k_base'):
    # Models to encoding: https://github.com/openai/tiktoken/blob/main/tiktoken/model.py
    # List of all the encoding names: tiktoken.registry.list_encoding_names()   
    if encoding in OPENAI_ENCODINGS:
        encoding = OPENAI_ENCODINGS[encoding]
    elif encoding not in tiktoken.registry.list_encoding_names():
        try:
            encoding = encoding_name_for_model(encoding)
        except:
            raise ValueError(f"Encoding {encoding} not found")
    enc = tiktoken.get_encoding(encoding)
    return enc.encode(text)


def classifier_args_openai(logit_bias: Dict[int, int]):
    return {
        'logit_bias': logit_bias,
        'temperature': 0.0, # temperature=0.0, 
        'top_logprobs': len(logit_bias),
        'max_completion_tokens': 3, # give some buffer
        'logprobs': True,
    }

            
def find_model_card(name: str) -> ModelCard:
    if name not in MODEL_CARDS:
        for model_card in MODEL_CARDS.values():
            if name in model_card.snapshot_dict:
                return model_card
        raise ValueError(f"Model card {name} not found")
    return MODEL_CARDS[name]


def openai_model_usage(model_card: ModelCard, usage: Dict[str, float]) -> CompletionCost:
    # {
    #   "completion_tokens":400,
    #   "prompt_tokens":13584,
    #   "total_tokens":13984,
    #   "completion_tokens_details":{"accepted_prediction_tokens":0,"audio_tokens":0,"reasoning_tokens":0,"rejected_prediction_tokens":0},
    #   "prompt_tokens_details":{"audio_tokens":0,"cached_tokens":0}
    # }
    cost = 0
    cost += model_card.input_price * usage['prompt_tokens']
    cost += model_card.output_price * usage['completion_tokens']
    cost += model_card.cached_input_price * usage['prompt_tokens_details']['cached_tokens']
    cost = cost / 1000000 # convert to USD
    return CompletionCost(
        prompt_tokens=usage['prompt_tokens'],
        completion_tokens=usage['completion_tokens'],
        cached_prompt_tokens=usage['prompt_tokens_details']['cached_tokens'],
        cost=cost
    )



GPT_41 = ModelCard(
    name='gpt-4.1',
    provider=Providers.OPENAI,
    snapshots=[
        Snapshot(name='gpt-4.1', date='2025-04-14'),
    ],
    max_tokens=1047576,
    max_output_tokens=32768,
    input_price=2,
    cached_input_price=0.5,
    output_price=8,
    knowledge_cutoff='2024-06-01',
    input_modalities=[Modalities.TEXT, Modalities.IMAGE],
    features = [
        Features.FUNCTION_CALL, 
        Features.STRUCTURED_OUTPUT, 
        Features.STREAMING,     
        Features.FINETUNING, 
        Features.DISTILLATION, 
        Features.PREDICTED_OUTPUT,
        Features.CLASSIFICATION,
    ],
)


# gpt-5.x are the deployed successors to gpt-5 on Azure Foundry (gpt-5 itself is
# not deployable on every resource). Specs mirror the gpt-5 family; pricing is
# approximate and should be reconciled against the published rate card.
GPT_54 = ModelCard(
    name='gpt-5.4',
    provider=Providers.OPENAI,
    snapshots=[
        Snapshot(name='gpt-5.4', date='2025-08-07'),
    ],
    max_tokens=400000,
    max_output_tokens=128000,
    input_price=1.25,
    cached_input_price=0.125,
    output_price=10,
    knowledge_cutoff='2024-09-29',
    input_modalities=[Modalities.TEXT, Modalities.IMAGE],
    features=[
        Features.FUNCTION_CALL,
        Features.STRUCTURED_OUTPUT,
        Features.STREAMING,
        Features.FINETUNING,
        Features.DISTILLATION,
        Features.PREDICTED_OUTPUT,
        Features.CLASSIFICATION,
    ],
)


# Claude via the GitHub Copilot SDK (see sllm/copilot_client.py).
# Calls are routed through a GitHub Copilot subscription, or your own Anthropic
# key via BYOK (provider='anthropic', ANTHROPIC_API_KEY).
CLAUDE_SONNET_4_5_COPILOT = ModelCard(
    name='claude-sonnet-4.5',
    provider=Providers.COPILOT,
    snapshots=[
        Snapshot(name='claude-sonnet-4.5', date='2025-09-29'),
    ],
    max_tokens=200000,
    max_output_tokens=64000,
    input_price=3,
    cached_input_price=0.3,
    output_price=15,
    knowledge_cutoff='2025-01-30',
    input_modalities=[Modalities.TEXT, Modalities.IMAGE],
    features=[
        Features.FUNCTION_CALL,
        Features.STREAMING,
    ],
)
    
O4_MINI = ModelCard(
    name='o4-mini',
    provider=Providers.OPENAI,
    snapshots=[
        Snapshot(name='o4-mini', date='2025-04-16'), # deployment name
    ],
    max_tokens=200000,
    max_output_tokens=100000,
    input_price=1.1,
    cached_input_price=0.275,
    output_price=4.4,
    knowledge_cutoff='2024-06-01',
    input_modalities=[Modalities.TEXT, Modalities.IMAGE],
    features=[
        Features.FUNCTION_CALL, 
        Features.STRUCTURED_OUTPUT, 
        Features.STREAMING,     
    ],
    is_reasoning=True,
)

# O3_PRO = ModelCard(
#     name='o3-pro',
#     provider=Providers.OPENAI,
#     snapshots=[
#         Snapshot(name='o3-2025-04-16', date='2025-04-16'), 
#     ],
#     max_tokens=200000,
#     max_output_tokens=100000,
#     input_price=2,
#     cached_input_price=0.5,
#     output_price=80,
#     knowledge_cutoff='2024-06-01',
#     input_modalities=[Modalities.TEXT, Modalities.IMAGE],
#     features=[
#         Features.FUNCTION_CALL, 
#         Features.STRUCTURED_OUTPUT, 
#         Features.STREAMING,     
#     ],
#     is_reasoning=True,
# )

GPT_41_MINI = ModelCard(
    name='gpt-4.1-mini',
    provider=Providers.OPENAI,
    snapshots=[
        Snapshot(name='gpt-4.1-mini', date='2025-04-14'),
    ],
    max_tokens=1047576,
    max_output_tokens=32768,
    input_price=0.4,
    cached_input_price=0.1,
    output_price=1.6,
    knowledge_cutoff='2024-06-01',
    input_modalities=[Modalities.TEXT, Modalities.IMAGE],
    features=[
        Features.FUNCTION_CALL, 
        Features.STRUCTURED_OUTPUT, 
        Features.STREAMING,     
        Features.FINETUNING, 
        Features.CLASSIFICATION,
    ]
)



COMPUTER_USE = ModelCard(
    name='computer-use-preview',
    provider=Providers.OPENAI,
    snapshots=[
        Snapshot(name='computer-use-preview', date='2025-03-11'),
    ],
    max_tokens=8192,
    max_output_tokens=1024,
    input_price=3,
    cached_input_price=1.5,
    output_price=12,
    knowledge_cutoff='2023-09-30',
    input_modalities=[Modalities.TEXT, Modalities.IMAGE],
    features=[
        Features.FUNCTION_CALL,   
        Features.COMPUTER_USE,
    ],
    apikey_varname='CUA_API_KEY',
    # Endpoint is read from the environment so no personal/tenant URL is committed.
    # Set AZURE_CUA_ENDPOINT in your .env (see .env.example).
    endpoint=os.environ.get('AZURE_CUA_ENDPOINT'),
)



CODEX_MINI = ModelCard(
    name='codex-mini',
    provider=Providers.OPENAI,
    snapshots=[
        Snapshot(name='codex-mini', date='2025-04-16'),
    ],
    max_tokens=200000,
    max_output_tokens=100000,
    input_price=1.5,
    cached_input_price=0.375,
    output_price=6,
    knowledge_cutoff='2024-06-01',
    input_modalities=[Modalities.TEXT, Modalities.IMAGE],
    features=[
        Features.FUNCTION_CALL, 
        Features.STRUCTURED_OUTPUT, 
        Features.STREAMING,     
    ],
)



CLAUDE_4_SONNET = ModelCard(
    name='claude-sonnet-4',
    provider=Providers.DATABRICKS, 
    snapshots=[
        Snapshot(name='databricks-claude-sonnet-4', date='2025-05-22'),
    ],
    max_tokens=200000,
    max_output_tokens=64000,
    input_price=3,
    cached_input_price=0.3,
    output_price=15,
    knowledge_cutoff='2025-01-30', 
    input_modalities=[Modalities.TEXT, Modalities.IMAGE],
    features=[
        Features.FUNCTION_CALL, 
        Features.STRUCTURED_OUTPUT, 
        Features.STREAMING,     
    ],
)


GPT_5 = ModelCard(
    name='gpt-5',
    provider=Providers.OPENAI,
    snapshots=[
        Snapshot(name='gpt-5', date='2025-08-07'),
    ],
    max_tokens=400000,
    max_output_tokens=128000,
    input_price=1.25,
    cached_input_price=0.125,
    output_price=10,
    knowledge_cutoff='2024-09-29',
    input_modalities=[Modalities.TEXT, Modalities.IMAGE],
    features=[
        Features.FUNCTION_CALL, 
        Features.STRUCTURED_OUTPUT, 
        Features.STREAMING,     
        Features.FINETUNING, 
        Features.DISTILLATION, 
        Features.PREDICTED_OUTPUT,
        Features.CLASSIFICATION,
    ],
)