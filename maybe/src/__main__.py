"""Lancement : ``uv run python -m src [--functions_definition F] ...``."""

import argparse
import sys
from pathlib import Path

from src.decoder import ConstrainedDecoder
from src.errors import CallMeMaybeError
from src.file_io import load_function_definitions, load_prompts, save_results
from src.function_caller import FunctionCaller
from src.llm_engine import LLMEngine
from src.models import FunctionCall, PromptItem, RunConfig
from src.vocabulary import Vocabulary


def parse_arguments() -> RunConfig:
    """Lit les options de ``python -m src`` (défauts : fichiers du sujet).

    Return: La configuration, validée par pydantic.
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


def process_prompts(
    caller: FunctionCaller, prompts: list[PromptItem]
) -> list[FunctionCall]:
    """Traite chaque prompt, sans jamais en sauter un.

    La moulinette compare la sortie ligne à ligne : en cas d'échec, on
    écrit l'appel de secours pour garder l'ordre.
    Args: caller: FunctionCaller initialisé.
          prompts: Prompts à traiter.
    Return: Un appel de fonction par prompt, dans l'ordre d'entrée.
    """
    results: list[FunctionCall] = []
    for index, item in enumerate(prompts, start=1):
        try:
            call = caller.call(item.prompt)
        except CallMeMaybeError as err:
            print(f"[{index}/{len(prompts)}] {item.prompt!r}: {err}"
                  " -> fallback call", file=sys.stderr)
            call = caller.fallback_call(item.prompt)
        else:
            print(f"[{index}/{len(prompts)}] {item.prompt!r} -> {call.name}")
        results.append(call)
    return results


def run(config: RunConfig) -> None:
    """Charge tout, traite les prompts et écrit la sortie.

    Arg: config: Configuration CLI validée.
    """
    functions = load_function_definitions(config.functions_definition)
    prompts = load_prompts(config.input)
    engine = LLMEngine()
    vocab = Vocabulary.from_file(engine.vocab_path())
    decoder = ConstrainedDecoder(engine=engine, vocab=vocab)
    caller = FunctionCaller(engine=engine, decoder=decoder,
                            functions=functions)
    save_results(config.output, process_prompts(caller, prompts))
    print(f"Results written to {config.output}")


def main() -> int:
    """Lance le programme ; toute erreur devient un message clair.

    Return: Le code de sortie.
    """
    try:
        run(parse_arguments())
    except CallMeMaybeError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as err:
        print(f"Unexpected error: {type(err).__name__}: {err}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
