"""Convertit un prompt en ``FunctionCall``.

On écrit la structure JSON (tokens forcés) ; le LLM ne remplit que les
valeurs, chacune sous la contrainte de son type::

    {"name": "<ChoiceConstraint>", "parameters": {"a": <NumberConstraint>}}
"""

from pydantic import BaseModel

from src.constraints import ChoiceConstraint, constraint_for
from src.decoder import ConstrainedDecoder
from src.errors import DecodingError
from src.llm_engine import LLMEngine
from src.models import FunctionCall, FunctionDefinition, ParameterValue
from src.prompt_builder import build_prompt

NAME_OPENING = '{"name": "'
PARAMETERS_OPENING = '", "parameters": {'

DEFAULT_VALUES: dict[str, ParameterValue] = {
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

        Args:
            prompt: La requête.

        Returns:
            L'appel de fonction validé.

        Raises:
            DecodingError: Impossible de compléter la sortie.
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

        Args:
            input_ids: Prompt encodé.

        Returns:
            La fonction choisie et les ids après son nom.
        """
        ids = input_ids + self.engine.encode(NAME_OPENING)
        names = ChoiceConstraint(options=[f.name for f in self.functions])
        result = self.decoder.generate(ids, names, stop='"')
        return self.get_function(result.text), result.input_ids

    def extract_arguments(
        self, input_ids: list[int], function: FunctionDefinition
    ) -> dict[str, ParameterValue]:
        """Génère chaque argument de ``function``, dans l'ordre défini.

        Args:
            input_ids: Ids finissant après le nom de fonction.
            function: Fonction choisie.

        Returns:
            Argument -> valeur Python.
        """
        arguments: dict[str, ParameterValue] = {}
        ids = input_ids
        forced = PARAMETERS_OPENING
        last = len(function.parameters) - 1
        for index, (name, spec) in enumerate(function.parameters.items()):
            quote = '"' if spec.type == "string" else ""
            forced += f'"{name}": {quote}'
            ids = ids + self.engine.encode(forced)
            stop = quote or ("}" if index == last else ",")
            constraint = constraint_for(spec.type)
            result = self.decoder.generate(ids, constraint, stop)
            arguments[name] = constraint.to_python(result.text)
            ids = result.input_ids
            forced = f"{quote}, "
        return arguments

    def fallback_call(self, prompt: str) -> FunctionCall:
        """Appel de secours quand le décodage échoue.

        La moulinette compare les réponses ligne à ligne avec sa
        correction : sauter un prompt décalerait toutes les suivantes.
        On écrit donc une entrée valide (1re fonction, valeurs neutres),
        comptée fausse mais qui garde l'ordre.

        Args:
            prompt: La requête qui a échoué.

        Returns:
            Un appel conforme au schéma.
        """
        function = self.functions[0]
        return FunctionCall(prompt=prompt, name=function.name, parameters={
            name: DEFAULT_VALUES[spec.type]
            for name, spec in function.parameters.items()
        })

    def get_function(self, name: str) -> FunctionDefinition:
        """Trouve une fonction.

        Raises:
            DecodingError: Aucune fonction de ce nom.
        """
        for function in self.functions:
            if function.name == name:
                return function
        raise DecodingError(f"unknown function {name!r}")
