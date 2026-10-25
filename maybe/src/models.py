"""Modèles pydantic partagés par tout le projet."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

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
    parameters: dict[str, ParameterSpec] = Field(default_factory=dict)


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
