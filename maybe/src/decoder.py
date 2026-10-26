"""Décodage contraint: logits -> masque -> meilleur token autorisé."""

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel

from src.constraints import Constraint
from src.llm_engine import LLMEngine
from src.models import DecodingError
from src.vocabulary import BoolMask, Vocabulary


class GenerationResult(BaseModel):
    """Sortie d'une génération contrainte."""

    text: str
    """Valeur générée, sans le token d'arrêt."""

    input_ids: list[int]
    """Ids d'entrée + tokens générés (sans token d'arrêt)."""


class ConstrainedDecoder(BaseModel):
    """Génère une valeur token par token sous contrainte."""

    engine: LLMEngine
    vocab: Vocabulary
    max_tokens: int = 64

    def generate(
        self, input_ids: list[int], constraint: Constraint, stop: str
    ) -> GenerationResult:
        """Génère le texte d'une valeur, token par token.

        Au plus ``max_tokens`` étapes : masque de la contrainte (+ tokens
        d'arrêt si le texte est complet), logits du modèle, meilleur token
        autorisé. Un token d'arrêt finit la valeur sans être gardé :
        l'appelant écrit lui-même la suite du JSON.
        Args: input_ids: Prompt + JSON déjà généré (non modifié).
              constraint: Règles de la valeur.
              stop: Caractère de fin de valeur (``"``, ``,`` ou ``}``).
        Return: Le texte généré et les ids étendus.
        Raise: DecodingError: Aucune valeur valide possible.
        """
        token_ids = list(input_ids)
        text = ""
        for _ in range(self.max_tokens):
            allowed_tokens = constraint.allowed_mask(text, self.vocab)
            if constraint.is_complete(text):
                stop_tokens = self.vocab.mask_starting_with(stop)
                allowed_tokens = allowed_tokens | stop_tokens
            if not allowed_tokens.any():
                break
            logits = self.engine.next_token_logits(token_ids)[:self.vocab.size]
            token_id = self.best_token(logits, allowed_tokens)
            if self.vocab.texts[token_id].startswith(stop):
                return GenerationResult(text=text, input_ids=token_ids)
            text += self.vocab.texts[token_id]
            token_ids.append(token_id)
        if constraint.is_complete(text):
            return GenerationResult(text=text, input_ids=token_ids)
        name = type(constraint).__name__
        raise DecodingError(f"{name}: cannot complete {text!r}")

    @staticmethod
    def best_token(
        logits: npt.NDArray[np.float32], allowed: BoolMask
    ) -> int:
        """Renvoie le token autorisé au logit maximal.

        Les interdits valent ``-np.inf`` dans une copie (``np.where``) :
        ``np.argmax`` ne peut pas les choisir. Au moins un doit passer.
        Args: logits: Logits du token suivant, taille ``vocab.size``.
              allowed: Masque des tokens autorisés (idem).
        Return: Id du token choisi.
        """
        return int(np.argmax(np.where(allowed, logits, -np.inf)))
