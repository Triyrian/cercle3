"""Table id -> vrai texte des tokens, décodée du ``vocab.json`` du modèle.

Dans ``vocab.json``, chaque octet devient imprimable (espace = ``Ġ``).
"""

import json

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel

from src.models import ModelLoadError

BoolMask = npt.NDArray[np.bool_]
"""Un booléen par id de token : True = token autorisé."""


def bytes_to_unicode() -> dict[int, str]:
    """Table octet -> caractère : imprimable inchangé, sinon ``chr(256+n)``.

    Return: 256 entrées, ex. ``{32: "Ġ", 65: "A", ...}``.
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
    Return: Le texte décodé.
    """
    try:
        return bytes(char_to_byte[char] for char in raw_token).decode("utf-8")
    except (KeyError, UnicodeDecodeError):
        return ""


class Vocabulary(BaseModel):
    """Texte décodé des tokens et fabrication des masques."""

    texts: list[str]
    """``texts[token_id]`` = texte décodé, ``""`` si token inutilisable."""

    @classmethod
    def from_file(cls, path: str) -> "Vocabulary":
        """Charge ``vocab.json`` et décode ses tokens.

        Arg: path: Chemin donné par ``LLMEngine.vocab_path()``.
        Return: Le vocabulaire décodé.
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

    @property
    def size(self) -> int:
        """Nombre d'ids de token du vocabulaire."""
        return len(self.texts)

    def mask_from_ids(self, token_ids: list[int]) -> BoolMask:
        """Crée un masque n'autorisant que ``token_ids``."""
        mask = np.zeros(self.size, dtype=np.bool_)
        mask[token_ids] = True
        return mask

    def mask_starting_with(self, prefix: str) -> BoolMask:
        """Masque des tokens commençant par ``prefix`` (tokens d'arrêt)."""
        return np.array([text.startswith(prefix) for text in self.texts],
                        dtype=np.bool_)
