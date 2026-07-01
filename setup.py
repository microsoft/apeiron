import os

from setuptools import setup, find_packages

_here = os.path.abspath(os.path.dirname(__file__))
try:
    with open(os.path.join(_here, 'README.md'), encoding='utf-8') as _f:
        long_description = _f.read()
except OSError:
    long_description = ''

setup(
    name='apeiron',
    version='0.1.0',
    description='Apeiron / amorphware: an agentic LLM toolkit.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Microsoft Corporation',
    license='MIT',
    url='https://github.com/microsoft/apeiron',
    packages=find_packages(),
    py_modules=['cli'],
    python_requires='>=3.10',
    install_requires=[
        'click',
        'openai>=1.40',
        'azure-identity>=1.16',
        'numpy',
        'pydantic>=2',
        'tiktoken',
        'pyparsing',
        'requests',
        'tqdm',
        'filelock',
        'python-dotenv',
    ],
    extras_require={
        # Computer-Use Agent tooling (sllm/tools/cua.py)
        'cua': ['playwright'],
        # Claude (and others) via the GitHub Copilot SDK (sllm/copilot_client.py).
        # Also requires the GitHub Copilot CLI on PATH.
        'copilot': ['github-copilot-sdk'],
        # Optional Plotly chart helper library (apeiron.library.modules.plotly_proxy).
        'plotly': ['plotly'],
    },
    entry_points={
        'console_scripts': [
            'apeiron=cli:cli',
        ],
    },
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)
