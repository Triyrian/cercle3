"""Règles d'UNE valeur générée (le JSON autour vient de FunctionCaller).

* ``is_valid_prefix`` : peut encore devenir valide ?
* ``is_complete`` : déjà valide, arrêt permis ?
* ``to_python`` : valeur Python finale.
"""

import json
import re
from abc import abstractmethod

from pydantic import BaseModel

from src.models import DecodingError, JsonType, ParameterValue
from src.vocabulary import BoolMask, Vocabulary

NUMBER_RE = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")
"""Nombre complet : '-' optionnel, partie entière, décimales optionnelles."""

INTEGER_RE = re.compile(r"-?(0|[1-9][0-9]*)")
"""Entier complet : '-' optionnel, sans zéro initial."""


class Constraint(BaseModel):
    """Base des contraintes (un modèle pydantic est aussi une ABC)."""

    def allowed_mask(self, generated: str, vocab: Vocabulary) -> BoolMask:
        """Garde les tokens qui laissent un préfixe valide.

        Args: generated: Texte déjà généré.
              vocab: Vocabulaire décodé.
        Return: Masque de taille ``vocab.size``.
        """
        return vocab.mask_from_ids([
            token_id for token_id, text in enumerate(vocab.texts)
            if text and self.is_valid_prefix(generated + text)
        ])

    @abstractmethod
    def is_valid_prefix(self, text: str) -> bool:
        """Dit si ``text`` peut encore devenir valide."""

    @abstractmethod
    def is_complete(self, generated: str) -> bool:
        """Dit si ``generated`` est déjà une valeur complète."""

    @abstractmethod
    def to_python(self, generated: str) -> ParameterValue:
        """Convertit le texte final en valeur Python."""


class ChoiceConstraint(Constraint):
    """Une des ``options`` (ex. noms de fonctions)."""

    options: list[str]

    def is_valid_prefix(self, text: str) -> bool:
        """Valide si début d'une option."""
        return any(option.startswith(text) for option in self.options)

    def is_complete(self, generated: str) -> bool:
        """Complet si exactement une option."""
        return generated in self.options

    def to_python(self, generated: str) -> ParameterValue:
        """Renvoie l'option choisie."""
        if generated not in self.options:
            raise DecodingError(f"{generated!r} is not a valid choice")
        return generated


class BooleanConstraint(ChoiceConstraint):
    """Booléen JSON, ``true`` ou ``false``."""

    options: list[str] = ["true", "false"]

    def to_python(self, generated: str) -> ParameterValue:
        """Renvoie un booléen."""
        return super().to_python(generated) == "true"


class NumberConstraint(Constraint):
    """Nombre JSON : ``float``, ou ``int`` si ``integer``."""

    integer: bool = False

    def is_valid_prefix(self, text: str) -> bool:
        """Complet, ou complet après ajout de ``"0"`` (``"-"``, ``"4."``)."""
        return self.is_complete(text) or self.is_complete(text + "0")

    def is_complete(self, generated: str) -> bool:
        """Complet si le texte est un nombre JSON."""
        pattern = INTEGER_RE if self.integer else NUMBER_RE
        return pattern.fullmatch(generated) is not None

    def to_python(self, generated: str) -> ParameterValue:
        """Renvoie ``int`` ou ``float``."""
        if not self.is_complete(generated):
            raise DecodingError(f"{generated!r} is not a valid number")
        return int(generated) if self.integer else float(generated)


class StringConstraint(Constraint):
    """Corps d'une chaîne JSON, sans guillemets (``"`` final = arrêt)."""

    def is_valid_prefix(self, text: str) -> bool:
        """Préfixe valide = complet."""
        return self.is_complete(text)

    def is_complete(self, generated: str) -> bool:
        """Complet si JSON valide, sans caractère de contrôle."""
        try:
            value = str(self.to_python(generated))
        except DecodingError:
            return False
        return all(char >= " " for char in value)

    def to_python(self, generated: str) -> ParameterValue:
        """Décode le corps JSON en ``str``."""
        try:
            return str(json.loads(f'"{generated}"'))
        except json.JSONDecodeError as err:
            raise DecodingError(f"invalid string {generated!r}") from err


def constraint_for(param_type: JsonType) -> Constraint:
    """Renvoie la contrainte d'un type de paramètre.

    Arg: param_type: Type de ``functions_definition.json``.
    Return: Contrainte neuve pour ce type.
    """
    if param_type == "string":
        return StringConstraint()
    if param_type == "boolean":
        return BooleanConstraint()
    if param_type == "integer":
        return NumberConstraint(integer=True)
    return NumberConstraint()
