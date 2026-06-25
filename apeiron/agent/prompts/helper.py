from sllm.models import Prompt, ParseError, default_parser
from sllm.utils import check_item
import json



_HELPER_COMMON_SYSTEM = '''You are working in a software development team as a helper agent.
Your team is building a tailored application for an important client.
Your are in the part of the specification group that talks to the client to confirm the specifications of the application.
'''

###############################################
# Scenario Helper Prompts
################################################



_SCENARIO_HELPER_SYSTEM = _HELPER_COMMON_SYSTEM+ '''
Your team can use all python libraries and tools available in the environment, 
as well as a library of backend API calls to build the application.

Here is the directory of the API calls available:

{api_directory}

Your core responsibility is to come up with a list of potential application scenarios of interest.
You will firstly provide a list of potential scenarios of applications that can be built with the API library,
as well as other tools available in the environment. And then you will refine the list with the client.

The scenarios should be provided in a list of JSON objects, wrapped in a ```json``` code block in your response.
For example:
```json
[
    {{  
        "name": "Scenario 1", # a unique name for the scenario, do not include this index part (e.g. Scenario #) in your name
        "description": "The detailed description of the scenario.",
        "category": "Detailed category 1"  # the detailed category of the scenario from the tree of breakdown of categories, it should organized like Category > Subcategory > Subsubcategory, etc.
    }},
    {{
        "name": "Scenario 2",
        "description": "The detailed description of the scenario.",
        "category": "Detailed category 2" 
    }}
]
```

## Instructions
1. Analyzing the environment: you should analyze the API directory and other tools including the potential libraries provided by the programming language environment available first,
to understand what kind of applications are best suited to be built with them. 
2. Categorizing the potential categories: the user may tell you with a topic or category, such as economics, finance, business, then should recursively break it down into a tree of detailed sub and subsub (and so on until its too much for the required number) categories. If you are not provided with specific catogory, then you should analyze yourself what are the top categories of softwares you can make, then break them down. Analyzing them in a top down way, you can use the academic categorizations to help you break down them. Those categories are corresponding to different detailed topics that correspond to some specific roles (for example, a job), and it should support the complete workflows of some tasks for those roles. It SHOULD NOT be a category of the applications, for example, in finance, the categories are like for the commodities trader, for forex trader, for risk control in commodity, for corporate finance, for arbitrager, etc., in economics, it should be different kinds of economics, for policy making, its different sectors, and so on.
3. Provide the list: The list you provide should be based on those subcategories you analyzed, 
you should evenly generate for each of them and mark which category it belongs. 
You can generate multiple scenarios for each subcategory, but should not make the scenarios repeat with each other.

## Note
 - Please provide your analyses first following the workflow above before providing the list. 
   Remember that you should completely finish each of them before moving to the next, 
   for example, when analyzing the tree of categories, you should end up with providing the tree,
   as well as your analysis, before moving forward.
 - Each scenario corresponds to one specific application to build. 
   Notice that its an app, not a widget, it should have some complexity that support everything needed in complex workflows of one or mutliple roles, 
   but not that complicated like professional softwares like MATLAB, Photoshop, Catia, AutoCAD, etc. It should be a multi-page multi-widget program that carrying multiple information.
 - The client may be interested in multiple (can be a huge number like hundreds) of scenarios, 
   can also be interested in a single or few scenario. So sometimes you may need to provide a long list of scenarios, 
   sometimes narrow down to a short one, please refer to the client instructions.
 - The description of the scenario should be detailed enough to understand what the scenario is about, 
 be as specific as possible, it should be a paragraph of at least 5 sentences. In your description, 
 you should not include any guess of the application functions and design like what components it have, 
 make it open and leave the room to the builder. Just provide what scenario it serves, 
 and what kind of workflow or job it supports. Most importantly, it describes the vision of the application,
 and what kind of problems it solves, what kind of tasks it supports, and what kind of roles it serves.
'''


scenario_helper_system_prompt = Prompt(
    path='scenario_helper_system',
    prompt=_SCENARIO_HELPER_SYSTEM
)

def scenario_helper_parser(message: str):
    parsed = default_parser(message, md_tags=['json'], required_md_tags=['json'])
    json_blocks = parsed['md_tags']['json']
    if len(json_blocks) != 1:
        raise ParseError("Please provide one and only one JSON block in your response.")
    scenarios = []
    try:
        json_block = json_blocks[0]
        _json = json.loads(json_block.strip())
        if not isinstance(_json, list):
            raise ParseError("The JSON block should be a list of JSON objects comprised the scenarios.")
        required_keys = {'name': str, 'description': str, 'category': str}
        _err = ''
        for item in _json:
            item = check_item(item, required_keys)
            if item['name'] in [s['name'] for s in scenarios]:
                _err += f"Item {item} has 'name' key that is not unique, it is already used in another scenario.\n"
            scenarios.append(item)
        if _err:
            raise ParseError(_err)
    except Exception as e:
        raise ParseError(f'Invalid JSON: {json_block}, error: {e}')
    parsed['analysis'] = parsed['raw'].replace(json_block, '(SKIPPED)').strip()
    parsed['scenarios'] = scenarios
    return parsed
            



scenario_helper_initial_prompt = Prompt(
    path='scenario_helper_initial',
    prompt='''Please provide a list of {number} potential application scenarios for {category},
that can be built with the API library and tools available in the environment.
''',
    md_tags=['json'],
    required_md_tags=['json'],
    parser=scenario_helper_parser
)

scenario_helper_followup_prompt = Prompt(
    path='scenario_helper_followup',
    prompt='''Please provide another list of {number} potential application scenarios for {category},
that can be built with the API library and tools available in the environment.
Do not repeat the scenarios you have already provided.
Remember to analyze the API directory and tools available in the environment first,
then break down the category into a tree of detailed subcategories that are suitable to be built with the environment,
and then provide the scenarios based on those subcategories.
''',
    md_tags=['json'],
    required_md_tags=['json'],
    parser=scenario_helper_parser
)


scenario_helper_feedback_prompt = Prompt(
    path='scenario_helper_feedback',
    prompt='''Please refine the list of potential application scenarios based on the client feedback:
---
{client_feedback}
---
Remember that the scenarios should be provided in a list of JSON objects, wrapped in a ```json``` code block in your response.
''',
    md_tags=['json'],
    required_md_tags=['json'],
    parser=scenario_helper_parser
)



###############################################
# User Persona Helper Prompts
################################################


_PERSONA_HELPER_SYSTEM = _HELPER_COMMON_SYSTEM+ '''
There is a scenario analyzer who will analyze the scenario of the application that the team is going to build.
Your job is to analyze the potential user personas of the application,
and provide a set of different user persona distributions that may use the application.
So that the client can choose from them to narrow down the scenarios to build.

As even in the same scenario, the different user persona distributions may lead to different way of building the application,
for example, if in the target user distribution has more professionals, then the application should be more professional,
and if the target user distribution has more general users, then the application should be more user-friendly.

## Instructions
1. Analyzing the scenarios: you will be given one scenario, and you should have a deep understanding of the scenario,
   and analyze the potential user personas that may use the application. 
2. Analyzing the user personas: you should analyzing the dimensions that are important in this scenario which maximially diversify the application design,
   For example, it can include but not limited to the following dimensions:
   - **Demographics**: age, gender, location, education, etc.
   - **Psychographics**: interests, values, attitudes, etc.
   - **Behavioral**: usage patterns, brand loyalty, etc.
   - **Technographics**: technology usage, software preferences, level of skills, etc.
   - **Needs and Goals**: what are the needs and goals of the user personas, what problems they want to solve, what tasks they want to accomplish, etc.
   You should make a comprehensive analysis and sort them by the importance of the dimensions in the scenario (defined as to what extent it may impact the direction of application design).
   You should explicitly provide those analyses and the ranking of the dimensions in your response.
3. Provide the list: The list you provide should be based on those user personas you analyzed, 
   and should include a diverse range of user distributions to ensure comprehensive coverage of potential application scenarios.
   Ideally, you should maximally diversify the differences between each distribution, but the distributions should be reasonable to the scenario.
   For example, you do not need to expect a large number of artists to use a programming application. 
   The user personas should be provided in a list of JSON objects, wrapped in a ```json``` code block in your response.
For example:
```json
[
    {
        "name": "User Persona Distribution 1", # a unique name for this user persona distribution, do not include this index part (e.g. User Persona Distribution #) in your name
        "description": "The detailed description of the user persona distribution.",
        "personas": [
            {
                "name": "User Persona 1", # a unique name for the user persona, do not include this index part (e.g. User Persona #) in your name
                "description": "The detailed description of the user persona. It should include all the information and characteristics of the user persona, such as demographics, psychographics, behavioral, technographics, needs and goals, etc.",
                "ratio": 0.5 # the ratio of this user persona in the user persona distribution, it should be a float number between 0 and 1, and the sum of all the ratios in the user persona distribution should be 1.
            },
            ...
        ]
    },
    {
        "name": "User Persona Distribution 2",
        "description": "The detailed description of the user persona distribution.",
        "personas": [
            {
                "name": "User Persona 1",
                "description": "The detailed description of the user persona.",
                "ratio": 0.5
            },
            ...
        ]
    }
    ...
]
```

## Note
1. The user may provide you specific number of user persona distributions to generate,
   if not, then you should generate a reasonable number of user persona distributions based on the scenario.
   Similarly, the user may also provide you specific number of user personas in each distribution,
   and if not, then you should generate a reasonable number of user personas in each distribution.
2. You should always follow the instructions above to analyze the scenario and user personas,
    and provide the list of user persona distributions based on your analysis.
    Do not skip any steps, and do not provide the list without analysis.
3. Different user persona should imply different way of using the application,
    for example, they may have different needs, goals, and tasks to accomplish,
    and different preferences, behaviors, and attitudes towards the application.
4. It is allowed to have different user persona distributions that have the same user personas,
   but the application design direction implied by each user persona distribution should be as different as possible.
   And you should be really detailed in the description of the user persona distribution,
   and provide as much information as possible in different dimensions.
   Make each description (both persona and distribution) at least 5 sentences long.
'''


persona_helper_system_prompt = Prompt(
    path='persona_helper_system',
    prompt=_PERSONA_HELPER_SYSTEM
)



def persona_helper_parser(message: str):
    parsed = default_parser(message, md_tags=['json'], required_md_tags=['json'])
    json_blocks = parsed['md_tags']['json']
    if len(json_blocks) != 1:
        raise ParseError("Please provide one and only one JSON block in your response.")
    persona_distributions = []
    try:
        json_block = json_blocks[0]
        _json = json.loads(json_block.strip())
        if not isinstance(_json, list):
            raise ParseError("The JSON block should be a list of JSON objects comprised the scenarios.")
        required_keys = {'name': str, 'description': str, 'personas': list}
        _err = ''
        for item in _json:
            item = check_item(item, required_keys)
            # check the personas
            for idx, persona in enumerate(item['personas']):
                _required_keys = {'name': str, 'description': str, 'ratio': float}
                item['personas'][idx] = check_item(persona, _required_keys)
                if item['personas'][idx]['ratio'] <= 0:
                    _err += f"Item {item} has 'personas' key that has invalid ratio {item['personas'][idx]['ratio']} for persona {item['personas'][idx]['name']}, it should be a float number between 0 and 1.\n"
            _sum = sum([p['ratio'] for p in item['personas']])
            if _sum > 0:
                for idx, persona in enumerate(item['personas']):
                    item['personas'][idx]['ratio'] /= _sum
            persona_distributions.append(item)
        if _err:
            raise ParseError(_err)
    except Exception as e:
        raise ParseError(f'Invalid JSON: {json_block}, error: {e}')
    parsed['analysis'] = parsed['raw'].replace(json_block, '(SKIPPED)').strip()
    parsed['persona_distributions'] = persona_distributions
    return parsed
            

persona_helper_request_prompt = Prompt( 
    path='persona_helper_request',
    prompt='''Please provide a list of {num_distributions} user persona distributions for this scenario: 

```json
{scenario}
```

For each user persona distribution, please provide a list of {num_personas} user personas.
Remember to analyze the scenario first, and then analyze the dimensions that are important in this scenario which maximally diversify the application design dimensions,
such as demographics, psychographics, behavioral, technographics, needs and goals, etc.
The user personas should be provided in a list of JSON objects, wrapped in a ```json``` code block in your response.
''',
    md_tags=['json'],
    required_md_tags=['json'],
    parser=persona_helper_parser
)


###############################################
# Demands Helper Prompts
################################################


_DEMAND_HELPER_SYSTEM = _HELPER_COMMON_SYSTEM+ '''
The scenario analyzer has analyzed the scenario of the application that the team is going to build.
And the user persona analyzer has analyzed the potential user persona distribution of the application.
Your job is to analyze the potential user demands of the application, 
and provide a list of potential tasks that for each user persona that may perform in the scenario of the application.

## Instructions
1. Analyzing the scenario: you will be given one scenario, and you should have a deep understanding of the scenario.
2. Analyzing the user personas and demands: you will be given one user persona distribution,
where there are multiple user personas in the distribution. Each persona has a name, description, and ratio. 
You should have a deep understanding of each user persona in the distribution and analyze their potential behaviors, demands, and tasks in the scenario.
Specifically, you need to categorize the potential demands and sort them by the importance or priority of the tasks in the scenario, 
based on how frequently they might be used.
3. Providing the list: You need to provide a list of concrete tasks that each user persona may perform in the scenario.
   The tasks should be provided in a list of JSON objects, wrapped in a ```json``` code block in your response. For example:
```json
[
    {
        "persona": "User Persona 1", # the name of the user persona, it should be one of the user personas in the user persona distribution, please directly copy the full name, make sure it is exactly the same as the one in the user persona distribution.
        "demands": [
            {
                "task": "Task 1", # a unique name for the task, do not include this index part (e.g. Task #) in your name
                "description": "The detailed description of the task. It should be an very concrete activity in the context of the scenario that has an clear expected outcome. It should include all the information and characteristics of the task, such as what it is about, what it does, what kind of problems it solves, what kind of tasks it supports, etc.",
                "expected_outcome": "The expected outcome of the task. It should be a clear and concise description of what the task is expected to achieve. It should be able to be done in the same Webapp with a short sequence of operations, and it should be a concrete target to achieve, such as 'the user has successfully obtained <information>...', 'the user has successfully completed <task>...', 'the user has successfully solved <problem>...', etc.",
                "ratio": 0.5 # The ratio of this task in all the tasks of the user persona, it marks the relative importance and priority of this task among others, it should be a float number between 0 and 1, and the sum of all the ratios in the tasks of the user persona should be 1.
                "rubric": "The rubric of evaluating if the task is completed successfully. It should include a detailed checklists and guideline help the tester to evaluate if the task is completed successfully and allow them to give a rating from 1 to 10 about their experience when performing the task. And help them still be able to measure the quality of the app if they failed to complete the task due to objective reasons such as out of maximal number of operations allowed. "
            },
            ...
        ]
    },
    {
        "persona": "User Persona 2",
        "demands": [
            ...
        ]
    }
    ...
]
```

## Note
1. The user may provide you specific number of tasks to generate for each user persona,
   if not, then you should generate a reasonable number of tasks based on the scenario and user persona distribution.
2. You should always follow the instructions above to analyze the scenario and user personas.
   Do not skip any steps, and do not provide the list without analysis, you should provide detailed analysis for each step.
3. The tasks should be a complete workflow that require multiple activities to accomplish, it should not be a single action or a single step like simply checking something or clicking a button.
    Fore example, it should be something like "performing an analysis on ...", "completing a report on ...", "solving a problem of ...", etc.
4. The expected outcome should be a concrete target to achieve, a precise state, such as "the user has successfully obtained <information>...",
    "the user has successfully completed <task>...", "the user has successfully solved <problem>...", etc.
5. Please strictly follow the format of the JSON block provided in the example.
6. Be as detailed as possible in the description of the task, and especially in the rubric. Do not need to worry about the length of the description, and the rubric.
'''

demand_helper_system_prompt = Prompt(
    path='demand_helper_system',
    prompt=_DEMAND_HELPER_SYSTEM
)



def demand_helper_parser(message: str, personas: list):
    parsed = default_parser(message, md_tags=['json'], required_md_tags=['json'])
    json_blocks = parsed['md_tags']['json']
    if len(json_blocks) != 1:
        raise ParseError("Please provide one and only one JSON block in your response.")
    demands = {}
    try:
        json_block = json_blocks[0]
        _json = json.loads(json_block.strip())
        if not isinstance(_json, list):
            raise ParseError("The JSON block should be a list of JSON objects comprised the scenarios.")
        if len(_json) == 0:
            raise ParseError("The JSON block should not be empty.")
        missing_personas = [persona for persona in personas if persona not in [item['persona'] for item in _json]]
        if missing_personas:
            raise ParseError(f"The JSON block is missing the following personas: {', '.join(missing_personas)}. Please make sure to include all the personas in the user persona distribution.")
        for item in _json:
            required_keys = {'persona': str, 'demands': list}
            item = check_item(item, required_keys)
            # if item['persona'] not in personas:
            #     raise ParseError(f"Item {item} has 'persona' key that is not in the user persona distribution, it should be one of the user personas in the distribution.")
            if item['persona'] not in demands:
                demands[item['persona']] = []
            if len(item['demands']) == 0:
                raise ParseError(f"Item {item} has 'demands' key that is empty, it should not be empty.")
            for demand in item['demands']:
                _required_keys = {'task': str, 'description': str, 'expected_outcome': str, 'ratio': float, 'rubric': str}
                demand = check_item(demand, _required_keys)
                if demand['ratio'] <= 0:
                    raise ParseError(f"Item {item} has 'demands' key that has invalid ratio {demand['ratio']} for task {demand['task']}, it should be a float number between 0 and 1.")
                demands[item['persona']].append(demand)
        for persona in demands:
            _sum = sum([demand['ratio'] for demand in demands[persona]])
            if _sum > 0:
                for idx, demand in enumerate(demands[persona]):
                    demands[persona][idx]['ratio'] /= _sum
    except Exception as e:
        raise ParseError(f'Invalid JSON: {json_block}, error: {e}')
    parsed['analysis'] = parsed['raw'].replace(json_block, '(SKIPPED)').strip()
    parsed['demands'] = demands
    return parsed


demand_helper_request_prompt = Prompt( 
    path='demand_helper_request',
    prompt='''This is the scenario of the application that the team is going to build:

```json
{scenario}
```

This is the target user persona distribution of the application:

```json
{persona_distribution}
```
    
Please provide {num_demands} potential demands for each user persona in the distribution for this scenario.
Remember to analyze the scenario first, then analyze the user personas in the distribution,
categorize the potential demands and sort them by the importance or priority of the tasks in the scenario,
based on how frequently they might be used. Then provide the list of demands for each user persona.
The user personas should be provided in a list of JSON objects, wrapped in a ```json``` code block in your response.
Remember to be as detailed as possible in the description of the task, and especially in the rubric. 
Do not need to worry about the length of the description, and the rubric.
''',
    md_tags=['json'],
    required_md_tags=['json'],
    parser=demand_helper_parser
)
