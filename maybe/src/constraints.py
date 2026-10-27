"""Contraintes de schéma du décodage contraint.

Une contrainte vérifie le texte généré pour UNE valeur (la structure
JSON autour, comme ``{"name": "`` ou ``, "b": ``, est imposée par
``FunctionCaller``). Elle répond à trois questions :
* ``is_valid_prefix`` : le texte peut-il encore devenir une valeur valide ?
* ``is_complete`` : le texte est-il déjà une valeur valide (arrêt permis) ?
* ``to_python`` : quelle valeur Python finale ?
``allowed_mask`` (commun à toutes) garde les tokens après lesquels le
texte reste un préfixe valide.
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
        """Garde les tokens après lesquels le texte peut encore être valide.

        Args: generated: Texte déjà généré pour cette valeur.
              vocab: Vocabulaire décodé.
        Return: Un masque de taille ``vocab.size``.
        """
        return vocab.mask_from_ids([
            token_id for token_id, text in enumerate(vocab.texts)
            if text and self.is_valid_prefix(generated + text)
        ])

    @abstractmethod
    def is_valid_prefix(self, text: str) -> bool:
        """Dit si ``text`` peut encore devenir une valeur valide."""

    @abstractmethod
    def is_complete(self, generated: str) -> bool:
        """Dit si ``generated`` est déjà une valeur valide complète."""

    @abstractmethod
    def to_python(self, generated: str) -> ParameterValue:
        """Convertit le texte final en valeur Python."""


class ChoiceConstraint(Constraint):
    """La valeur doit être l'une des ``options`` (ex. noms de fonctions)."""

    options: list[str]

    def is_valid_prefix(self, text: str) -> bool:
        """Valide si le texte est le début d'une des options."""
        return any(option.startswith(text) for option in self.options)

    def is_complete(self, generated: str) -> bool:
        """Complet si le texte est exactement une des options."""
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
    """Nombre JSON (``float``), ou entier si ``integer`` est True."""

    integer: bool = False

    def is_valid_prefix(self, text: str) -> bool:
        """Dit si ``text`` peut encore devenir un nombre valide.

        Un préfixe valide est un nombre complet (``"4"``, ``"0.5"``) ou
        un nombre privé d'un chiffre (``""``, ``"-"``, ``"4."``) :
        ajouter ``"0"`` le complète.
        """
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
    """Contenu d'une chaîne JSON, SANS les guillemets autour.

    Le guillemet ouvrant est imposé par l'appelant, le fermant est le
    token d'arrêt géré par le décodeur.
    """

    def is_valid_prefix(self, text: str) -> bool:
        """Une chaîne peut s'arrêter partout : préfixe valide = complet."""
        return self.is_complete(text)

    def is_complete(self, generated: str) -> bool:
        """Complet si ``to_python`` le lit comme corps de chaîne JSON."""
        try:
            value = str(self.to_python(generated))
        except DecodingError:
            return False
        return all(char >= " " for char in value)

    def to_python(self, generated: str) -> ParameterValue:
        """Décode le corps de chaîne JSON en ``str`` Python."""
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
