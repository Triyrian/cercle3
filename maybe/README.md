*This project has been created as part of the 42 curriculum by vtriyadi.*

# call me maybe

## Description

**Function calling** turns a natural language request into a structured call
that a program can execute. For *"What is the sum of 2 and 3?"*, the goal is
not to answer `5` but to produce:

```json
{"prompt": "What is the sum of 2 and 3?", "name": "fn_add_numbers", "parameters": {"a": 2.0, "b": 3.0}}
```

The program reads the available functions (`functions_definition.json`) and a
list of prompts (`function_calling_tests.json`). For each prompt, the small
**Qwen3-0.6B** model picks a function and extracts its arguments, and every
call is written to `data/output/function_calls.json`.

Asked to "answer in JSON", a 0.6B model is unreliable: it forgets quotes, adds
prose or invents keys. This project uses **constrained decoding** instead: at
each generation step, every token that would break the JSON or the schema is
forbidden. The output is always valid JSON that matches the function
definitions; the model only decides the *content*.

## Instructions

Requirements: Python 3.10+ and [uv](https://docs.astral.sh/uv/). The
`llm_sdk/` package provided with the subject sits next to `src/`.

```bash
make install   # uv sync: creates .venv with the versions pinned in uv.lock
make run       # uv run python -m src, with the default files below
```

The first run downloads the model (about 1.5 GB) into the Hugging Face cache.

| Option | Default |
|---|---|
| `--functions_definition` | `data/input/functions_definition.json` |
| `--input` | `data/input/function_calling_tests.json` |
| `--output` | `data/output/function_calls.json` (folder created if needed) |

Other rules: `make debug` (pdb), `make lint` (flake8 + mypy),
`make lint-strict` (mypy `--strict`), `make clean`.

## Example usage

```bash
uv run python -m src \
    --functions_definition data/input/functions_definition.json \
    --input data/input/function_calling_tests.json \
    --output data/output/function_calls.json
```

The program writes a JSON array (excerpt, reformatted), then prints
`Results written to data/output/function_calls.json`:

```json
[
    {"prompt": "What is the sum of 2 and 3?", "name": "fn_add_numbers",
     "parameters": {"a": 2.0, "b": 3.0}},
    {"prompt": "Greet shrek", "name": "fn_greet",
     "parameters": {"name": "shrek"}}
]
```

An error (missing file, invalid JSON, unknown parameter type...) is reported in
one line, e.g. `Error: file not found: data/input/nope.json`, with exit code 1.

## Algorithm explanation

**1. Prompt.** The model receives a Qwen3 chat prompt: a short instruction, the
list of functions (`- fn_add_numbers(a: number, b: number): Add two
numbers...`) and the user request. An empty `<think></think>` block turns off
Qwen3's reasoning mode.

**2. Forced structure, generated values.** The program writes the JSON skeleton
itself. The model only generates the values, one after the other:

```
{"name": "fn_add_numbers", "parameters": {"a": 2, "b": 3}}
          └─ generated ┘                       ^       ^ generated
```

Each forced piece is encoded and appended to the token ids, then the next value
is generated under the constraint of its type.

**3. Generating one value** (`ConstrainedDecoder.generate`), at most 64 tokens:

1. the constraint returns a boolean **mask** of the tokens allowed after the
   text generated so far;
2. if that text is already a complete value, the **stop tokens** are allowed
   too: tokens starting with the closing character (`"` for strings and the
   function name, `,` or `}` for numbers and booleans);
3. the model returns the **logits** of the next token; forbidden ones become
   `-inf` and the best remaining token is taken (greedy `argmax`);
4. a stop token ends the value and is not kept (the program writes the rest of
   the JSON); any other token is appended and the loop goes on.

**4. What each token writes.** `vocab.json` maps the ~151k token ids to
*byte-level BPE* strings (`Ġhello` is ` hello`, `Ċ` is a newline). The program
rebuilds the byte table once to get the real text of every token. Tokens that
hold half of a UTF-8 character get an empty text and are never allowed.

**5. One constraint per JSON type:**

| Constraint | Allowed tokens | Complete when |
|---|---|---|
| Choice: function name, `true`/`false` | text that continues one of the options | the text is exactly an option |
| Number: `number` (float), `integer` (int) | tokens made of `0-9 . -` that keep a valid prefix (`-` or `4.` can still become numbers, `01` or `4..` cannot) | it matches `-?(0\|[1-9][0-9]*)(\.[0-9]+)?` (no `.` for integers) |
| String | tokens without `"`, `\` or control characters; the ~5k others only if the string stays valid | the body is a valid JSON string |

Strings keep one rule: the body is a complete, valid JSON string after every
token. Escapes therefore arrive whole (`\"` and `\\` are single tokens in
Qwen's vocabulary), a quote can only be the closing one, and escapes that
decode to control characters (`\n`, `\b`...) are refused.

Since every token is checked, the output always parses and follows the schema.
The values are converted to Python (`to_python`), validated by a pydantic model
and written with `json.dump`.

## Design decisions

- **Forced structure, generated values**: keys, order and punctuation cannot be
  wrong, the model cannot add prose, and fewer tokens are generated.
- **The LLM chooses the function**, through a choice constraint over the
  defined names, as the subject requires: no keyword heuristics.
- **Greedy decoding**: always the best allowed token, so runs are deterministic.
- **Types**: `number` values are floats (`2.0`, like the subject's example) and
  `integer` values are ints. Exponents (`1e5`) are not generated: a huge one
  would become `Infinity`, which is not valid JSON.
- **pydantic everywhere**: input entries, output entries, CLI configuration,
  constraints and decoder are pydantic models. Errors are custom exceptions
  caught in `main`: one clear message, never a traceback. A prompt that cannot
  be decoded is reported and replaced by a neutral fallback call (first
  function, zero values): the output keeps one entry per prompt, in order,
  because the moulinette compares the answers line by line.
- **Small modules**: `file_io`, `models`, `llm_engine` (the only module that
  uses the SDK, public methods only), `vocabulary`, `constraints`, `decoder`,
  `function_caller` (the prompt, then the JSON skeleton).
- **Scan once per value**: the candidate tokens (number tokens, "safe" string
  tokens) are found once; each step then only tests a few hundred others.
- **`llm_sdk` as a regular dependency**: an editable install relies on a `.pth`
  file, which Python 3.13+ ignores when it is hidden (this happens in a macOS
  iCloud folder).
- **CPU build of torch on Linux**: the SDK needs torch, whose default Linux
  build pulls about 3 GB of CUDA packages (too much for a school session).
  `torch` is listed in `pyproject.toml` only to take it from the PyTorch CPU
  index on Linux (about 200 MB); our code never imports it. A full run on CPU
  takes about a minute, with the same answers.

## Performance analysis

Measured on an Apple Silicon Mac, model already downloaded, with the public and
private sets of the moulinette (11 prompts each):

| Set | Function selection | Moulinette score | Time (with model loading) |
|---|---|---|---|
| public | 11/11 | 9/11 (81.8 %) | ~35 s |
| private | 11/11 | 9/11 (81.8 %) | ~43 s |

- **Valid JSON: 100 %**, on every run and on the edge cases below.
- **Reliable**: decoding is greedy, so two runs give byte-identical files.
- **Speed**: about 3 s per prompt, far under the 5-minute limit. The SDK re-reads
  the whole sequence at every step, so time grows with the number of generated
  tokens; forcing the structure keeps that number low.
- **Remaining errors** come from the model's understanding, never from the
  format: `\d+` written as `34`, a space copied from the prompt (`" *"`,
  `" /home/..."`), `Say 'hello'` instead of `Say "hello"`.

## Challenges faced

- **Reading the vocabulary**: tokens are byte-level BPE strings, not text. The
  byte-to-character table (GPT-2 style) had to be rebuilt before any constraint
  could work.
- **Speed of the masks**: testing 151k tokens in Python at every step is slow.
  Finding the candidate tokens once per value fixed it.
- **Escapes in strings**: prompts contain `"`, `\` and `{}` (`C:\Users\john`,
  `Say "hello"`, `\d+`). The "always valid" rule makes escapes atomic and
  separates an escaped quote from the closing one; refusing control characters
  stops `\bcat\b` from turning into backspaces.
- **Ending a value**: values end on tokens such as `",` or `}\n`. Any token
  starting with the closing character is a stop, allowed only once the value is
  complete.
- **Packaging**: on macOS, the editable `llm_sdk` install stopped working
  without any message (hidden `.pth` file) until it became a regular
  dependency.

## Testing strategy

- **Unit tests** (pytest, kept locally: the subject does not grade them): byte
  table and token decoding, each constraint on small hand-made vocabularies
  (prefixes, masks, completeness, conversion), the decoder with a scripted fake
  model (refused tokens, stop handling, out of budget), loading of missing or
  invalid input files.
- **Static checks**: `make lint` and `make lint-strict` pass.
- **End to end**: the public and private sets of the moulinette, run and graded
  with it (scores above).
- **Edge cases**: missing or invalid input files, empty function list, unknown
  parameter type, unknown option, an output path that is a folder, a prompt
  matching no function, an empty prompt, very large numbers, quotes,
  backslashes and accents. Each gives a valid output or a one-line error, never
  a traceback.

## Resources

- [Qwen3-0.6B model card](https://huggingface.co/Qwen/Qwen3-0.6B): chat
  template and thinking mode.
- [Hugging Face LLM course, Byte-Pair Encoding tokenization](https://huggingface.co/learn/llm-course/chapter6/5)
- [GPT-2 `encoder.py`](https://github.com/openai/gpt-2/blob/master/src/encoder.py):
  origin of the byte-to-unicode table.
- B. T. Willard, R. Louf,
  [*Efficient Guided Generation for Large Language Models*](https://arxiv.org/abs/2307.09702)
  (2023): constrained decoding with masks over the vocabulary.
- [RFC 8259, the JSON format](https://www.rfc-editor.org/rfc/rfc8259): numbers,
  strings and escapes.
- Documentation of [pydantic](https://docs.pydantic.dev/),
  [NumPy](https://numpy.org/doc/) and [uv](https://docs.astral.sh/uv/).

### AI usage

AI (Claude, by Anthropic) was used as an assistant during the project:

- **Understanding**: explanations of the subject, BPE tokenization, constrained
  decoding and the tooling (uv, mypy, pyproject).
- **Review**: checking the code against the subject and the grading sheet,
  removing unnecessary code, finding bugs (such as the hidden `.pth` file).
- **Code**: help writing parts of the constraints, the decoding loop and the
  unit tests; each part was discussed, tested and adapted before being kept.
- **Writing**: translating the code comments to French and drafting this README.

Every part of the code was read, tested and can be explained.
