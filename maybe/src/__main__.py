"""Lancement : ``uv run python -m src [--functions_definition F] ...``."""

import sys

from src.cli import parse_arguments
from src.decoder import ConstrainedDecoder
from src.errors import CallMeMaybeError
from src.file_io import load_function_definitions, load_prompts, save_results
from src.function_caller import FunctionCaller
from src.llm_engine import LLMEngine
from src.models import FunctionCall, PromptItem, RunConfig
from src.vocabulary import Vocabulary


def process_prompts(
    caller: FunctionCaller, prompts: list[PromptItem]
) -> list[FunctionCall]:
    """Traite chaque prompt, sans jamais en sauter un.

    La moulinette compare la sortie ligne à ligne : en cas d'échec, on
    écrit l'appel de secours pour garder l'ordre.

    Args:
        caller: FunctionCaller initialisé.
        prompts: Prompts à traiter.

    Returns:
        Un appel de fonction par prompt, dans l'ordre d'entrée.
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

    Args:
        config: Configuration CLI validée.
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

    Returns:
        Le code de sortie.
    """
    try:
        run(parse_arguments())
    except CallMeMaybeError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as err:  # dernier recours : jamais de traceback
        print(f"Unexpected error: {type(err).__name__}: {err}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
