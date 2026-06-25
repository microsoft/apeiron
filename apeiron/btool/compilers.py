import asyncio
import shlex
import json
import traceback
import apeiron.utils as U
import psutil
from dataclasses import dataclass
from sllm.models import ParseError, default_parser
from sllm.utils import check_item, find_level1_blocks_sorted
from typing import Dict, Any, List
from playwright.async_api import async_playwright
import datetime as dt
import time
import os
import subprocess
import venv
import shutil
import stat
import sys
from sllm.tools.cua import OpenAICUA
from apeiron.btool.ir import ACTDiff, FolderDiff


current_dir = os.path.dirname(os.path.abspath(__file__))
streamlit_template_dir = U.pjoin(current_dir, 'streamlit_template')
# streamlit_injector_dir = U.pjoin(current_dir, 'streamlit_injector.py')
stracelit_dir = U.pjoin(current_dir, 'streamlit_tracer')


def copy_stracelit(destination_dir):
    U.mkdirs(destination_dir)
    stracelit_folder = U.pjoin(stracelit_dir, 'stracelit')
    shutil.copytree(stracelit_folder, U.pjoin(destination_dir, 'stracelit'), dirs_exist_ok=True)
    with open(U.pjoin(stracelit_dir, 'pyproject.toml'), 'r', encoding='utf-8') as f:
        with open(U.pjoin(destination_dir, 'pyproject.toml'), 'w', encoding='utf-8') as ft:
            ft.write(f.read())
    with open(U.pjoin(stracelit_dir, 'setup.py'), 'r', encoding='utf-8') as f:
        with open(U.pjoin(destination_dir, 'setup.py'), 'w', encoding='utf-8') as ft:
            ft.write(f.read())

def install_stracelit(venv_path: str = None):
    # run pip install -e . in the stracelit directory
    if venv_path:
        python_executable = U.pjoin(venv_path, 'bin', 'python') if os.name != 'nt' else U.pjoin(venv_path, 'Scripts', 'python.exe')
    else:
        python_executable = sys.executable
    _stracelit_dir = U.pjoin(venv_path, '.apeiron', 'streamlit_tracer')
    copy_stracelit(_stracelit_dir)
    command = [python_executable, '-m', 'pip', 'install', _stracelit_dir]
    try:
        subprocess.run(command, check=True, text=True)
        U.cprint("Stracelit installed successfully.", 'g')
    except subprocess.CalledProcessError as e:
        U.cprint(f"Error occurred while installing Stracelit: {e}", 'r')
        traceback_str = traceback.format_exc()
        raise RuntimeError(f"\nFailed to install Stracelit: {e}\n\n{traceback_str}")


async def install_stracelit_async(venv_path: str = None):
    # Determine python executable path
    if venv_path:
        python_executable = U.pjoin(venv_path, 'bin', 'python') if os.name != 'nt' else U.pjoin(venv_path, 'Scripts', 'python.exe')
    else:
        python_executable = sys.executable
        
    _stracelit_dir = U.pjoin(venv_path, '.apeiron', 'streamlit_tracer')
    
    # 1. Run the blocking file I/O in a separate thread
    await asyncio.to_thread(copy_stracelit, _stracelit_dir)
    
    # 2. Run the subprocess asynchronously
    command = [python_executable, '-m', 'pip', 'install', _stracelit_dir]
    
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        error_message = stderr.decode().strip()
        U.cprint(f"Error occurred while installing Stracelit: {error_message}", 'r')
        raise RuntimeError(f"Failed to install Stracelit: {error_message}")
    else:
        U.cprint("Stracelit installed successfully.", 'g')

@dataclass
class CheckReport:
    passed: bool
    message: str = None 

    def to_dict(self) -> Dict[str, Any]:
        return {
            'passed': self.passed,
            'message': self.message
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckReport':
        return cls(
            passed=data['passed'],
            message=data.get('message', None)
        )



class CompilerBase:
    def __init__(self, build_state, bind_libraries: List[str] = None):
        self.state = build_state
        self.bind_libraries = bind_libraries if bind_libraries else []

    @property
    def app_output_file(self) -> str:
        return U.pjoin(self.state.app_dir, 'app_output.log')

    def init(self):
        raise NotImplementedError("This method should be implemented by subclasses.")

    async def _run_app(self, output_file=None, **kwargs) -> int:
        raise NotImplementedError("This method should be implemented by subclasses.")

    async def run_app(self, output_file=None, **kwargs) -> int:
        """
        Run the app in the app directory.
        """
        app_dir = self.state.app_dir
        if not U.pexists(app_dir):
            raise FileNotFoundError(f"App directory {app_dir} does not exist. Please initialize the app first.")
        try:
            if not output_file:
                output_file = self.app_output_file
            self.prepare_re()
            return await self._run_app(output_file=output_file, **kwargs)
        except Exception as e:
            raise RuntimeError(f"Failed to run the app in {app_dir}. Error: {e}")

    
    def app_running(self) -> bool:
        raise NotImplementedError("This method should be implemented by subclasses.")
    
    def check(self, **kwargs) -> CheckReport:
        raise NotImplementedError("This method should be implemented by subclasses.")
    
    def read_output(self, output_file=None) -> str:
        if not output_file:
            output_file = self.app_output_file
        if not U.pexists(output_file):
            return f"Output file {output_file} does not exist."
        with open(output_file, 'r', encoding='utf-8') as f:
            return f.read()

    def get_temp_output_file(self, flush = True) -> str:
        """
        Get a temporary output file path for the app output.
        This is useful for checking the app output without overwriting the main output file.
        """
        _temp_output_dir = U.pjoin(self.state.appspace_dir, 'temp_output')
        U.mkdirs(_temp_output_dir)
        _temp_output_file = U.pjoin(_temp_output_dir, f'_temp_{U.dt_now_str()}_{U.random_str(6)}.log')
        if flush:
             open(_temp_output_file, 'w', encoding='utf-8').write('')
        return _temp_output_file

    def prepare_re(self):
        re_content = f"""import sys
sys.path.append('{U.PROJECT_ROOT}')
from apeiron.library.re import Library
library = Library(bind_libraries={self.bind_libraries})
CALL_API = library.__call__
""" 
        if os.name == 'nt':  # Windows
            re_content = re_content.replace('\\', '/')
        re_path = U.pjoin(self.state.app_dir, 'apeiron_re.py')
        with open(re_path, 'w', encoding='utf-8') as f:
            f.write(re_content)


class ReflexCompiler(CompilerBase):

    def __init__(self, build_state, bind_libraries = None):
        super().__init__(build_state, bind_libraries)
        raise NotImplementedError("ReflexCompiler needs update.")
    
    async def _run_app(self, output_file=None, dev_mode=True, **kwargs) -> int:
        """
        Run the app in the app directory.
        """
        command = ["reflex", "run"]
        if not dev_mode:
            command += ["--env", "prod"]
        with open(output_file, 'w', encoding='utf-8') as f:
            process = subprocess.Popen(
                command,
                cwd=self.state.app_dir,
                text=True,
                # shell=True,
                stdout=f,  # Redirect standard output to the file
                stderr=subprocess.STDOUT  # Redirect standard error to the same file as stdout
            )
        return process.pid
    
    def static_check(self):
        app_py = U.pjoin(self.state.app_dir, 'app', 'app.py')
        if not U.pexists(app_py):
            return CheckReport(False, f"App file `app.py` does not exist in the `app/` directory. Please ensure the app is correctly set up.")
        _current_dir = os.getcwd()
        os.chdir(self.state.app_dir)
        try:
            from app.app import app  # Import the app module to check for syntax errors
            pages = app._unevaluated_pages
            if len(pages) == 0:
                return CheckReport(False, "No pages found in the app. Please ensure you have added the pages to the app using `app.add_page(...)`.")
        except Exception as e:
            return CheckReport(False, f'''Error occurred while performing the static check: 
Trying to perform `from app import app` in the `app/` directory under the project root `{self.state.app_dir}`, but got an error:

{e}

''')
        finally:
            os.chdir(_current_dir)

        return CheckReport(True, "App is valid.")

    def app_running(self) -> bool:
        output = self.read_output()  # read the final output after the process is done
        if not 'App Running' in output:
            return False
        if not 'App running at: ' in output:
            return False
        if not 'Backend running at: ' in output:
            return False
        return True
        
    async def check(self, **kwargs) -> CheckReport: # just check if build succeed
        # flush the output file before running the app
        if U.pexists(self.app_output_file):
            with open(self.app_output_file, 'w', encoding='utf-8') as f:
                f.write('')
        pid = await self.run_app(dev_mode=False)  # run the app to check if it is deliverable, check in production mode
        _passed = True  # assume the app is valid
        _last_output = self.read_output()
        last_refresh = dt.datetime.now()
        max_wait_time = 120  # maximum wait time in seconds
        note = ''
        static_check_report = self.static_check()
        if not static_check_report.passed:
            return static_check_report  # if static check failed, return the report immediately
        while True:
            try:
                psutil.Process(pid)  # check if the process is still running
                output = self.read_output()
                if output != _last_output:  # if the output has changed, update the last output
                    _last_output = output
                    last_refresh = dt.datetime.now()
                if self.app_running():  # if the app is running, we can stop checking
                    break
                if dt.datetime.now() - last_refresh > dt.timedelta(seconds=max_wait_time):
                    _passed = False
                    note = f"\n\n(App seems not start running and frozen for {max_wait_time} seconds. The system forcely stopped the process.)"
                    break
                await asyncio.sleep(1) # <-- NON-BLOCKING CALL
            except psutil.NoSuchProcess:
                _passed = False
                break
        if not self.app_running():
            _passed = False
        U.kill_process(pid)  # kill the process after checking
        return CheckReport(_passed, message=output+note)  

    def init(self):
        U.mkdirs(self.state.app_dir)
        command = ["reflex", "init", "--template", "blank"]
        subprocess.run(
            command,
            cwd=self.state.app_dir,
            check=True,
            text=True,
            shell=True  
        )




_CHECK_CUA_SYSTEM = """You are working in a software testing team. 
Your task is to test the webapp developed by the developers.
You will be given an webapp and you need to try all the ways to use the app, 
and interact with any elements on the webapp.
You should also try your best to find any bugs or issues in the webapp.
At the end, you should also provide a summary of the testing process and the results.
"""


_CHECK_CUA_PROMPT = """Please test the webapp, try all the ways to use the app, and interact with any elements on the webapp.
"""

_CHECK_CUA_CONCLUDE = """Please conclude whether the app is functional well or not, and if there are any issues or bugs found.
In the end, you should return a JSON object wrapped in a ```json``` block with the following keys:

```json
{
  "decision": "pass" | "fail",  # whether the app is functional well or not
  "explanation": "string", # a detailed explanation of the decision
  "comments": "string" # any additional comments or suggestions
}
```

Please be detailed in your explanation and comments, and make sure to provide a single JSON object. 
Also, do not just give the JSON object directly, but provide a summary, analysis, and reasoning first before the final JSON object.
"""



def _cua_check_parser(message: str) -> dict:
    """
    Parse the conclusion from the CUA conclude prompt.
    """
    parsed = default_parser(message, md_tags=['json'])
    json_blocks = parsed['md_tags']['json']
    if len(json_blocks) != 1:
        raise ParseError("Please provide one and only one JSON block in your response.")
    try:
        json_data = json.loads(json_blocks[0].strip())
        if isinstance(json_data, list):
            assert len(json_data) == 1, "Please provide a single JSON object."
            json_data = json_data[0]
        required_keys = {'decision': str, 'explanation': str, 'comments': str}
        item = check_item(json_data, required_keys)
        if item['decision'] not in {'pass', 'fail'}:
            raise ParseError("The 'decision' key must be one of 'pass' or 'fail'.")
    except Exception as e:
        raise ParseError(f'Invalid JSON: {json_blocks[0]}, error: {e}')
    parsed['json'] = item
    parsed['analysis'] = parsed['raw'].replace(json_blocks[0], '(SKIPPED)').strip()
    return parsed


class StreamlitCompiler(CompilerBase):

    def init(self):
        U.mkdirs(self.state.app_dir)
        shutil.copytree(streamlit_template_dir, self.state.app_dir, dirs_exist_ok=True)

    def ensure_dependencies(self):  # Create a requirements.txt file if it doesn't exist
        requirements_path = U.pjoin(self.state.app_dir, 'requirements.txt')
        required_libraries = [
            'streamlit',
            # 'streamlit_navigation_bar',
            'pandas','numpy','plotly',
            'tqdm','pyparsing','tiktoken','filelock',
            'psutil','PyYAML','dotenv','pydantic'
        ]
        if not U.pexists(requirements_path):
            open(requirements_path, 'w', encoding='utf-8').write('')
        requirements = open(requirements_path, 'r', encoding='utf-8').readlines()
        cleaned_requirements = []
        for line in requirements:
            if line.startswith('#') or line.strip() == '':
                continue
            line = line.strip()
            if '#' in line:
                line = line.split('#',1)[0].strip()
            cleaned_requirements.append(line)
        cleaned_requirements = list(set(cleaned_requirements))  # remove duplicates
        for lib in required_libraries:
            if lib not in cleaned_requirements:
                cleaned_requirements.append(lib)
        requirements_content = '\n'.join(cleaned_requirements) + '\n'
        with open(requirements_path, 'w', encoding='utf-8') as f:
            f.write(requirements_content)


    def prepare_re(self):#, inject=True):
        super().prepare_re()
        self.ensure_dependencies()
        # self.inject_streamlit(inject=inject)  # inject or disinject the streamlit interceptor into the app directory

    @property
    def venv_dir(self) -> str:
        tmp_dir = os.environ['TMP_DIR']
        return U.pjoin(tmp_dir, '.venv')
    
    def python_executable(self, venv_path) -> str:
        if sys.platform == "win32":
            return U.pjoin(venv_path, "Scripts", "python.exe")
        else:
            return U.pjoin(venv_path, "bin", "python")

    def make_temp_venv(self, key=None) -> str:
        _NEED_INSTALL = False
        if key is None:
            key = U.dt_now_str()+'_'+U.random_str(8)  # generate a random key if not provided
        venv_path = U.pjoin(self.venv_dir, key)
        if U.pexists(venv_path): # for best stability
            shutil.rmtree(venv_path)  # remove the existing virtual environment
        U.mkdirs(venv_path)
        # U.cprint(f"Creating a temporary virtual environment at {venv_path}")
        venv.create(venv_path, with_pip=True)
        # Determine the path to the python executable within the venv
        # U.cprint(f"Temporary virtual environment created at {venv_path}", 'g')
        _NEED_INSTALL = True
        return venv_path, _NEED_INSTALL

    def install_requirements(self, python_executable: str):
        self.ensure_dependencies()
        requirements_path = U.pjoin(self.state.app_dir, 'requirements.txt')
        print(f"Installing requirements from {requirements_path}...")
        install_command = [str(python_executable), "-m", "pip", "install", "-r", requirements_path]
        try:
            subprocess.run(install_command, check=True, text=True)
            U.cprint("Requirements installed successfully.", 'g')
        except subprocess.CalledProcessError as e:
            U.cprint(f"Error occurred while installing requirements: {e}")
            raise RuntimeError(f"Failed to install requirements in the virtual environment: {e}")
        
    async def install_requirements_async(self, python_executable: str):
        self.ensure_dependencies()
        requirements_path = U.pjoin(self.state.app_dir, 'requirements.txt')
        print(f"Installing requirements from {requirements_path}...")
        install_command = [str(python_executable), "-m", "pip", "install", "-r", requirements_path]
        
        # Create the subprocess without blocking
        process = await asyncio.create_subprocess_exec(
            *install_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Wait for the subprocess to finish and capture output
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_message = stderr.decode().strip()
            U.cprint(f"Error occurred while installing requirements: {error_message}", 'r')
            raise RuntimeError(f"Failed to install requirements: {error_message}")
        else:
            U.cprint("Requirements installed successfully.", 'g')

    def app_running(self, output_file=None) -> bool:
        output = self.read_output(output_file)
        if not 'You can now view your Streamlit app in your browser.' in output:
            return False
        if not 'Local URL: ' in output:
            return False
        if not 'Network URL: ' in output:
            return False
        return True

    async def _run_app(self, output_file=None, use_venv=True, headless=False, trace_dir=None, port = None, **kwargs) -> int:
        """
        Run the app in the app directory.
        """
        # run in a temp virtual environment, install the requirements
        if not output_file:
            output_file = self.app_output_file
        if U.pexists(output_file):
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('')

        # TODO: handle stracelit tracing
        _exe = 'stracelit' if trace_dir else 'streamlit'
        _NEED_INSTALL = False

        if port is None:
            port = U.find_free_port(init_port=8000)
        # port = 0 # let os decide, avoid conflict
        port = str(port)  

        if use_venv:
            key = port # use port as unique key, one app one port one venv
                  # U.hash_str(self.state.app_dir)  # use the app directory hash as the key for the virtual environment
            venv_path, _NEED_INSTALL = self.make_temp_venv(key)  # create a temporary virtual environment
            python_executable = self.python_executable(venv_path)
            # current_permissions = os.stat(python_executable).st_mode
            # # Add execute permissions for the owner, group, and others
            # os.chmod(
            #     python_executable,
            #     current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            # )
            # if _NEED_INSTALL: # only install if the virtual environment is newly created
            await self.install_requirements_async(python_executable)
            await install_stracelit_async(venv_path)  # install stracelit in the virtual environment

            if os.name == 'nt':  # Windows
                _executable = python_executable.replace('python.exe', _exe+'.exe')
            else:  # Linux or macOS
                _executable = python_executable.replace('python', _exe)
            assert U.pexists(_executable), f"Executable {_executable} does not exist. Please ensure Streamlit is installed in the virtual environment."
            command = [_executable, "run", "app.py", "--server.port", str(port)]
        else:
            # if _NEED_INSTALL: 
            #     install_stracelit() 
            python_executable = sys.executable  # use the system Python executable
            command = [_exe, "run", "app.py", "--server.port", str(port)]
        if headless:
            command += ["--server.headless", "true"]
        if trace_dir:
            command += ["--log-dir", trace_dir]
        # if _NEED_INSTALL:
        #     U.cprint(f"Installing requirements...", 'b')
        #     self.install_requirements(python_executable)
        print(f"Running command: {' '.join(shlex.quote(arg) for arg in command)} in \"{self.state.app_dir}\"")
        output_handle = open(output_file, 'w', encoding='utf-8')
        app_process = await asyncio.create_subprocess_exec(
            *command,
            cwd=self.state.app_dir,
            # text=True,
            stdout=output_handle,
            stderr=output_handle
        )
        return app_process.pid, output_handle

    def running_url(self, output_file=None) -> str:
        assert self.app_running(output_file), "The app is not running. Please run the app first."
        output: str = self.read_output(output_file)
        for line in output.splitlines():
            if 'Local URL: ' in line:
                # Extract the port number from the URL
                url = line.split('Local URL: ')[1].strip()
                return url
        return None  # If no URL is found, return None

    def has_error(self, output_file=None) -> bool:
        output = self.read_output(output_file)
        feature_phrases = [
            'Error: ', 
            'Exception', 
            'AssertionError', 
            'RuntimeError',
            'Traceback (most recent call last)', 
            'ModuleNotFoundError', 
            'ImportError', 
            'SyntaxError', 
            'NameError', 
            'TypeError', 
            'ValueError'
        ]
        if any(phrase in output for phrase in feature_phrases):
            return True
        return False

    async def check(self, use_venv: bool = True, max_cua_iterations = 30, locality_control: str = None, locality_thresholds: dict = None, port = None, **kwargs) -> CheckReport: # just check if build succeed
        # flush the output file before running the app
        _passed, report = await self.check_locality(locality_control, locality_thresholds)  # check the locality of the app
        if not _passed:
            return CheckReport(False, f"Locality check failed: {report}")
        _temp_output_file = self.get_temp_output_file(flush=True) 
        pid, output_handle = await self.run_app(output_file=_temp_output_file, use_venv=use_venv, headless=True, port=port)  # run the app to check if it is deliverable, check in production mode
        max_build_time = 30  # wait for the app to finish building FIXME: make it adaptable
        max_init_time = 60  # maximum wait time in seconds
        # App running check
        _passed, note = await self.check_running(pid, max_init_time=max_init_time, output_file=_temp_output_file)  # check if the app is running
        if _passed: # passed by far, now check the health of the app
            # _passed = asyncio.run(self.check_health(max_build_time=max_build_time, output_file=_temp_output_file)) # await if in async context
            _passed = await self.check_health(max_build_time=max_build_time, output_file=_temp_output_file)  # check the health of the app
        if _passed:
            _passed, report = await self.check_cua(max_iterations=max_cua_iterations, output_file=_temp_output_file) 
            note += report
        U.kill_process(pid)  # kill the process after checking
        if output_handle:
            output_handle.close()
        _passed = _passed and not self.has_error(output_file=_temp_output_file)  # check if there is any error in the output
        output = self.read_output(_temp_output_file)  # read the final output after the process is done
        return CheckReport(_passed, message=output+note)  # return the check report with the output and note
    
    async def check_running(self, pid, max_init_time=60, output_file = None) -> bool:
        note = ''
        _passed = True  # assume the app is valid
        _last_output = self.read_output(output_file)
        last_refresh = dt.datetime.now()
        while True:
            try:
                psutil.Process(pid)  # check if the process is still running
                if self.app_running(output_file=output_file):  # if the app is running, we can stop checking
                    break
                output = self.read_output(output_file)
                if output != _last_output:  # if the output has changed, update the last output
                    _last_output = output
                    last_refresh = dt.datetime.now()
                if dt.datetime.now() - last_refresh > dt.timedelta(seconds=max_init_time):
                    _passed = False
                    note = f"\n\n(App seems not start running and frozen for {max_init_time} seconds. The system forcely stopped the process.)"
                    break
                await asyncio.sleep(1) # <-- NON-BLOCKING CALL
            except psutil.NoSuchProcess:
                U.cprint("Process not found, stopping the check...", 'r')
                _passed = False
                break
        U.cprint(f"App running check completed. Passed: {_passed}", 'g' if _passed else 'r')
        return _passed, note

    async def check_health(self, max_build_time=30, output_file=None) -> bool:
        _passed = True  # assume the app is valid
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True) # Set headless=False to see the browser UI
            page = await browser.new_page()
            await page.goto(self.running_url(output_file=output_file))  # Replace with your local server URL

            for i in range(max_build_time):
                if self.has_error(output_file=output_file):  # if there is an error in the output, we can stop checking
                    U.cprint("Error found in the output, stopping the process...", 'r')
                    await browser.close()
                    _passed = False
                    break
                await asyncio.sleep(1)  # wait for a while before checking again
            await browser.close()
        U.cprint(f"App health check completed. Passed: {_passed}", 'g' if _passed else 'r')
        return _passed


    async def check_cua(self, max_iterations=30, output_file=None, trace_dir=None) -> CheckReport:
        """
        Check the CUA (Computer User Actions) by simulating multiple users.
        """
        if max_iterations <= 0:
            return True, "No CUA iterations specified, skipping CUA check."
        _passed = True
        url = self.running_url(output_file)
        cua = OpenAICUA({'max_iterations': max_iterations})
        sess = await cua.call(
            url=url,
            user_input=_CHECK_CUA_PROMPT,
            system=_CHECK_CUA_SYSTEM,
            conclude=_CHECK_CUA_CONCLUDE,
            conclude_parser=_cua_check_parser,
            headless=True,
            trace_dir=trace_dir,
        )
        if sess.report:
            _passed = sess.report['json']['decision'] == 'pass'
            report = f'### Report from CUA test\n\n{sess.report['raw']}'
        else:
            _passed = False
            report = f'Error in CUA session.'
        U.cprint(f"CUA check completed. Passed: {_passed}", 'g' if _passed else 'r')
        return _passed, report

    async def check_locality(self, locality_control: str, locality_thresholds: dict):
        if locality_control is None or locality_control == 'none':
            return True, "No locality control specified, skipping locality check."
        assert locality_control in {'loc', 'act', 'both'}, "Invalid locality control specified. Must be one of 'loc', 'act', or 'both'."
        folder_diff = None
        act_diff = None
        if locality_control == 'both' or locality_control == 'loc':
            assert 'loc' in locality_thresholds, "Locality thresholds for 'both' control must be specified."
            if self.state.last_version_app_dir is not None:
                folder_diff = FolderDiff.from_folders(old_folder_dir=self.state.last_version_app_dir, new_folder_dir=self.state.app_dir)
        if locality_control == 'both' or locality_control == 'act':
            assert 'act' in locality_thresholds, "Locality thresholds for 'act' control must be specified."
            if self.state.last_version_trace_dir is not None:
                act_diff = ACTDiff.from_trace_dirs(old_trace_dir=self.state.last_version_trace_dir, new_trace_dir=self.state.latest_trace_dir)
        if folder_diff is None and act_diff is None:
            return True, "No significant changes detected, skipping locality check."
        _errors = []
        if folder_diff is not None:
            if folder_diff.turnover_rate > locality_thresholds['loc']:
                _errors.append(f"Code turnover rate (lines of code deleted/added by the total lines of code before change): {folder_diff.turnover_rate} exceeds threshold {locality_thresholds['loc']}.")
        if act_diff is not None:
            if act_diff.turnover_rate > locality_thresholds['act']:
                _errors.append(f"Component turnover rate (number of modified/deleted/added components by the total number of components before change): {act_diff.turnover_rate} exceeds threshold {locality_thresholds['act']}.")
        if _errors:
            return False, "\n".join(_errors)
        return True, "Locality check passed."

