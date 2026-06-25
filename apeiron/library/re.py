from apeiron.library.modules import PROXY_REGISTRY
from apeiron.const import BASIC_PROXIES
import inspect
import argparse
import requests
import apeiron.utils as U
import os
from typing import List
import datetime as dt
from dataclasses import dataclass
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
import random
import numpy as np
import pandas as pd
from itertools import combinations
from sllm.proxies import BaseProxy



class Library:
    """
    Library Runtime Environment

    This class is used to proxy API requests to the appropriate API.
    bind_libraries: the list of proxies to activate, if None, then use the default proxies
    """
    def __init__(self, bind_libraries: List[str] = None):
        self.proxies: dict[str, BaseProxy] = {}
        self.registry: dict[str, dict] = {}
        if bind_libraries is None:
            bind_libraries = BASIC_PROXIES
        # U.cprint(f"Activating libraries: {bind_libraries}", color='y')
        self.bind_libraries = bind_libraries
        for proxy_name in bind_libraries:
            proxy: BaseProxy = PROXY_REGISTRY[proxy_name]
            try:
                self.proxies[proxy._proxy_path] = proxy()
                self.proxies[proxy._proxy_path]._proxy_path = proxy._proxy_path
            except Exception as e:
                U.cprint(f"Error initializing proxy {proxy._proxy_path}: {e}", color='r')
                continue
            self.registry[proxy._proxy_path] = {
                'name': proxy._proxy_name,
                'description': proxy._proxy_description,
                'doc_string': inspect.getdoc(proxy),
            }

    def reload(self, bind_libraries: List[str] = None):
        self.__init__(bind_libraries)
        return self

    def to_dict(self):
        return {
            'bind_libraries': self.bind_libraries,
        }

    @classmethod
    def from_dict(cls, d: dict): return cls(**d)

    def parse_path(self, full_path: str):
        try:
            proxy_path, endpoint = full_path.split('/', maxsplit=1)
            return proxy_path, endpoint
        except ValueError as e:
            raise ValueError(f"Failed to parse path: {full_path}, {e}")

    def __call__(self, full_path: str, params: dict) -> dict:
        proxy_path, endpoint = self.parse_path(full_path)
        return self.proxies[proxy_path](endpoint, params)
    
    def prompt_proxy(self): # prompt the agent to choose the best proxy and api
        raise NotImplementedError("This method should be implemented by the subclass")

    def auto_test(self, proxy_path: str = None, skip_k: int = 0):
        test_proxies = proxy_path.split(',') if proxy_path else self.proxies.keys()
        for proxy in test_proxies:
            self.proxies[proxy].auto_test(skip_k)

    def _prompt_api(self, proxy_path: str, indent = '', additional_doc: bool = True):
        _data = self.registry[proxy_path]
        _proxy = self.proxies[proxy_path]
        _prompt = f''
        for key in _data:
            if key != 'doc_string':
                _prompt += f'{indent} - {key}: {_data[key]}\n'
            else:
                _space = indent*2+'   '
                lines = [_space+i for i in _data[key].split('\n')]
                _prompt += f'{indent} - doc string:\n{_space}---\n{'\n'.join(lines)}\n{_space}---\n' 
                if additional_doc:
                    _additional_doc = _proxy.additional_doc(indent=_space+'  ')
                    _prompt += f'{indent} - additional doc:\n{_additional_doc}\n'
        _prompt += '\n'
        return _prompt

    @property
    def api_catalog(self):
        _prompt = 'API catalog:\n'
        for proxy in self.registry:
            _prompt += f' - {proxy}\n'
            _prompt += self._prompt_api(proxy, indent='  ')
        return _prompt
    
    @property
    def call_directory(self, by_cat: bool = False):
        _prompt = 'Endpoint directory for each API:\n'
        for _api_path, _proxy in self.proxies.items():
            _prompt += f' - {_api_path}\n'
            _prompt += _proxy.endpoint_directory(indent='  ', by_cat=by_cat)
        return _prompt

    @property
    def api_directory(self):
        _prompt = 'API directory:\n'
        indent = '  '
        for proxy in self.registry:
            _prompt += f' - {proxy}\n'
            _prompt += self._prompt_api(proxy, indent=indent)
            _prompt += f'{indent} - endpoints:\n'
            _proxy = self.proxies[proxy]
            _prompt += _proxy.endpoint_directory(indent=indent*2)
        return _prompt
    
    def _api_prompt(self,full_path: str, indent: str = ''):
        proxy_path, endpoint = self.parse_path(full_path)
        _proxy = self.proxies[proxy_path]
        _data = _proxy.registry[endpoint]
        _prompt = f'{indent} - {full_path}\n'
        if _data["name"]:
            _prompt += f'{indent}    - name: {_data["name"]}\n'
        _prompt += f'{indent}    - category: {_data["category"]}\n'
        if _data["sub_category"]:
            _prompt += f'{indent}    - sub_category: {_data["sub_category"]}\n'
        _prompt += f'{indent}    - description: {_data["description"]}\n'
        if _data["doc_string"].strip():
            _indent = '      '+indent
            lines = [_indent+i for i in _data["doc_string"].strip().split('\n')]
            _prompt += f'{indent}    - doc_string:\n{_indent}---\n{'\n'.join(lines)}\n{_indent}---\n'
        _params = _data["params"]
        _prompt += f'{indent}    - params:\n'
        for param in _params:
            _indent = '        '+indent
            _type, _example = _params[param]
            _type = _type.__name__ if _type!='date' else 'str (date)'
            _required = param.endswith('*')
            param = param.replace('$', '').replace('*', '').replace('#', '')
            _required = ' (required)' if _required else ''  
            _prompt += f'{_indent}"{param}": type: {_type}, example: {_example}{_required}\n'
        _prompt += f'{indent}    - example response: {_data["response"]}\n'
        return _prompt

    def retrieve_api_docs(self,full_paths: str | List[str], additional_doc: bool = False): # if include additional doc in directory already, then set additional_doc to False, by default its in directory already
        paths = {}
        if isinstance(full_paths, str):
            full_paths = [full_paths]
        self.check_paths(full_paths)
        for full_path in full_paths:
            proxy_path, _ = self.parse_path(full_path)
            if proxy_path not in paths:
                paths[proxy_path] = []
            paths[proxy_path].append(full_path)
        _prompt = 'Endpoint details:\n'
        for proxy_path in paths:
            _proxy = self.proxies[proxy_path]
            _prompt += f' - {proxy_path}:\n'
            for full_path in paths[proxy_path]:
                _prompt += self._api_prompt(full_path, indent='  ')
            _prompt += '\n'
            if additional_doc and len(_proxy.additional_docs) > 0:
                _prompt += f'   * Additional documentation for {proxy_path} APIs:\n'
                _prompt += _proxy.additional_doc(indent='     ')
            _prompt += '\n'
        return _prompt

    def check_paths(self, paths: List[str]):
        if isinstance(paths, str):
            paths = [paths]
        errors = []
        for path in paths:
            proxy_path, endpoint = self.parse_path(path)
            if proxy_path not in self.proxies:
                errors.append(f"Invalid path: {path}, {proxy_path} not found in the proxy registry")
            if endpoint not in self.proxies[proxy_path].registry:
                errors.append(f"Invalid path: {path}, {endpoint} not found in the registry of {proxy_path}")
        if errors:
            raise ValueError(f"Invalid paths:\n{'\n'.join(errors)}\nPlease check the paths and try again. Remember to use the *full path* of the API from the *API directory*.")
        return True







if __name__ == "__main__":
    # args
    parser = argparse.ArgumentParser()
    parser.add_argument("--test_lib", "-tp", type=str, default=None)
    parser.add_argument("--skip_k", "-s", type=int, default=0)
    parser.add_argument("--config", "-cfg", type=str, default='base')
    args = parser.parse_args()

    config = U.load_config(U.pjoin('configs', f'{args.config}.yaml'))

    if args.test_lib:
        proxy = Library(bind_libraries=config['bind_libraries'])
        path = args.test_lib if args.test_lib != 'all' else None
        proxy.auto_test(path, args.skip_k)
