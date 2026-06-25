import atexit
import streamlit as st_original
import sys
import os
import uuid
import json
import inspect
import ast
from datetime import datetime
from contextlib import contextmanager
from enum import Enum
from functools import wraps


class LogType(Enum):
    META = "meta"
    ACTION = "action"
    TREE = "tree"

class NodeType(Enum):
    ROOT = "root" # the whole app, a virtual root node
    PAGE = "page"
    FUNC = "func" # functions, can be any functions
    CONTEXT = "context" # context managers like containers, etc.
    WIDGET = "widget" 

class MetaLog(Enum):
    SESSION_START = "SESSION_START"
    DEFAULT_PAGE = "DEFAULT_PAGE"
    BASE_DIR = "BASE_DIR"
    


STREAMLIT_CONTEXT_MANAGERS = {"expander", "container", "form", "sidebar", "Column",
                            "popover","echo","chat_message","status","spinner"}


class SourceParser:
    def __init__(self, filepath):
        self.filepath = filepath
        self.coverage_map = {}
        with open(filepath, 'r') as f:
            source = f.read()
        self.tree = ast.parse(source)
        self._walk_tree(self.tree)

    def _walk_tree(self, node):
        """Recursively walk the AST to map start lines to end lines."""
        if hasattr(node, 'lineno'):
            start_line = node.lineno
            end_line = getattr(node, 'end_lineno', start_line)
            self.coverage_map[start_line] = end_line
        for child in ast.iter_child_nodes(node):
            self._walk_tree(child)

    def get_end_line(self, start_line):
        return self.coverage_map.get(start_line, start_line)
    

class SourceCache:
    _cache = {} # Cache ASTs by filename: { "path/to/file.py": AST_tree }
    _coverage_maps = {} # Cache coverage maps: { "path/to/file.py": {start_line: end_line} }
    _ast_cache = {}
    _function_defs = {}
    _scanned_files = set() # Track scanned files to avoid re-scanning

    @classmethod
    def _parse_file(cls, filepath):
        if not filepath or filepath in cls._ast_cache: return
        try:
            with open(filepath, 'r') as f: source = f.read()
            tree = ast.parse(source); cls._ast_cache[filepath] = tree
            coverage_map = {}; function_defs = {}
            for node in ast.walk(tree):
                if hasattr(node, 'lineno'):
                    start, end = node.lineno, getattr(node, 'end_lineno', node.lineno)
                    if isinstance(node, (ast.With, ast.FunctionDef, ast.AsyncFunctionDef)):
                        coverage_map[start] = end
                        if isinstance(node, ast.FunctionDef):
                            func_coverage = f"{filepath}:{start}->{end}"
                            function_defs[node.name] = {"coverage": func_coverage, "source": ast.get_source_segment(source, node)}
                    elif start not in coverage_map: coverage_map[start] = end
            cls._coverage_maps[filepath] = coverage_map; cls._function_defs[filepath] = function_defs
        except Exception: 
            cls._ast_cache[filepath], cls._coverage_maps[filepath], cls._function_defs[filepath] = None, {}, {}
    

    @classmethod
    def get_end_line(cls, filepath, start_line):
        """Gets the end line for a given start line from the correct file's cache."""
        if filepath not in cls._cache:
            cls._parse_file(filepath)
        return cls._coverage_maps.get(filepath, {}).get(start_line, start_line)

    @classmethod
    def get_function_coverage(cls, func):
        try:
            func_file = inspect.getsourcefile(func)
            if not func_file or not os.path.exists(func_file): return None, None
            if func_file not in cls._cache:
                with open(func_file, 'r') as f:
                    source = f.read()
                cls._cache[func_file] = ast.parse(source)
            
            tree = cls._cache[func_file]
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == func.__name__:
                    return node.lineno, node.end_lineno
        except (TypeError, OSError):
            pass
        return None, None
    
    @classmethod
    def get_function_definitions(cls, filepath):
        if filepath not in cls._ast_cache: 
            cls._parse_file(filepath)
        return cls._function_defs.get(filepath, {})

    @classmethod
    def scan_source_file(cls, tracer: "Tracer", filepath: str):
        if filepath in cls._scanned_files: return
        print(f"Scanning source file: {filepath}")
        defined_funcs = SourceCache.get_function_definitions(filepath)
        for func_name, func_info in defined_funcs.items():
            if func_name not in tracer.page_function_names:
                tracer.register_tree_node(
                    coverage=func_info["coverage"], component_type=f"Function: {func_name}",
                    level=NodeType.FUNC, source_code=func_info["source"], args=[], kwargs={}
                )
        cls._scanned_files.add(filepath)

    
    
class Tracer:
    """The new singleton that manages the component stack and all logging."""
    _instance = None
    _component_registry = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Tracer, cls).__new__(cls)
            cls._instance.meta_log_file = None
            cls._instance.action_log_file = None
            cls._instance.tree_log_file = None
            cls._instance.component_stack = [] # Stack now stores coverage strings
            cls._instance.source_parser = None
            cls._instance.page_function_names = set()
            atexit.register(cls._instance.save_tree_log)
        return cls._instance

    def configure(self, app_script_path: str, log_dir: str, flush: bool = True):
        os.makedirs(log_dir, exist_ok=True)
        self.meta_log_file = os.path.join(log_dir, "meta.jsonl")
        self.action_log_file = os.path.join(log_dir, "actions.jsonl")
        self.tree_log_file = os.path.join(log_dir, "tree.jsonl")
        self.source_parser = SourceParser(app_script_path) # Parse the app script
        if flush:
            open(self.meta_log_file, "w").close()
            open(self.action_log_file, "w").close()
            open(self.tree_log_file, "w").close()

        if "___session_started" not in st_original.session_state:
            self.log_meta(MetaLog.SESSION_START, {"timestamp": datetime.now().isoformat()})
            app_script_full_path = os.path.abspath(app_script_path)
            self.log_meta(MetaLog.BASE_DIR, {"base_dir": os.path.dirname(app_script_full_path)})
            st_original.session_state.___session_started = True


    def _log(self, file_path, data):
        if not file_path: return
        log_entry = json.dumps(data, default=str)
        # print(f"Logging to {file_path}: {log_entry}")
        with open(file_path, "a") as f: f.write(log_entry + "\n")

    def log_meta(self, meta_type, value):
        self._log(self.meta_log_file, {"type": LogType.META.value, "meta_type": meta_type.value, "value": value})

    def log_action(self, path, action_type, value):
        self._log(self.action_log_file, {
            "type": LogType.ACTION.value,
            "timestamp": datetime.now().isoformat(),
            "path": path,
            "action": action_type,
            "value": value
        })

    def register_tree_node(self, coverage, component_type, level, source_code, args, kwargs):
        if "unknown:" in coverage:
            return coverage  # Skip unknown components
        
        parent_path = self.component_stack[-1] if self.component_stack else NodeType.ROOT.value
        path = f"{parent_path} > {coverage}"

        self._component_registry[path] = {
            "id": coverage,
            "level": level,
            "component": component_type,
            "parent_path": parent_path,
            "source_code": source_code,
            "params": {"args": args, "kwargs": kwargs}
        }
        self.save_tree_log()
        return path

    def save_tree_log(self):
        tree_data = {"type": LogType.TREE.value, "tree": self._component_registry}
        with open(self.tree_log_file, "w") as f:
            json.dump(tree_data, f, indent=2, default=str)



class TracerWrapper:
    def __init__(self, original_streamlit_module, tracer: Tracer):
        self.stream = original_streamlit_module
        self.tracer = tracer
        self.tracer_filepath = os.path.abspath(__file__)
        self.tracer_filename = os.path.basename(__file__)
        self.stdlib_path = os.path.dirname(os.path.abspath(os.__file__))
        self.site_packages_paths = [os.path.abspath(p) for p in sys.path if 'site-packages' in p]

    def get_coverage(self, func):
        start_line, end_line = SourceCache.get_function_coverage(func)
        if start_line and end_line:
            filepath = inspect.getsourcefile(func)
            SourceCache.scan_source_file(self.tracer, filepath)

            coverage = f"{filepath}:{start_line}->{end_line}"
            source = inspect.getsource(func)
        else:
            coverage, source = self._get_component_info(func.__name__)
        return coverage, source

    def _get_component_info(self, name):
        """
        Gets component call site info by inspecting the call stack.
        This is the new, robust method for finding user code.
        """
        for frame_info in inspect.stack(context=1):
            filepath = os.path.abspath(frame_info.filename)

            # Robustly check if the frame is from the tracer, stdlib, or site-packages
            is_tracer_file = (filepath == self.tracer_filepath)
            is_stdlib_file = filepath.startswith(self.stdlib_path)
            is_site_packages_file = any(filepath.startswith(p) for p in self.site_packages_paths)

            if is_tracer_file or is_stdlib_file or is_site_packages_file:
                continue

            SourceCache.scan_source_file(self.tracer, filepath)

            lineno = frame_info.lineno
            end_lineno = SourceCache.get_end_line(filepath, lineno)
            coverage = f"{filepath}:{lineno}->{end_lineno}"
            source_code = (frame_info.code_context[0] if frame_info.code_context else "").strip()
            return coverage, source_code
    
    def __getattr__(self, name):
        original_attr = getattr(self.stream, name)
        if not callable(original_attr):
            return original_attr

        # self.tracer.save_tree_log()
        original_func = original_attr        
        
        
        if name == "Page":
            def page_constructor_wrapper(page_function, *args, **kwargs):
                page_title = kwargs.get("title", page_function.__name__)
                coverage, source = self.get_coverage(page_function)

                path = self.tracer.register_tree_node(coverage, f"st.{name}", NodeType.PAGE, source, args, kwargs)

                # This factory function creates a new, uniquely named wrapper for each page
                def create_page_execution_wrapper(original_func, title):
                    def page_execution_wrapper():
                        previous_page = self.stream.session_state.get("___previous_page_title", None)
                        if previous_page != title:
                            # We only log a switch *after* the first page has been established
                            if previous_page is not None:
                                self.tracer.log_action("navigation", "page_switch", {"from": previous_page, "to": title})
                        self.stream.session_state["___previous_page_title"] = title
                        return original_func()
                    page_execution_wrapper.__name__ = original_func.__name__
                    return page_execution_wrapper

                # Create the uniquely named wrapper
                wrapped_func = create_page_execution_wrapper(page_function, page_title)
                
                # Log default page meta-data
                if "___page_tracker_initialized" not in self.stream.session_state:
                    self.tracer.log_meta(MetaLog.DEFAULT_PAGE, page_title)
                    self.stream.session_state["___previous_page_title"] = page_title
                    self.stream.session_state["___page_tracker_initialized"] = True

                # Return a new Page object with our uniquely named, wrapped function
                return original_func(wrapped_func, *args, **kwargs)
            return page_constructor_wrapper
        
        elif name in STREAMLIT_CONTEXT_MANAGERS:
            @contextmanager
            @wraps(original_func)
            def context_wrapper(*args, **kwargs):
                # Directly get component info from the call stack
                coverage, source_code = self._get_component_info(name)
                path = self.tracer.register_tree_node(coverage, f"st.{name}", NodeType.CONTEXT, source_code, args, kwargs)
                self.tracer.component_stack.append(path)
                try:
                    with original_func(*args, **kwargs) as context_obj:
                        yield context_obj
                finally:
                    self.tracer.component_stack.pop()
            return context_wrapper
        
        else: # For all other regular functions
            @wraps(original_func)
            def generic_wrapper(*args, **kwargs):
                coverage, source_code = self._get_component_info(name)
                path = self.tracer.register_tree_node(coverage, f"st.{name}", NodeType.WIDGET, source_code, args, kwargs)
                
                sig = inspect.signature(original_func)
                if "on_click" in sig.parameters:
                    if callable(kwargs.get("on_click")): # wrap existing callback
                        user_cb = kwargs["on_click"]
                        def cb_wrapper(*a, **kw):
                            self.tracer.log_action(path, "on_click", True)
                            user_cb(*a, **kw)
                        kwargs["on_click"] = cb_wrapper
                    else: # add new callback
                        def cb(): self.tracer.log_action(path, "on_click", True)
                        kwargs["on_click"] = cb
                elif "on_change" in sig.parameters:
                    key = kwargs.get("key", coverage)
                    kwargs["key"] = key
                    if callable(kwargs.get("on_change")):
                        user_cb = kwargs["on_change"]
                        def cb_wrapper(*a, **kw):
                            self.tracer.log_action(path, "on_change", self.stream.session_state.get(key))
                            user_cb(*a, **kw)
                        kwargs["on_change"] = cb_wrapper
                    else:
                        def cb(): self.tracer.log_action(path, "on_change", self.stream.session_state.get(key))
                        kwargs["on_change"] = cb
                return original_func(*args, **kwargs)
            return generic_wrapper

def activate_tracer(app_script_path: str, log_dir: str, flush: bool = True):
    if 'streamlit' in sys.modules and isinstance(sys.modules['streamlit'], TracerWrapper): return
    tracer_instance = Tracer()
    tracer_instance.configure(app_script_path, log_dir, flush)
    sys.modules['streamlit'] = TracerWrapper(st_original, tracer_instance)

