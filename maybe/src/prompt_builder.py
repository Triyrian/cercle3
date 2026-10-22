"""Construit le prompt donné au LLM (template de chat Qwen3).

Le prompt aide juste le modèle à *choisir* ; le décodage contraint, et non
ces instructions, garantit le format de sortie.
"""

from src.models import FunctionDefinition

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

    Args:
        function: Fonction à décrire.

    Returns:
        Ex. ``- fn_add_numbers(a: number, b: number): Add two numbers.``
    """
    params = ", ".join(
        f"{name}: {spec.type}" for name, spec in function.parameters.items()
    )
    return f"- {function.name}({params}): {function.description}"


def build_prompt(user_prompt: str, functions: list[FunctionDefinition]) -> str:
    """Construit le prompt de chat complet, jusqu'au début du JSON.

    Args:
        user_prompt: Requête en texte libre.
        functions: Fonctions proposées.

    Returns:
        Le texte à encoder.
    """
    catalog = "\n".join(describe_function(function) for function in functions)
    return (
        f"{IM_START}system\n{SYSTEM_INSTRUCTIONS}"
        f"Available functions:\n{catalog}{IM_END}\n"
        f"{IM_START}user\n{user_prompt}{IM_END}\n"
        f"{IM_START}assistant\n{NO_THINK}"
    )
