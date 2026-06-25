"""Pytest configuration for the apeiron test suite.

Ensures the project root (which contains the ``sllm`` and ``apeiron`` packages)
is importable when tests are run from anywhere.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
