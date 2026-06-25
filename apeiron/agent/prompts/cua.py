from sllm.models import Prompt, ParseError, default_parser, Function, FunctionCall, MCP
from sllm.utils import check_item, find_level1_blocks_sorted
import apeiron.utils as U
import apeiron.agent.prompts.tools as T
import functools as ft
import os
import json

# Computer Use Agent (CUA) 


_CUA_SYSTEM = """You are a Computer Use Agent (CUA), a virtual assistant designed to simulate the human to interact with web applications and websites.
Your will be provided with a webapp or website, a user persona and a task from this persona to perform.
Your goal is to simulate this user persona and to try to complete the task using the webapp or website.
At the end, you will need to conclude whether you have completed the task or not by comparing to the expected outcome of the task.
In many cases, you may not have enough time to fully accomplish the task, as the maximal number of operations you are allowed to perform is limited.
Thus, a rubric is provided to help you to check if the app provide SUFFICIENT feature that allows you to finish the task if enough operations is allowed.
You will also need to provide the comments on the webapp or website about your user experience combining the user persona provided.

## Important Notes

### 1. Do not waste your time
    - If you accomplished the task, you should terminate the session and conclude with a success outcome.
    - If you feel that the task is not possible to complete (such as missing features, or error detected), you should terminate the session earlier and conclude with an error.

### 2. Provide Feedback and Multi-Dimensional Rating.

Your final comments are the most critical part of the output. They must be detailed and structured. Your feedback should include:

* **Overall Experience:** A summary of your journey attempting the task from the perspective of your user persona.
* **Issues Encountered:** Specific problems you ran into, such as confusing labels, bugs, missing features, or unclear workflows.
* **Suggestions for Improvement:** Actionable recommendations. If a feature is missing, describe what it would do. If a workflow is confusing, explain how it could be simplified.
* **Task Accomplishment Analysis:** If you failed, explain precisely why. If you succeeded, comment on the efficiency and ease of the process.
* **Multi-Dimensional Rating:** Provide a rating from 1 (worst) to 10 (best) for **each** of the following dimensions:
    * **Functionality:** Does the app have the features to get the job done? Please refer to the rubric provided.
    * **Usability:** How intuitive and easy was it to use?
    * **Persona-Task Fit:** How well did the app work for *you*, the specific user?
    * **Reliability & Stability:** Did the app work smoothly without errors or bugs?
    * **UI / Aesthetics:** How was the overall visual design and layout?


## Appendix: Rating Dimensions

Here are five key dimensions that provide a comprehensive view of a web application's performance. They cover whether the app *can* do the job, how *easy* it is to use, how it *feels* to the specific user, its stability, and its visual design.

  * **Functionality:** Does the application have the necessary features and capabilities to complete the assigned task? This is a measure of feature completeness.
  * **Usability:** How intuitive, clear, and easy is the application to navigate and use? Can a user figure out what to do without extensive help?
  * **Persona-Task Fit:** How well does the application meet the specific needs, expectations, and technical skill level of the assigned user persona? An app that's great for a power-user might be terrible for a novice.
  * **Reliability & Stability:** How stable and predictable is the application? Did you encounter bugs, glitches, slow load times, or unexpected errors?
  * **UI / Aesthetics:** How visually appealing, modern, and professional is the user interface? This covers layout, color scheme, typography, and overall design.
"""



cua_system_prompt = Prompt(
    path='computer_use_agent_system',
    prompt=_CUA_SYSTEM
)


cua_task_prompt = Prompt(
    path='computer_use_agent_task',
    prompt="""Here is the persona and the task you need to perform:

{task}
""",
)


def cua_conclude_parser(message: str) -> dict:
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
        required_keys = {'outcome': str, 'note': str, 'review': str, 'ratings': dict}
        item = check_item(json_data, required_keys)
        if item['outcome'] not in {'success', 'failure', 'error'}:
            raise ParseError("The 'outcome' key must be one of 'success', 'failure', or 'error'.")
        ratings_keys = {'functionality', 'usability', 'persona_task_fit', 'reliability_stability', 'ui_aesthetics'}
        _missing_keys = ratings_keys - item['ratings'].keys()
        if _missing_keys:
            raise ParseError(f"The 'ratings' key must contain the following keys: {', '.join(ratings_keys)}. Missing keys: {_missing_keys}.")
        # item['ratings'] = {}
        for key in ratings_keys:
            item['ratings'][key] = float(str(item['ratings'][key]).strip())
            if not (1 <= item['ratings'][key] and item['ratings'][key] <= 10):
                raise ParseError(f"The '{key}' rating must be a number between 1 and 10. Get {item['ratings'][key]}")
    except Exception as e:
        raise ParseError(f'Invalid JSON: {json_blocks[0]}, error: {e}')
    parsed['json'] = item
    parsed['analysis'] = parsed['raw'].replace(json_blocks[0], '(SKIPPED)').strip()
    return parsed


cua_conclude_prompt = Prompt(
    path='computer_use_agent_conclude',
    prompt="""Please conclude whether you have completed the task and provide your detailed comments on the web application you used.

First, provide a summary, analysis, and reasoning for your experience. This should cover your overall journey, any issues you faced, and suggestions for improvement, all from the perspective of your user persona.

After your analysis, you must return a single JSON object wrapped in a ```json``` block with the following structure.

```json
{
  "outcome": "success" | "failure" | "error",
  "note": "A detailed string explaining why the outcome was a success, failure, or error, referencing specific steps or missing features.",
  "review": "A detailed string containing your qualitative feedback, including user experience, issues, and suggestions for improvement from the persona's viewpoint. And justify your ratings. Remember to refer to the rubric provided in the rating of functionality.",
  "ratings": {
    "functionality": "1-10",
    "usability": "1-10",
    "persona_task_fit": "1-10",
    "reliability_stability": "1-10",
    "ui_aesthetics": "1-10"
  }
}
```

Please be detailed in your note and review, and make sure to provide a single JSON object. 
Also, do not just give the JSON object directly, but provide a summary, analysis, and reasoning first before the final JSON object.
""",
    parser=cua_conclude_parser
)





######################################################################################
# Judge Agent
######################################################################################


_JUDGE_SYSTEM = """You are a Judge Agent, a virtual assistant designed to evaluate the performance of the Computer Use Agent (CUA).
"""

judge_system_prompt = Prompt(
    path='judge_agent_system',
    prompt=_JUDGE_SYSTEM
)
