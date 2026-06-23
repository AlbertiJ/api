"""
Conftest para que pytest provea el fixture `tmp_cwd`.

Los tests fueron escritos para correr con `python tests/test_explorer.py`,
donde `main()` define `tmp = tempfile.mkdtemp(...)` y lo pasa como
argumento posicional a cada test. Para que pytest pueda correr los
mismos tests sin modificarlos, declaramos `tmp_cwd` como fixture
que devuelve un directorio temporal único por test.
"""
from __future__ import annotations

import tempfile

import pytest


@pytest.fixture
def tmp_cwd() -> str:
    """Devuelve un directorio temporal recién creado (path str)."""
    return tempfile.mkdtemp(prefix="api_explorer_test_")
