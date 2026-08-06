"""
Conftest para que pytest provea el fixture `tmp_cwd`.

Los tests fueron escritos para correr con `python tests/test_explorer.py`,
donde `main()` define `tmp = tempfile.mkdtemp(...)` y lo pasa como
argumento posicional a cada test. Para que pytest pueda correr los
mismos tests sin modificarlos, declaramos `tmp_cwd` como fixture
que devuelve un directorio temporal único por test.
"""
from __future__ import annotations

import os
import tempfile

import pytest

# Los tests de licencia.py necesitan APIEXPLORER_LICENSE_SECRET seteada
# (el secreto ya no vive hardcodeado en el código — ver explorer/licencia.py).
# Este es un valor SOLO para tests, no el secreto real de producción.
os.environ.setdefault(
    "APIEXPLORER_LICENSE_SECRET", "solo-para-tests-no-usar-en-produccion"
)


@pytest.fixture
def tmp_cwd() -> str:
    """Devuelve un directorio temporal recién creado (path str)."""
    return tempfile.mkdtemp(prefix="api_explorer_test_")
