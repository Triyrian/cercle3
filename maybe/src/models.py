"""Types partagés par tout le projet : les données et les erreurs."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel


JsonType = Literal["number", "integer", "string", "boolean"]
"""Types de paramètre gérés par ``functions_definition.json``."""

ParameterValue = bool | int | float | str
"""Valeur Python d'un argument décodé."""


class ParameterSpec(BaseModel):
    """Type d'un paramètre de fonction."""

    type: JsonType


class FunctionDefinition(BaseModel):
    """Entrée de ``functions_definition.json``."""

    name: str
    description: str = ""
    parameters: dict[str, ParameterSpec] = {}


class PromptItem(BaseModel):
    """Entrée de ``function_calling_tests.json``."""

    prompt: str


class FunctionCall(BaseModel):
    """Entrée du fichier de sortie : exactement prompt, name, parameters."""

    prompt: str
    name: str
    parameters: dict[str, ParameterValue]


class RunConfig(BaseModel):
    """Configuration CLI validée."""

    functions_definition: Path
    input: Path
    output: Path


class CallMeMaybeError(Exception):
    """Classe de base des erreurs attendues du programme."""


class InputFileError(CallMeMaybeError):
    """Fichier d'entrée absent, illisible ou non conforme au schéma."""


class OutputFileError(CallMeMaybeError):
    """Fichier de sortie impossible à écrire."""


class ModelLoadError(CallMeMaybeError):
    """LLM ou vocabulaire impossible à charger."""


class DecodingError(CallMeMaybeError):
    """Aucune valeur valide issue du décodage contraint."""
