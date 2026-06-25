from sllm.models import Prompt, ParseError, default_parser, Function, FunctionCall, MCP
from sllm.utils import check_item, find_level1_blocks_sorted
import apeiron.utils as U
import apeiron.agent.prompts.tools as T
import functools as ft
import os
import json


# Tools
# 1. Reflex MCP https://github.com/reflex-dev/reflex/blob/main/MCP_README
# 2. CALL_API
# 3. Read files
# 4. *Websearch: not hurry, maybe later for better debugging
# Actions
# Write files: as the output and parse it separately
# Compile and run 
# Finish the session

# Ideally: https://reflex.dev/docs/ai-builder/overview/what-is-reflex-build/ 


current_dir = os.path.dirname(os.path.abspath(__file__))
docs_path = U.pjoin(current_dir, 'docs')
streamlit_nav_bar_doc = U.pjoin(docs_path, 'streamlit_navigation_bar_doc.md')
streamlit_nav_bar_doc = U.read_file(streamlit_nav_bar_doc).replace('{','{{').replace('}', '}}')
st_navigation_doc = U.pjoin(docs_path, 'st_navigation_doc.md')
st_navigation_doc = U.read_file(st_navigation_doc).replace('{','{{').replace('}', '}}')



# FIXME: this mcp server is not working
reflex_mcp_server = MCP(
    server_label='reflex_docs',
    server_url= "https://reflex-mcp-server.fly.dev/mcp",
)



_BUILDER_BACKGROUND_OVERVIEW = '''You are an expert in designing and building applications using {framework}, 
a Python framework for building web applications.


## Overview

You will be given a set of details about the application to build,
including the target scenario and user personas, you do not only write the code, 
you are also designing the app that can best meet the needs of the users and the scenario.
You might be provided with an empty reflex project that have just been initilized, or a project that has already been built by others.
You will be able to make operations on the files and use the APIs in a backend library to build the application.

You will be asked to operate the files until you are satisfied and then you can inform the system to compile the code by include a special tag <COMPILE> in your response.
You will continously be able to make operations until you submit with the <COMPILE> tag, so you do not need to finish everything in a single response.
The system will then compile and run the application, and run some tests to verify the correctness of the application:
* If the tests pass, the system will finish the session and you can then will be asked to provide a journal of the session,
including what you have done to the current application for the future builders as a reference. In your journal, 
you will also need to analyze the current status of the application, like if it is ready to be delivered to the users given the input scenario and personas:
    - If yes, you need to explain why it is ready, whether all the potential demands and issues have been addressed, then include a tag <DELIVER> in your response to finish the session.
    - If no, you need to explain why it is not ready, what features are missing, and what are the issues that need to be addressed, and what are the next steps to take.
    - Be really careful about deciding whether the application is ready to be delivered, you should implement all the features and fix all the issues, do not leave any unfinished features, as there will be no more sessions to finish them if you decide to deliver the application.
* If there is any errors or failures, you will be asked to debug the application and fix the issues,
you will make operations on the files until you are satisfied and then you can inform the system to compile the code again by including a special tag <COMPILE> in your response,
the system will check the application again and run the tests. 
You will repeat this process until the application is built successfully and the tests pass.
If the error cannot be fixed for a long time, the system may terminate the session and ask you to provide a journal of the session,
including what you have done to the current application for the future builders as a reference when continuing fixing the application.

Notice that, you do not necessarily need to finish everything in a single session (from the start to the successful build),
be clear about the current status of the application that is given to you, and have a reasonable plan for what to do in this session.
For example, you do not want to make too many edits in a single session, as it makes it harder to debug the application if there are any issues.
Remember that there might be other builders who will continue to build the application after you,
so you do not need to make it deliverable in one time, make sure that making feasible plans, and make clear and well-documented in your journal at the end.
'''




_REFLEX_OPERATIONS_BACKGROUND = '''
## Operations


You can make multiple operations in a single response by including different blocks:
To write a file, you can wrap the content in ```write:<file_path>``` blocks, where `<file_path>` is the path of the file you are writing to.
If the file does not exist, it will be created, otherwise, it will be overwritten.
And you can use ```delete:<file_path>``` blocks to delete a file. The content of the block will be ignored.
The path should be relative to the project root directory (do not include the project root directory in the path).

For example, suppose the current app directory is:

app:
├── .gitignore
├── app
│   ├── app.py # main entry point of the application, do not rename or delete this file, do not have multiple app.py files, remember to add all your components and pages to the app=rx.App() object of this file
│   └── __init__.py
├── assets
│   └── favicon.ico
├── requirements.txt
├── rxconfig.py
... 

Then you can write the `app.py` file by wrapping the content in ```write:app/app.py``` blocks, like this:
```write:app/app.py
import reflex as rx
from apeiron_re import CALL_API # for accessing API library, see API Library Usage section below
rx.config(title="My App", description="This is my app.")
...
```

You can create a new file by using the same syntax, for example, to create a new file `app/pages/login.py`, you can use:
```write:app/pages/login.py
... (your code here, it can also be empty if you just want to create an empty file)
```

Then the app directory will look like this:
app:
├── app
│   ├── app.py
│   ├── pages
│   │   └── login.py # new file created
│   └── __init__.py
...

If you want to delete a file, you can use the ```delete:app/pages/login.py``` block, like this:
```delete:app/pages/login.py```

This will delete the `login.py` file from the `app/pages/` directory, the directory will look like this:
app:
├── app
│   ├── app.py
│   ├── pages # login.py deleted, pages directory is now empty, note that you cannot directly create an empty directory
│   └── __init__.py
...

You can also delete the entire directory by using the same syntax, for example, to delete the `app/pages/` directory, you can use:
```delete:app/pages/```

This will delete the `pages` directory and all its contents, the directory will look like this:
app:
├── app
│   ├── app.py
│   └── __init__.py
...


### Important Notes

* Note that the operations in your response will be executed **in the order they appear**, so you can write multiple files in a single response.
* Before writing or deleting on any files, you should be sure that you know their content, and read them first.
* Think carefully about writing any code or deleting any files, as it is **irreversible**. 
* You should always have a plan first before writing any code, the plan should appear in between the blocks. Do not just provide the operations without any explanation.
* Always make sure that the paths are correct, if there is any mistake in any of the paths, the system will raise an error and you will need to fix it, and the operations will not be executed until you fix the errors.
* ALWAYS remember to add the components and pages to the `app` object in `app.py` file, so that they can be rendered in the application. This is VERY IMPORTANT, otherwise, the components and pages you created will not be included in the application. And MAKE SURE that you added the `index` and other pages to the app correctly, otherwise, they will not be included correctly in the application.
* You should always have `app.py` in the `app/` directory, and keep it as the main entry point of the application, and there must be a `app = rx.App()` object in the `app.py` file, so that the application can be run correctly. 
* There will be a static checker which will `from app.app import app` and check the app object, and if it is not passed, it will raise an error and you will need to fix it.
* Search the internet by quering the websearch agent if you have any questions.
'''




_STREAMLIT_OPERATIONS_BACKGROUND = '''
## Operations


You can make multiple operations in a single response by including different blocks:
To write a file, you can wrap the content in ```write:<file_path>``` blocks, where `<file_path>` is the path of the file you are writing to.
If the file does not exist, it will be created, otherwise, it will be overwritten.
And you can use ```delete:<file_path>``` blocks to delete a file. The content of the block will be ignored.
The path should be relative to the project root directory (do not include the project root directory in the path).

For example, suppose the current app directory is:

app:
├── .streamlit
│   └── config.toml # configuration file for Streamlit, you can modify it
├── app.py # main entry point of the application, do not rename or delete this file, do not have multiple app.py files, remember to import and add all your components and pages to this file
├── assets
│   └── ...
├── requirements.txt # you can write the dependencies you need in this file, and the system will install them for you
...  

Then you can write the `app.py` file by wrapping the content in ```write:app.py``` blocks, like this:
```write:app.py
import streamlit as st
...
```

You can create a new file by using the same syntax, for example, to create a new file `pages/login.py`, you can use:
```write:pages/login.py
... (your code here, it can also be empty if you just want to create an empty file)
```

Then the app directory will look like this:
app:
├── app.py
├── pages
│   └── login.py # new file created
...

If you want to delete a file, you can use the ```delete:pages/login.py``` block, like this:
```delete:pages/login.py```

This will delete the `login.py` file from the `pages/` directory, the directory will look like this:
app:
├── app.py
├── pages # login.py deleted, pages directory is now empty, note that you cannot directly create an empty directory
...

You can also delete the entire directory by using the same syntax, for example, to delete the `pages/` directory, you can use:
```delete:pages/```

This will delete the `pages` directory and all its contents, the directory will look like this:
app:
├── app.py
...


### Important Notes

* Note that the operations in your response will be executed **in the order they appear**, so you can write multiple files in a single response.
* Before writing or deleting on any files, you should be sure that you know their content, and read them first.
* Think carefully about writing any code or deleting any files, as it is **irreversible**. 
* You should always have a plan first before writing any code, the plan should appear in between the blocks. Do not just provide the operations without any explanation.
* Always make sure that the paths are correct, if there is any mistake in any of the paths, the system will raise an error and you will need to fix it, and the operations will not be executed until you fix the errors.
* ALWAYS remember to add the components and pages to the `app` object in `app.py` file, so that they can be rendered in the application. This is VERY IMPORTANT, otherwise, the components and pages you created will not be included in the application. 
* You should always have `app.py` in the project root directory, and keep it as the main entry point of the application, so that the application can be run correctly.
* Search the internet by quering the websearch agent if you have any questions.
* If you already know the content of the file, you do not need to read it again and again.
'''

_STREAMLIT_OPERATIONS_BACKGROUND += '''

### Project Structure

Please use `st.navigation` and `st.Page` to manage the multiple pages in your Streamlit application.
The project is initilized with a default structure, where the pages are organized in the `pages/` directory.
The pages are imported in the `app.py` file, and the navigation is rendered in the `app.py` file as well.
In the template, there are pages by default: `page1.py`, `page2.py`, ..., rememeber to rename them, and you can delete or add new pages as you need.
When renaming the pages, make sure to update the import statements and the keys in the navigation in the `app.py` file accordingly.

The `assets/` directory is used to store the static assets, such as images, CSS files, etc. 
There is also a `.streamlit/config.toml` file in the project, which is used to configure the Streamlit application.
The `requirements.txt` file is used to specify the dependencies of the application, you can write the dependencies you need in this file, and the system will install them for you.
The `utils.py` file is used to store the utility functions that can be used in the application, you can write your utility functions in this file or delete it if you do not need it.

* DO NOT BREAK THE STRUCTURE OF THE PROJECT
* KEEP the way of building navigation in `app.py`, as the api may change, see the latest documentation later.
* KEEP the wide page setting and the logo
* DO NOT USE the sidebar 
* USE st.logo to set the logo of the application instead of using st.image 
* The use_column_width parameter has been deprecated and will be removed in a future release. Please utilize the use_container_width parameter instead.

''' + st_navigation_doc



## Prompt for using streamlit_navigation_bar package, it has errors so not used for now
# _STREAMLIT_OPERATIONS_BACKGROUND+= '''

# ### Project Structure

# The team uses the `streamlit_navigation_bar` package to provide a navigation bar for the application, remember to keep it and use it to organize your app.
# The project is initilized with a default structure, where the pages are organized in the `pages/` directory, each page may have multiple tabs, the tabs are selected in the sidebar.
# The pages are imported in the `app.py` file, and the navigation bar is rendered in the `app.py` file as well.
# In the template, there are pages by default: `page1.py`, `page2.py` ..., rememeber to rename them, and you can delete or add new pages as you need.
# When renaming the pages, make sure to update the import statements and the keys in the navigation bar in the `app.py` file accordingly.

# The `assets/` directory is used to store the static assets, such as images, CSS files, etc. There is a `logo.svg` file in the `assets/` directory by default, do not delete, rename, or modify it.
# It is used as the logo of the application, as well as the entry point of the `home` page of the application in the navigation bar.
# Remember to ensure the logo is properly set up in the navigation bar, otherwise, the home page will not be accessible in the application.

# There is also a `.streamlit/config.toml` file in the project, which is used to configure the Streamlit application.
# The `requirements.txt` file is used to specify the dependencies of the application, you can write the dependencies you need in this file, and the system will install them for you.
# The `utils.py` file is used to store the utility functions that can be used in the application, you can write your utility functions in this file or delete it if you do not need it.

# * DO NOT BREAK THE STRUCTURE OF THE PROJECT, most importantly, do not remove the streamlit_navigation_bar structure

# ### Documentation of Streamlit Navigation Bar


# ''' + streamlit_nav_bar_doc


_API_LIBRARY_USAGE = '''
## API Library Usage

You have access to an API library within your `<python_cell>` blocks. The system will execute these for you:

 **`CALL_API(api_path: str, api_params: dict)`**: Use this to call an API endpoint.
    * Example: `response = CALL_API("fmp/crypto/end-of-day/historical-price-eod/full", {{"symbol": "BTCUSD", "from": "2023-01-01"}}) `

Remember to import the `CALL_API` function at the beginning of your Python cell:
```python
from apeiron_re import CALL_API
```

`apeiron_re` is an internal module that provides the `CALL_API` function for you to interact with the APIs.
You should never have a module named `apeiron_re` in your project, 
as it is a reserved name for the internal module that provides the `CALL_API` function.
A directory of available APIs is provided below.



### API Directory

---
```
{api_directory}
```
---


### Important Notes

1.  **Consult Documentation First**: ALWAYS make sure you have retrieved and read the documents of the API endpoints you 
are going to use *before* you write a Python cell that uses `CALL_API` function, unless you have retrieved that specific
documentation earlier in this session. This prevents incorrect API usage. 
2.  **Use `CALL_API`**: ALWAYS use the `CALL_API` function to interact with APIs. API keys are managed by the backend. 
3.  **Batch API Documentation Retrieval**: It's generally more efficient to retrieve documentation for several APIs you anticipate using in one go, 
rather than retrieve multiple rounds of dialogs.
4. You should ALWAYS use REAL DATA from the API, you should NEVER use fake data or mock data in your application,
as the application is expected to be used in real-world scenarios and should provide real data to the users.
'''




reflex_builder_system_prompt = Prompt(
    path='reflex_builder_system',
    prompt=_BUILDER_BACKGROUND_OVERVIEW.format(framework='Reflex')+_REFLEX_OPERATIONS_BACKGROUND+_API_LIBRARY_USAGE
)



streamlit_builder_system_prompt = Prompt(
    path='streamlit_builder_system',
    prompt=_BUILDER_BACKGROUND_OVERVIEW.format(framework='Streamlit')+_STREAMLIT_OPERATIONS_BACKGROUND+_API_LIBRARY_USAGE
)


build_session_input_prompt = Prompt(
    path='build_session_input',
    prompt='''Here are the details of the application to build, and the current progress:

{build_state}
''',
)


def retrieve_api_doc_processor(result: str, function_call: FunctionCall):
    return f'''Here are the documentations for the APIs you requested for {function_call.arguments['full_paths']}:
---
{result}
---
'''


retrieve_api_doc_func = Function(
    name='retrieve_api_doc',
    description="Retrieve the API documentation for the given API full paths from the directory.",
    properties={
        'full_paths': {
            'type': 'array',
            'items': {'type': 'string'},
            'minItems': 1,
            'maxItems': 25,
            'description': 'A list of API full paths to retrieve the documentation for. You can request documentation for multiple API paths in a single request. It must be the full path of the API from the directory.'
        }
    },
    required=['full_paths'],
    processor=retrieve_api_doc_processor,
)


def read_files_processor(result: str, function_call: FunctionCall):
    return f'''Here are the contents of the files you requested for {function_call.arguments['paths']}:
---
{result}
---
'''



read_files_func = Function(
    name='read_files',
    description="Read the contents of a file.",
    properties={
        'paths': {
            'type': 'array',
            'items': {'type': 'string'},
            'minItems': 1,
            'maxItems': 10,
            'description': 'A list of file paths to read the contents from. You can request to read multiple files in a single request. It must be the relative path of the file from project root directory (do not include the project root directory in the path). If you need to read multiple files, provide a list instead of calling multiple times.'
        }
    },
    required=['paths'],
    processor=read_files_processor,
)


# def bash_script_processor(result: str, function_call: FunctionCall):
#     if result.strip() == '':
#         return 'The bash script executed successfully, but there is no output.'
#     return f'''Here is the log of executing the bash script:
# ```{result}```
# '''

# os_info = os.name

# bash_script_func = Function(
#     name='bash_script',
#     description="Execute a bash script.",
#     properties={
#         'script': {
#             'type': 'string',
#             'description': f'The bash script to execute. It should be a valid bash script. The OS is {os_info}.'
#         }
#     },
#     required=['script'],
#     processor=bash_script_processor
# )

def bun_install_processor(result: str, function_call: FunctionCall):
    return f'''Here is the log of installing the packages using Bun:
```{result}```
'''

bun_install_func = Function(
    name='bun_install',
    description="Install the dependencies using Bun.",
    properties={
        'package_names': {
            'type': 'array',
            'items': {'type': 'string'},
            'minItems': 1,
            'maxItems': 10,
            'description': 'A list of package names to install using Bun. You can request to install multiple packages in a single request.'
        }
    },
    required=['package_names'],
    processor=bun_install_processor,
)



def build_act_parser(message: str, app_dir: str):
    blocks = find_level1_blocks_sorted(message)
    blocks = [b[3:-3] for b in blocks] 
    operations = []
    warnings = []
    errors = [] 
    for block in blocks:
        _instruct1 = block.split(' ',1)[0]
        _instruct2 = block.split('\n',1)[0]
        # the shortest instruction is the one
        instruct = _instruct1 if len(_instruct1) < len(_instruct2) else _instruct2
        if instruct.startswith('write:') or instruct.startswith('delete:'):
            operation, path = instruct.split(':', 1)
            content = block[len(instruct):].strip()
            if operation == 'delete':
                if not U.pexists(U.pjoin(app_dir, path.strip())):
                    errors.append(f'Error: File {path} does not exist in current directory (note that you cannot delete the file you just created in the same response). All operations will not be performed. Please re-provide all the operations with the correct file paths and in the right order you want them to be performed.')
                for op in operations:
                    if op['type'] == 'delete' and op['target'] == path:
                        warnings.append(f'Warning: Duplicate delete operation for {path}. Ignoring this one.')
                        continue
            operations.append({
                'type': operation,
                'target': path,
                'content': content
            })
    if errors:
        raise ParseError(f'Errors:\n{'\n'.join(errors)}\n\nWarnings:\n{'\n'.join(warnings)}')
    
    return {
        'raw': message,
        'operations': operations,
        'warnings': warnings,
        'errors': errors,
        'compile': '<COMPILE>' in message,
    }


BuildPrompt = ft.partial(
    Prompt,
    _functions=[retrieve_api_doc_func], #, T.websearch_agent_func], # bun_install_func, read_files_func
    parser=build_act_parser,
    # _mcp_servers=[reflex_mcp_server],
    allow_web_search=True,
)





build_act_start_prompt = BuildPrompt(
    path='build_act_start',
    prompt='''Please start building the application based on the details provided.
Provide your operations in your response and including your analysis process. Remember to follow the instructions strictly.
''',
)



build_act_followup_prompt = BuildPrompt(
    path='build_act_followup',
    prompt='''Your operations have been executed:

{execution_result}
    
Please continue building the application based on the details provided.
Provide your operations in your response and including your analysis process. Remember to follow the instructions strictly.
If you are ready and want to compile the code, please include a special tag <COMPILE> at the end of your response.
''',
)



build_debug_start_prompt = BuildPrompt(
    path='build_debug_start',
    prompt='''The project has been compiled and tested, but did not pass, please fix the issues, here are the details:

{bug_info}

Provide your operations in your response and including your analysis process. Remember to follow the instructions strictly.
''',
)



build_debug_followup_prompt = BuildPrompt(
    path='build_debug_followup',
    prompt='''Your operations have been executed:

{execution_result}

Please continue fixing the issues based on the details provided.
Provide your operations in your response and including your analysis process. Remember to follow the instructions strictly.
If you are ready and want to compile the code again, please include a special tag <COMPILE> at the end of your response.
''',
)




def build_conclude_parser(message: str):
    return {
        'raw': message,
        'deliver': '<DELIVER>' in message,
    }

build_conclude_prompt = Prompt(
    path='build_session_conclude',
    prompt='''The project has been successfully built and tested, please provide a journal of the session, including what you have done to the current application for the future builders as a reference.
In your journal, you will also need to analyze the current status of the application, like if it is ready to be delivered to the users given the input scenario and personas.
* If yes, you need to explain why it is ready, whether all the potential demands and issues have been addressed, then include a tag <DELIVER> in your response to finish the session.
* If no, you need to explain why it is not ready, what features are missing, and what are the issues that need to be addressed, and what are the next steps to take. And do not include the <DELIVER> tag in your response, the builders can continue to build the application in the next session.
''',
    parser=build_conclude_parser,
)



build_conclude_failed_prompt = Prompt(
    path='build_session_conclude_failed',
    prompt='''The project has failed in building and testing, please provide a journal of the session, including what you have done to the current application for the future builders as a reference.
''',
    parser=build_conclude_parser,
)


# TODO: self test cases generation

