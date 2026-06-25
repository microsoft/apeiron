from sllm.llm import Function




websearch_agent_func = Function(
    name='websearch_agent',
    description="Calling an LLM-based AI websearch agent to search the internet for the given query.",
    properties={
        'query': {
            'type': 'string',
            'description': 'The query to search the internet for. It should be as detailed as possible, as it will provide the agent with better context to search for relevant information.'
        },
    },
    required=['query'],
)


