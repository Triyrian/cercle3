"""Table id <-> texte des tokens, issue du ``vocab.json`` du modèle.

``vocab.json`` associe les tokens *bruts* à des ids. Qwen utilise du BPE
au niveau des octets : chaque octet devient un caractère imprimable (espace =
``Ġ``, saut de ligne = ``Ċ``...). Pour savoir quels tokens autoriser en
décodage contraint, il faut leur *vrai* texte, décodé ici une fois.
"""

import json
from typing import Any

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, PrivateAttr

from src.models import ModelLoadError

BoolMask = npt.NDArray[np.bool_]
"""Un booléen par id de token : True = token autorisé."""


def bytes_to_unicode() -> dict[int, str]:
    """Renvoie la table octet -> caractère du BPE au niveau des octets.

    Un octet imprimable garde son caractère. Les autres (caractères de
    contrôle, espace...) sont décalés, dans l'ordre, vers
    ``chr(256)``, ``chr(257)``... donc l'espace (32) devient ``"Ġ"``.
    Return: Un dict de 256 entrées, ex. ``{32: "Ġ", 65: "A", ...}``.
    """
    printable: dict[int, str] = (
        {i: chr(i) for i in range(33, 127)}
        | {i: chr(i) for i in range(161, 173)}
        | {i: chr(i) for i in range(174, 256)}
    )
    remapped = (i for i in range(256) if i not in printable)
    return printable | {b: chr(256 + n) for n, b in enumerate(remapped)}


def decode_token(raw_token: str, char_to_byte: dict[str, int]) -> str:
    """Donne le texte réel d'une entrée brute du vocabulaire.

    Exemple : ``"Ġhello"`` -> ``" hello"``.
    Args: raw_token: Clé de ``vocab.json``.
          char_to_byte: Table ``bytes_to_unicode()`` inversée.
    Return: Le texte décodé, ou ``""`` si les octets seuls ne sont pas de
            l'UTF-8 valide (bout de caractère multi-octet) : ces tokens sont
            toujours interdits en décodage contraint.
    """
    try:
        return bytes(char_to_byte[char] for char in raw_token).decode("utf-8")
    except (KeyError, UnicodeDecodeError):
        return ""


class Vocabulary(BaseModel):
    """Texte décodé des tokens et masques utiles en cache."""

    texts: list[str]
    """``texts[token_id]`` = texte décodé, ``""`` si token inutilisable."""

    _ids_by_text: dict[str, list[int]] = PrivateAttr(default_factory=dict)
    _prefix_masks: dict[str, BoolMask] = PrivateAttr(default_factory=dict)

    @classmethod
    def from_file(cls, path: str) -> "Vocabulary":
        """Charge ``vocab.json`` et décode ses tokens.

        Les tokens spéciaux (``<|im_start|>``...) ne sont pas dans
        ``vocab.json`` : le vocabulaire est donc un peu plus petit que les
        logits, et le décodeur n'en lit que les ``size`` premiers.
        Arg: path: Chemin donné par ``LLMEngine.vocab_path()``.
        Return: Le vocabulaire décodé.
        Raise: ModelLoadError: Fichier illisible.
        """
        try:
            with open(path, encoding="utf-8") as file:
                raw_vocab: dict[str, int] = json.load(file)
        except (OSError, json.JSONDecodeError) as err:
            raise ModelLoadError(f"cannot read vocabulary {path}: {err}") \
                from err
        char_to_byte = {
            char: byte for byte, char in bytes_to_unicode().items()
        }
        texts = [""] * (max(raw_vocab.values()) + 1)
        for raw_token, token_id in raw_vocab.items():
            texts[token_id] = decode_token(raw_token, char_to_byte)
        return cls(texts=texts)

    def model_post_init(self, __context: Any) -> None:
        """Indexe les ids par texte."""
        for token_id, text in enumerate(self.texts):
            if text:
                self._ids_by_text.setdefault(text, []).append(token_id)

    @property
    def size(self) -> int:
        """Nombre d'ids de token du vocabulaire."""
        return len(self.texts)

    def ids_with_text(self, text: str) -> list[int]:
        """Renvoie les ids des tokens dont le texte vaut ``text``."""
        return self._ids_by_text.get(text, [])

    def mask_from_ids(self, token_ids: list[int]) -> BoolMask:
        """Crée un masque n'autorisant que ``token_ids``."""
        mask = np.zeros(self.size, dtype=np.bool_)
        mask[token_ids] = True
        return mask

    def mask_starting_with(self, prefix: str) -> BoolMask:
        """Masque (en cache) des tokens commençant par ``prefix``.

        Sert aux tokens d'arrêt : une valeur complète finit sur tout token
        débutant par le caractère fermant (``"``, ``,`` ou ``}``).
        """
        if prefix not in self._prefix_masks:
            self._prefix_masks[prefix] = np.array(
                [text.startswith(prefix) for text in self.texts],
                dtype=np.bool_,
            )
        return self._prefix_masks[prefix]
