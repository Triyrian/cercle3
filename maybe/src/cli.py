"""Lecture des options de la ligne de commande."""

import argparse
from pathlib import Path

from src.models import RunConfig


def parse_arguments() -> RunConfig:
    """Lit les options de ``python -m src`` (défauts : fichiers du sujet).

    Returns:
        La configuration, validée par pydantic.
    """
    parser = argparse.ArgumentParser(
        prog="python -m src",
        description="Translate natural language prompts into function calls.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--functions_definition", type=Path,
        default=Path("data/input/functions_definition.json"),
        help="JSON file of available functions",
    )
    parser.add_argument(
        "--input", type=Path,
        default=Path("data/input/function_calling_tests.json"),
        help="JSON file of prompts",
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/output/function_calls.json"),
        help="JSON file to write",
    )
    return RunConfig.model_validate(vars(parser.parse_args()))
