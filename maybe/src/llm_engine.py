"""Surcouche du SDK (``Small_LLM_Model``) : seul fichier qui lui parle."""

from typing import Any

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, PrivateAttr

from llm_sdk import Small_LLM_Model
from src.models import ModelLoadError

MODEL_NAME = "Qwen/Qwen3-0.6B"


class LLMEngine(BaseModel):
    """Charge le modèle une fois et expose les appels du décodeur."""

    _model: Any = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        """Charge le modèle après la validation pydantic."""
        try:
            self._model = Small_LLM_Model(MODEL_NAME)
        except Exception as err:
            raise ModelLoadError(
                f"cannot load model {MODEL_NAME!r}: {err}"
            ) from err

    def encode(self, text: str) -> list[int]:
        """Encode ``text`` en ids de tokens.

        Arg: text: Texte à encoder.
        Return: Ids de tokens.
        """
        tensor = self._model.encode(text)
        return [int(token_id) for token_id in tensor[0].tolist()]

    def next_token_logits(
        self, input_ids: list[int]
    ) -> npt.NDArray[np.float32]:
        """Lance le modèle, renvoie les logits du token suivant.

        Arg: input_ids: Toute la séquence actuelle (prompt + généré).
        Return: Un logit par id de token du modèle.
        """
        logits = self._model.get_logits_from_input_ids(input_ids)
        return np.asarray(logits, dtype=np.float32)

    def vocab_path(self) -> str:
        """Renvoie le chemin du ``vocab.json`` du modèle."""
        return str(self._model.get_path_to_vocab_file())
