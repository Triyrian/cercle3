"""Lecture des JSON d'entrée, écriture du fichier de sortie."""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.models import (
    FunctionCall, FunctionDefinition, InputFileError, OutputFileError,
    PromptItem,
)


def read_json_list(path: Path) -> list[Any]:
    """Lit un fichier JSON qui doit contenir une liste.

    Arg: path: Fichier à lire.
    Return: La liste décodée.
    """
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError) as err:
        raise InputFileError(f"cannot read {path}: {err}") from err
    if not isinstance(data, list):
        raise InputFileError(f"expected a JSON list in {path}")
    return data


def load_function_definitions(path: Path) -> list[FunctionDefinition]:
    """Charge et valide ``functions_definition.json``.

    Arg: path: Fichier à lire.
    Return: Fonctions disponibles (ordre du fichier).
    """
    try:
        functions = [FunctionDefinition.model_validate(item)
                     for item in read_json_list(path)]
    except ValidationError as err:
        raise InputFileError(f"invalid functions in {path}:\n{err}") from err
    if not functions:
        raise InputFileError(f"no function defined in {path}")
    return functions


def load_prompts(path: Path) -> list[PromptItem]:
    """Charge et valide ``function_calling_tests.json``.

    Arg: path: Fichier à lire.
    Return: Prompts à traiter (ordre du fichier).
    """
    try:
        return [PromptItem.model_validate(item)
                for item in read_json_list(path)]
    except ValidationError as err:
        raise InputFileError(f"invalid prompts in {path}:\n{err}") from err


def save_results(path: Path, results: list[FunctionCall]) -> None:
    """Écrit les appels en tableau JSON.

    Args: path: Fichier à écrire (dossiers parents créés).
          results: Appels de fonction à écrire.
    """
    payload = [result.model_dump() for result in results]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=4, ensure_ascii=False)
            file.write("\n")
    except OSError as err:
        raise OutputFileError(f"cannot write {path}: {err}") from err
