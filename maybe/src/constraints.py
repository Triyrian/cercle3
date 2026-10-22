"""Contraintes de schéma du décodage contraint.

Une contrainte vérifie le texte généré pour UNE valeur (la structure
JSON autour, comme ``{"name": "`` ou ``, "b": ``, est imposée par
``FunctionCaller``). Elle répond à trois questions :

* ``allowed_mask`` : quels tokens ajouter en gardant le texte valide ?
* ``is_complete`` : le texte est-il déjà une valeur valide (arrêt permis) ?
* ``to_python`` : quelle valeur Python finale ?
"""

import json
import re
from abc import abstractmethod

from pydantic import BaseModel, Field, PrivateAttr

from src.errors import DecodingError
from src.models import JsonType, ParameterValue
from src.vocabulary import BoolMask, Vocabulary

# Sans exposant ("1e5") : les prompts n'en utilisent pas, et "1e999"
# donnerait float("inf"), que json.dump écrit Infinity (JSON invalide).
NUMBER_RE = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")
"""Nombre complet : partie entière, moins et décimales optionnels."""

INTEGER_RE = re.compile(r"-?(0|[1-9][0-9]*)")
"""Entier complet : '-' optionnel, sans zéro initial."""

NUMBER_CHARS = set("0123456789.-")
"""Seuls caractères permis dans un token nombre."""


class Constraint(BaseModel):
    """Base des contraintes (un modèle pydantic est aussi une ABC)."""

    @abstractmethod
    def allowed_mask(self, generated: str, vocab: Vocabulary) -> BoolMask:
        """Renvoie les tokens gardant ``generated + token`` valide.

        Args:
            generated: Texte déjà généré pour cette valeur.
            vocab: Vocabulaire décodé.

        Returns:
            Un masque de taille ``vocab.size``. Un token au texte vide ne
            doit jamais être autorisé (il n'ajouterait rien).
        """

    @abstractmethod
    def is_complete(self, generated: str) -> bool:
        """Dit si ``generated`` est déjà une valeur valide complète."""

    @abstractmethod
    def to_python(self, generated: str) -> ParameterValue:
        """Convertit le texte final en valeur Python.

        Raises:
            DecodingError: Le texte n'est pas valide.
        """


class ChoiceConstraint(Constraint):
    """La valeur doit être l'une des ``options`` (ex. noms de fonctions)."""

    options: list[str]

    def allowed_mask(self, generated: str, vocab: Vocabulary) -> BoolMask:
        """N'autorise que les tokens suivant une option.

        Pour chaque option commençant par ``generated``, tout préfixe non
        vide du reste ``rest`` égal au texte exact d'un token est autorisé.
        """
        ids: list[int] = []
        for option in self.options:
            if option.startswith(generated):
                rest = option[len(generated):]
                for end in range(1, len(rest) + 1):
                    ids += vocab.ids_with_text(rest[:end])
        return vocab.mask_from_ids(ids)

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

    options: list[str] = Field(default_factory=lambda: ["true", "false"])

    def to_python(self, generated: str) -> ParameterValue:
        """Renvoie un booléen."""
        return super().to_python(generated) == "true"


class NumberConstraint(Constraint):
    """Nombre JSON (``float``), ou entier si ``integer`` est True."""

    integer: bool = False
    _number_ids: list[int] | None = PrivateAttr(default=None)

    def is_valid_prefix(self, text: str) -> bool:
        """Dit si ``text`` peut encore devenir un nombre valide.

        Un préfixe valide est un nombre complet (``"4"``, ``"0.5"``) ou
        un nombre privé d'un chiffre (``""``, ``"-"``, ``"4."``) :
        ajouter ``"0"`` le complète. ``"--"``, ``"."``, ``"01"`` ou
        ``"4.."`` ne seront jamais complets.
        """
        return self.is_complete(text) or self.is_complete(text + "0")

    def allowed_mask(self, generated: str, vocab: Vocabulary) -> BoolMask:
        """Autorise les tokens gardant un préfixe valide.

        Tester 150k tokens par étape serait lent : les ids des
        tokens faits seulement de ``NUMBER_CHARS`` sont listés une fois
        (premier appel), puis seuls ceux-là passent par ``is_valid_prefix``.
        """
        if self._number_ids is None:
            self._number_ids = [
                token_id for token_id, text in enumerate(vocab.texts)
                if text and set(text) <= NUMBER_CHARS
            ]
        return vocab.mask_from_ids([
            token_id for token_id in self._number_ids
            if self.is_valid_prefix(generated + vocab.texts[token_id])
        ])

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

    _safe_ids: list[int] | None = PrivateAttr(default=None)
    _risky_ids: list[int] = PrivateAttr(default_factory=list)

    def allowed_mask(self, generated: str, vocab: Vocabulary) -> BoolMask:
        """Autorise les tokens qui laissent le corps de chaîne complet.

        Un token sans ``"``, ``\\`` ni caractère de contrôle est toujours
        sûr. Les autres (~5k) ne passent que si ``generated + texte``
        reste complet : un échappement arrive donc entier (``\\"``,
        ``\\\\``) et le texte est complet à chaque étape.
        """
        if self._safe_ids is None:
            self._safe_ids = []
            for token_id, text in enumerate(vocab.texts):
                if not text:
                    continue
                if '"' in text or "\\" in text or min(text) < " ":
                    self._risky_ids.append(token_id)
                else:
                    self._safe_ids.append(token_id)
        return vocab.mask_from_ids(self._safe_ids + [
            token_id for token_id in self._risky_ids
            if self.is_complete(generated + vocab.texts[token_id])
        ])

    def is_complete(self, generated: str) -> bool:
        """Complet si ``to_python`` le lit comme corps de chaîne JSON.

        Ex. ``abc`` et ``a\\\\`` (antislash échappé) sont complets,
        ``abc\\`` ou ``\\u12`` (échappement inachevé) non.
        """
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

    Args:
        param_type: Type de ``functions_definition.json``.

    Returns:
        Contrainte neuve pour ce type.
    """
    if param_type == "string":
        return StringConstraint()
    if param_type == "boolean":
        return BooleanConstraint()
    if param_type == "integer":
        return NumberConstraint(integer=True)
    return NumberConstraint()
