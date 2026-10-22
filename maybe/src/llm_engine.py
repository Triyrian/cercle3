"""Fine surcouche de ``llm_sdk.Small_LLM_Model``.

Le reste du code ne parle qu'à ``LLMEngine`` : il convertit les types
du SDK (tenseurs torch, listes Python) en ``list[int]`` / tableaux numpy.
Seules les méthodes publiques du SDK sont utilisées (règle du sujet).
"""

from typing import Any

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, PrivateAttr

from llm_sdk import Small_LLM_Model
from src.errors import ModelLoadError

LLM_NAME = "Qwen/Qwen3-0.6B"


class LLMEngine(BaseModel):
    """Charge le modèle une fois et expose les appels du décodeur."""

    _llm: Any = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:
        """Charge le modèle après la validation pydantic.

        Raises:
            ModelLoadError: Échec du téléchargement ou du chargement.
        """
        try:
            self._llm = Small_LLM_Model(LLM_NAME)
        except Exception as err:  # erreurs torch / HF / réseau variées
            raise ModelLoadError(
                f"cannot load model {LLM_NAME!r}: {err}"
            ) from err

    def encode(self, text: str) -> list[int]:
        """Encode ``text`` en ids de tokens.

        Args:
            text: Texte à encoder.

        Returns:
            Ids de tokens.
        """
        tensor = self._llm.encode(text)
        return [int(token_id) for token_id in tensor[0].tolist()]

    def next_token_logits(
        self, input_ids: list[int]
    ) -> npt.NDArray[np.float32]:
        """Lance le modèle, renvoie les logits du token suivant.

        Args:
            input_ids: Toute la séquence actuelle (prompt + généré).

        Returns:
            Un logit par id de token du modèle.
        """
        logits = self._llm.get_logits_from_input_ids(input_ids)
        return np.asarray(logits, dtype=np.float32)

    def vocab_path(self) -> str:
        """Renvoie le chemin du ``vocab.json`` du modèle."""
        return str(self._llm.get_path_to_vocab_file())
