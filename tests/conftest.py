"""Configuración común de las pruebas."""
import os

import pytest


@pytest.fixture(autouse=True)
def sin_variables_git(monkeypatch):
    """Quita todas las variables de entorno GIT_* mientras dura cada prueba.

    Dentro del hook de pre-commit en un worktree, git exporta GIT_DIR y
    GIT_INDEX_FILE con rutas absolutas. Si se heredan, las órdenes de git que
    lanzan las pruebas en sus repositorios temporales tocarían el índice y la
    config del repositorio de verdad en vez de los suyos.
    """
    for nombre in [n for n in os.environ if n.startswith("GIT_")]:
        monkeypatch.delenv(nombre)
