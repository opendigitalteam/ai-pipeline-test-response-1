# Supplier quotation extraction

Reads a folder of mixed supplier documents, pulls quotation lines into one
schema, and writes a table for a human reviewer with confidence and flags
attached.

The write-up asked for is in [WRITEUP.md](WRITEUP.md).

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add an OpenAI key if you want to re-run the
model-backed extractors:

```bash
cp .env.example .env
```

## Run

```bash
python -m src.cli
```

Reads from `documents/`, writes `out/extractions.csv` and
`out/extractions.sqlite`. Both are committed so you can look at the output
without running anything.

```bash
python -m src.cli --documents path/to/docs --out path/to/output --verbose
```

## Running without an API key

Model responses are cached in `cache/`, keyed by a hash of the model name and
the exact document content. The cache from my run is committed, so
`python -m src.cli` reproduces the committed table offline and for free. Change
a document or the model and the key changes, at which point a key is needed.

That is mostly a development convenience, but it also means the output table in
this repo is reproducible rather than something you have to take on trust.

## Tests

```bash
python -m pytest tests -q
```

Eleven tests, covering the JSON adapters and the price derivation rules. These
are the deterministic parts, and they are the parts worth pinning: everything
model-backed is exercised by running the pipeline and reading the output.

## Output

`out/extractions.csv` has one row per quotation line. Beyond the target schema:

| Column | Why it is there |
| --- | --- |
| `price_basis` | `stated`, `derived` or `inferred`. Tells a reviewer whether the number was read, calculated, or squinted at. |
| `derivation_note` | The actual arithmetic, e.g. `3.15 per pack / 90 tablet per pack`. |
| `overall_confidence` | `high`, `medium`, `low`, driven by whether the *price* can be trusted. |
| `field_confidence` | Per-field confidence with a reason for each. |
| `review_flags` | Things a human should look at, in words. |
| `source_locator` | Where in the document the figure came from. |

The SQLite output has a `needs_review` view filtering to anything not high
confidence or carrying a flag.

Current run: 37 line items from 8 documents, 12 high / 19 medium / 6 low
confidence, 24 carrying at least one flag.
