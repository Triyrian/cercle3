"""Exceptions propres au projet.

Elles héritent de ``Exception`` (pas de pydantic) : aucune donnée à
valider, elles signalent un échec attendu avec un message clair.
``__main__`` attrape ``CallMeMaybeError`` et l'affiche sans traceback.
"""


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
