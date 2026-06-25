import os
import json
import functools as ft
import time
import hashlib
import datetime as dt
import psutil
import requests
import yaml
import pandas as pd
import shutil
from PIL import Image
from pathlib import Path
from itertools import islice
import base64
from sllm.utils import cprint,call_api
from typing import Set
import re
from io import BytesIO
from typing import Dict, List
import io
import random
import uuid
import string
from dotenv import load_dotenv
import socket




PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # .../amorphware

# def load_env(env_file: str = '.env'):
#     _file = pjoin(PROJECT_ROOT, env_file)
#     if not pexists(_file):
#         raise FileNotFoundError(f'Env file not found: {_file}')
#     with open(_file, 'r') as f:
#         for line in f:
#             if line.strip().startswith('#'): continue
#             if line.strip() == '': continue
#             key, value = line.strip().split('=')
#             # print(f'Loaded env: {key}')
#             os.environ[key] = value


pjoin=os.path.join
psplit=os.path.split
pexists=os.path.exists
mkdirs=ft.partial(os.makedirs, exist_ok=True)
rmtree=ft.partial(shutil.rmtree, ignore_errors=True)


load_dotenv()

# Manually expand ${VAR} references — python-dotenv interpolation
# fails on Windows when values contain backslash paths.
_interpolation_re = re.compile(r'\$\{([^}]+)\}')
for _key in ('TMP_DIR', 'LOG_DIR', 'DATA_DIR', 'CKPT_DIR'):
    _val = os.environ.get(_key, '')
    if '${' in _val:
        os.environ[_key] = _interpolation_re.sub(
            lambda m: os.environ.get(m.group(1), m.group(0)), _val
        )

tmp_dir = os.getenv('TMP_DIR')
state_dir = pjoin(tmp_dir, '.state')
mkdirs(state_dir)


DEFAULT_CONFIG_PATH = pjoin(PROJECT_ROOT, 'configs', 'default.yaml')

assert pexists(DEFAULT_CONFIG_PATH), f'Default config file not found: {DEFAULT_CONFIG_PATH}'

def dt_now_str(format: str = '%Y%m%d_%H%M%S'):
    return dt.datetime.now().strftime(format)

def load_json(file,default={}):
    if not pexists(file):
        if default is None:
            raise FileNotFoundError(f'File {file} not found')
        return default
    with open(file, encoding='utf-8') as f:
        return json.load(f)
    
def load_jsonl(file, default=None):
    if not pexists(file):
        return default
    with open(file, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]
    
def save_json(file,data,indent=4): 
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent)

def load_yaml(file,default={}):
    if not pexists(file):
        if default is None:
            raise FileNotFoundError(f'File {file} not found')
        return default
    with open(file, encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_csv(file,default=None,skiprows=0):
    if not pexists(file):
        return default
    with open(file, encoding='utf-8') as f:
        return pd.read_csv(f,skiprows=skiprows)
    
def read_file(file_path, default=None):
    if not pexists(file_path):
        if default is None:
            raise FileNotFoundError(f'File {file_path} not found')
        return default
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def dts_to_dt(dts):
    formats =[
        '%Y-%m-%dT%H:%M:%SZ',   
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d',
    ]
    for format in formats:
        try:
            return dt.datetime.strptime(dts,format)
        except:
            pass
    raise ValueError(f'Invalid date string: {dts}')

def save_state(state_name: str, state: dict):
    state_file = pjoin(state_dir, f"{state_name}.json")
    save_json(state_file, state)

def load_state(state_name: str):
    state_file = pjoin(state_dir, f"{state_name}.json")
    if pexists(state_file):
        return load_json(state_file)
    return {}

def get_days(time_horizon):
    if time_horizon is None:
        return None
    elif isinstance(time_horizon, int):
        return time_horizon
    elif isinstance(time_horizon, str):
        time_horizon = time_horizon.lower()
        if time_horizon == '1d':
            return 1
        elif time_horizon == '1w':
            return 7
        elif time_horizon == '1m':
            return 30
        elif time_horizon == '3m':
            return 90
        elif time_horizon == '6m':
            return 180
        elif time_horizon == '1y':
            return 365
        else:
            raise ValueError(f'Invalid time horizon: {time_horizon}')
    else:
        raise ValueError(f'Invalid time horizon type: {type(time_horizon)}')
    
def to_str_span(span_days: int):
    str_span = {
        365: 'one year',
        180: 'half year',
        90: 'one quarter',
        30: 'one month',
        14: 'two weeks',
        7: 'one week',
        1: 'one day',
    }
    if span_days in str_span:
        return str_span[span_days]
    else:
        return f'{span_days} days'

def list2freq(lst: list, round_base: float = None, sort: bool = False):
    freq = {}
    for item in lst:
        if round_base is not None: # for float
            item = round(item, round_base)
        if item in freq:
            freq[item] += 1
        else:
            freq[item] = 1
    if sort:
        return dict(sorted(freq.items(), key=lambda x: x[0], reverse=False))
    return freq


def iteratively_set_default(config: dict, default_config: dict):
    for key, value in default_config.items():
        if isinstance(value, dict):
            if key not in config:
                config[key] = {}
            iteratively_set_default(config[key], value)
        else:
            if key not in config:
                config[key] = value
    return config

def load_config(config_path: str = None) -> dict:
    config = load_yaml(config_path, None) if config_path else None
    default_config = load_yaml(DEFAULT_CONFIG_PATH)
    if config is None:
        cprint(f'Config file {config_path} not found, using default config', 'r')
        return default_config
    config = iteratively_set_default(config, default_config)
    config['project_root'] = PROJECT_ROOT
    return config


def remove_ansi_codes(text: str) -> str:
  ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
  return ansi_escape.sub('', text)


def base64_to_image(base64_str: str) -> Image.Image:
    return Image.open(BytesIO(base64.b64decode(base64_str)))


def random_str(length: int = 10) -> str:
    return ''.join(random.sample(uuid.uuid4().hex, length))

def hash_str(seed: str, length: int = 10) -> str:
    return hashlib.sha256(seed.encode('utf-8')).hexdigest()[:length]

def idx2var(idx: int):
    k=idx//26
    r=idx%26
    tail = string.ascii_uppercase[r]
    return tail if k==0 else idx2var(k-1)+tail

def replace_special_chars(text: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]', '_', text)

def str_to_id(text: str, length: int = 100) -> str:
    """
    Convert a string to a unique identifier by removing special characters and truncating to a specified length.
    """
    text = remove_ansi_codes(text.replace(' ', '_').lower()).replace('\\', '_').replace('/', '_')
    return text[:length] if len(text) > length else text

def clean_and_backup(dir, backup_folder = '.backups'): # move everything in the directory to a backup folder
    backup_dir = pjoin(dir, backup_folder)
    mkdirs(backup_dir)
    n_backup = len(os.listdir(backup_dir)) 
    new_backup_dir = pjoin(backup_dir, f'backup_{n_backup + 1}_{dt_now_str()}')
    mkdirs(new_backup_dir)
    # move all files from the checkpoint directory to the new backup directory
    for item in os.listdir(dir):
        if item == backup_folder:
            continue
        item_path = pjoin(dir, item)
        shutil.move(item_path, new_backup_dir)
        while pexists(item_path): # wait until the move is complete
            time.sleep(0.1)


RESTRICTED_PORTS = [
    0,      # Not in Fetch Spec.
    1,      # tcpmux
    7,      # echo
    9,      # discard
    11,     # systat
    13,     # daytime
    15,     # netstat
    17,     # qotd
    19,     # chargen
    20,     # ftp data
    21,     # ftp access
    22,     # ssh
    23,     # telnet
    25,     # smtp
    37,     # time
    42,     # name
    43,     # nicname
    53,     # domain
    69,     # tftp
    77,     # priv-rjs
    79,     # finger
    87,     # ttylink
    95,     # supdup
    101,    # hostriame
    102,    # iso-tsap
    103,    # gppitnp
    104,    # acr-nema
    109,    # pop2
    110,    # pop3
    111,    # sunrpc
    113,    # auth
    115,    # sftp
    117,    # uucp-path
    119,    # nntp
    123,    # NTP
    135,    # loc-srv /epmap
    137,    # netbios
    139,    # netbios
    143,    # imap2
    161,    # snmp
    179,    # BGP
    389,    # ldap
    427,    # SLP (Also used by Apple Filing Protocol)
    465,    # smtp+ssl
    512,    # print / exec
    513,    # login
    514,    # shell
    515,    # printer
    526,    # tempo
    530,    # courier
    531,    # chat
    532,    # netnews
    540,    # uucp
    548,    # AFP (Apple Filing Protocol)
    554,    # rtsp
    556,    # remotefs
    563,    # nntp+ssl
    587,    # smtp (rfc6409)
    601,    # syslog-conn (rfc3195)
    636,    # ldap+ssl
    989,    # ftps-data
    990,    # ftps
    993,    # ldap+ssl
    995,    # pop3+ssl
    1719,   # h323gatestat
    1720,   # h323hostcall
    1723,   # pptp
    2049,   # nfs
    3659,   # apple-sasl / PasswordServer
    4045,   # lockd
    5060,   # sip
    5061,   # sips
    6000,   # X11
    6566,   # sane-port
    6665,   # Alternate IRC [Apple addition]
    6666,   # Alternate IRC [Apple addition]
    6667,   # Standard IRC [Apple addition]
    6668,   # Alternate IRC [Apple addition]
    6669,   # Alternate IRC [Apple addition]
    6697,   # IRC + TLS
    10080,  # Amanda
]

def get_available_ports(init_port: int = 3000, length = 2000):
    available_ports = []
    for port in range(init_port, min(65535,init_port+length)):
        if port in RESTRICTED_PORTS:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('localhost', port))
                available_ports.append(port)
            except OSError:
                pass
    if not available_ports:
        raise RuntimeError("No available ports found in the range.")
    return available_ports


def find_free_port(init_port: int = 3000, length = 2000) -> int:
    """
    Find a free port starting from init_port.
    """
    available_ports = get_available_ports(init_port, length)
    return random.choice(available_ports) 


def kill_process(pid: int):
    """
    Kill a process by its PID.
    """
    try:
        psutil.Process(pid).terminate()  # Graceful termination
        psutil.Process(pid).wait(timeout=5)  # Wait for the process to terminate
        return True
    except psutil.NoSuchProcess:
        cprint(f"Process {pid} does not exist.", 'g')
        return False
    except Exception as e:
        cprint(f"Failed to kill process {pid}: {e}", 'r')
        try:
            os.kill(pid, 9)  # Force kill if graceful termination fails
            return True
        except Exception as e:
            cprint(f"Failed to force kill process {pid}: {e}", 'r')
        return False


def copy_dir(source: str, to: str):
    """
    Copy a directory from one location to another.
    """
    try:
        shutil.copytree(source, to)
        return True
    except Exception as e:
        cprint(f"Failed to copy directory from {source} to {to}: {e}", 'r')
        return False



def directory_tree(dir_path: Path, level: int=-1, limit_to_directories: bool=False, length_limit: int=1000, 
        _str: str='', filter_by_path = [], filter_by_name = ['__pycache__'], read_files: bool = False) -> None: 
    # filter is the file to be ignored, by path is relative path, by name is the name of the file or directory
    """Given a directory Path object print a visual tree structure"""
    space =  '    '
    branch = '│   '
    tee =    '├── '
    last =   '└── '
    dir_path = Path(dir_path) # accept string coerceable to Path
    path_filter = [Path(os.path.join(dir_path, f)) for f in filter_by_path]
    files = 0
    directories = 0
    file_contents = {}
    def inner(dir_path: Path, prefix: str='', level=-1):
        nonlocal files, directories
        if not level: 
            return # 0, stop iterating
        if limit_to_directories:
            _contents = [d for d in dir_path.iterdir() if d.is_dir()]
        else: 
            _contents = list(dir_path.iterdir())
        contents =[]
        for c in _contents:
            if any(c == f for f in path_filter):
                continue
            if c.name in filter_by_name:
                continue
            contents.append(c)
            if read_files and c.is_file():
                try:
                    with c.open('r', encoding='utf-8') as f:
                        file_contents[str(c)] = f.read()
                except Exception as e:
                    file_contents[str(c)] = f'Error reading file: {e}'
        pointers = [tee] * (len(contents) - 1) + [last]
        for pointer, path in zip(pointers, contents):
            if path.is_dir():
                yield prefix + pointer + path.name
                directories += 1
                extension = branch if pointer == tee else space 
                yield from inner(path, prefix=prefix+extension, level=level-1)
            elif not limit_to_directories:
                yield prefix + pointer + path.name
                files += 1
    _str += f'{dir_path.name}:\n'
    iterator = inner(dir_path, level=level)
    for line in islice(iterator, length_limit):
        _str += line + '\n'
    if next(iterator, None):
        _str += f'... length_limit, {length_limit}, reached, counted:\n'
    _str += f'\n{directories} directories' + (f', {files} files' if files else '') + '\n'
    return _str if not read_files else (_str, file_contents)   



def ignore_by_abspaths(ignore_paths: List[str]):
    """
    Returns a function that can be used as the `ignore` callable for shutil.copytree.
    The returned function will ignore any file or directory whose absolute path
    is present in the `ignore_paths` list.
    """
    # Normalize and create a set for efficient lookup
    normalized_ignore_paths = {os.path.normpath(path) for path in ignore_paths}

    def _ignore(directory: str, contents: List[str]) -> Set[str]:
        """
        The actual ignore function called by shutil.copytree.
        """
        ignored_items = set()
        for item in contents:
            full_path = os.path.normpath(os.path.join(directory, item))
            if full_path in normalized_ignore_paths:
                ignored_items.add(item)
        return ignored_items

    return _ignore


def log_error(message: str, type: str):
    """
    Log an error message to a specified log file.
    """
    tmp_dir = os.getenv('TMP_DIR', './tmp')
    log_dir = pjoin(tmp_dir, '.error', type)
    mkdirs(log_dir)
    log_file = pjoin(log_dir, f"{dt_now_str('%Y%m%d_%H%M%S')}_{random_str(4)}.log")
    with open(log_file, 'a', encoding='utf-8') as f:
        timestamp = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"[{timestamp}] ERROR: {message}\n")

