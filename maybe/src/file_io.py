"""Lecture des JSON d'entrée, écriture du fichier de sortie."""

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from src.errors import InputFileError, OutputFileError
from src.models import FunctionCall, FunctionDefinition, PromptItem

_FUNCTIONS_ADAPTER = TypeAdapter(list[FunctionDefinition])
_PROMPTS_ADAPTER = TypeAdapter(list[PromptItem])


def read_json(path: Path) -> Any:
    """Lit un fichier JSON.

    Args:
        path: Fichier à lire.

    Returns:
        Le contenu JSON décodé.

    Raises:
        InputFileError: Fichier absent, illisible ou JSON invalide.
    """
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as err:
        raise InputFileError(f"file not found: {path}") from err
    except json.JSONDecodeError as err:
        raise InputFileError(f"invalid JSON in {path}: {err}") from err
    except (OSError, UnicodeDecodeError) as err:
        raise InputFileError(f"cannot read {path}: {err}") from err


def load_function_definitions(path: Path) -> list[FunctionDefinition]:
    """Charge et valide ``functions_definition.json``.

    Args:
        path: Fichier à lire.

    Returns:
        Fonctions disponibles (ordre du fichier).

    Raises:
        InputFileError: Fichier invalide ou liste vide.
    """
    try:
        functions = _FUNCTIONS_ADAPTER.validate_python(read_json(path))
    except ValidationError as err:
        raise InputFileError(f"invalid functions in {path}:\n{err}") from err
    if not functions:
        raise InputFileError(f"no function defined in {path}")
    return functions


def load_prompts(path: Path) -> list[PromptItem]:
    """Charge et valide ``function_calling_tests.json``.

    Args:
        path: Fichier à lire.

    Returns:
        Prompts à traiter (ordre du fichier).

    Raises:
        InputFileError: Fichier invalide.
    """
    try:
        return _PROMPTS_ADAPTER.validate_python(read_json(path))
    except ValidationError as err:
        raise InputFileError(f"invalid prompts in {path}:\n{err}") from err


def save_results(path: Path, results: list[FunctionCall]) -> None:
    """Écrit les appels en tableau JSON.

    Args:
        path: Fichier à écrire (dossiers parents créés).
        results: Appels de fonction à écrire.

    Raises:
        OutputFileError: Fichier impossible à écrire.
    """
    payload = [result.model_dump() for result in results]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=4, ensure_ascii=False)
            file.write("\n")
    except OSError as err:
        raise OutputFileError(f"cannot write {path}: {err}") from err
