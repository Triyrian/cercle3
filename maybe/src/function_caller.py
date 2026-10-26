"""Transforme un prompt en ``FunctionCall``, en deux parties.

1. Le prompt (``build_prompt``) : le texte donné au LLM, au format de chat
   de Qwen3. Il aide seulement le modèle à *choisir* ; le format de sortie
   est garanti par le décodage contraint, pas par ces instructions.
2. L'appel (``FunctionCaller``) : le programme écrit lui-même la structure
   JSON, le LLM ne remplit que les valeurs, chacune sous la contrainte de
   son type : ``{"name": "<Choice>", "parameters": {"a": <Number>}}``.
"""

from pydantic import BaseModel

from src.constraints import ChoiceConstraint, constraint_for
from src.decoder import ConstrainedDecoder
from src.llm_engine import LLMEngine
from src.models import (
    DecodingError, FunctionCall, FunctionDefinition, ParameterValue,
)

# 1. Le prompt donné au LLM

IM_START = "<|im_start|>"
IM_END = "<|im_end|>"
NO_THINK = "<think>\n\n</think>\n\n"
"""Bloc de réflexion vide : coupe le "thinking" de Qwen3."""

SYSTEM_INSTRUCTIONS = (
    "You translate a user request into one function call. "
    "Choose the function that fulfils the request and copy the argument "
    "values from the request.\n"
)


def describe_function(function: FunctionDefinition) -> str:
    """Décrit une fonction en une ligne.

    Arg: function: Fonction à décrire.
    Return: Ex. ``- fn_add_numbers(a: number, b: number): Add two numbers.``
    """
    params = ", ".join(
        f"{name}: {spec.type}" for name, spec in function.parameters.items()
    )
    return f"- {function.name}({params}): {function.description}"


def build_prompt(user_prompt: str, functions: list[FunctionDefinition]) -> str:
    """Construit le prompt de chat complet, jusqu'au début du JSON.

    Args: user_prompt: Requête en texte libre.
          functions: Fonctions proposées.
    Return: Le texte à encoder.
    """
    catalog = "\n".join(describe_function(function) for function in functions)
    return (
        f"{IM_START}system\n{SYSTEM_INSTRUCTIONS}"
        f"Available functions:\n{catalog}{IM_END}\n"
        f"{IM_START}user\n{user_prompt}{IM_END}\n"
        f"{IM_START}assistant\n{NO_THINK}"
    )


# 2. L'appel de fonction : squelette JSON + décodage contraint

NAME_OPENING = '{"name": "'
PARAMETERS_OPENING = '", "parameters": {'

FALLBACK_VALUES: dict[str, ParameterValue] = {
    "number": 0.0, "integer": 0, "string": "", "boolean": False,
}
"""Valeurs neutres de l'appel de secours, par type."""


class FunctionCaller(BaseModel):
    """Choisit la fonction puis extrait ses arguments via le LLM."""

    engine: LLMEngine
    decoder: ConstrainedDecoder
    functions: list[FunctionDefinition]

    def call(self, prompt: str) -> FunctionCall:
        """Traite un prompt en langage naturel.

        Arg: prompt: La requête.
        Return: L'appel de fonction validé.
        Raise: DecodingError: Impossible de compléter la sortie.
        """
        input_ids = self.engine.encode(build_prompt(prompt, self.functions))
        function, input_ids = self.choose_function(input_ids)
        parameters = self.extract_arguments(input_ids, function)
        return FunctionCall(
            prompt=prompt, name=function.name, parameters=parameters
        )

    def choose_function(
        self, input_ids: list[int]
    ) -> tuple[FunctionDefinition, list[int]]:
        """Le LLM choisit un nom de fonction parmi celles définies.

        Arg: input_ids: Prompt encodé.
        Return: La fonction choisie et les ids après son nom.
        """
        token_ids = input_ids + self.engine.encode(NAME_OPENING)
        name_constraint = ChoiceConstraint(
            options=[f.name for f in self.functions]
        )
        generation = self.decoder.generate(
            token_ids, name_constraint, stop='"'
        )
        return self.get_function(generation.text), generation.input_ids

    def extract_arguments(
        self, input_ids: list[int], function: FunctionDefinition
    ) -> dict[str, ParameterValue]:
        """Génère chaque argument de ``function``, dans l'ordre défini.

        Args: input_ids: Ids finissant après le nom de fonction.
              function: Fonction choisie.
        Return: Argument -> valeur Python.
        """
        arguments: dict[str, ParameterValue] = {}
        token_ids = input_ids
        json_before_value = PARAMETERS_OPENING
        last_index = len(function.parameters) - 1
        for index, (name, spec) in enumerate(function.parameters.items()):
            quote = '"' if spec.type == "string" else ""
            json_before_value += f'"{name}": {quote}'
            token_ids = token_ids + self.engine.encode(json_before_value)
            stop = quote or ("}" if index == last_index else ",")
            constraint = constraint_for(spec.type)
            generation = self.decoder.generate(token_ids, constraint, stop)
            arguments[name] = constraint.to_python(generation.text)
            token_ids = generation.input_ids
            json_before_value = f"{quote}, "
        return arguments

    def fallback_call(self, prompt: str) -> FunctionCall:
        """Appel de secours quand le décodage échoue.

        Arg: prompt: La requête qui a échoué.
        Return: Un appel conforme au schéma.
        """
        function = self.functions[0]
        return FunctionCall(prompt=prompt, name=function.name, parameters={
            name: FALLBACK_VALUES[spec.type]
            for name, spec in function.parameters.items()
        })

    def get_function(self, name: str) -> FunctionDefinition:
        """Trouve une fonction.

        Raise: DecodingError: Aucune fonction de ce nom.
        """
        for function in self.functions:
            if function.name == name:
                return function
        raise DecodingError(f"unknown function {name!r}")
