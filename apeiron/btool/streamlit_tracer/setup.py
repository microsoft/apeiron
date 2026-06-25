from setuptools import setup, find_packages

setup(
    name="stracelit",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["streamlit"],
    entry_points={
        'console_scripts': [
            'stracelit = stracelit.cli:main',
        ],
    },
)

