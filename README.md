# Payload Cache Service

A FastAPI caching microservice that generates payloads from two equal-length
lists of strings, plus a `cache-cli` tool for exercising it over HTTP.

Generation is the positional **interleave** of the two lists after each string
is passed through a "transformer function" — a stand-in for a slow external
service that, here, uppercases its input. The point of the exercise is
**two-level caching**: the service must reuse both the transformed strings and
the identifiers of previously generated payloads, so the number of transformer
calls is minimized.

**Input:**

```json
{
  "list_1": ["first string", "second string", "third string"],
  "list_2": ["other string", "another string", "last string"]
}
```

**Output:**

```json
{
  "output": "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
}
```

## Architecture

The service is layered so cache logic is testable without HTTP and the
transformer is swappable. The CLI speaks HTTP only and never imports the service
layer.

```mermaid
flowchart LR
    CLI["cache-cli<br/>(httpx client)"] -->|"HTTP"| API["FastAPI<br/>api/routes.py"]
    API --> SVC["PayloadService<br/>services/payload.py"]
    SVC -->|"cache misses only"| T["Transformer<br/>(external service)"]
    SVC --> L1["Level 1: payload cache<br/>Payload table"]
    SVC --> L2["Level 2: transform cache<br/>transform_cache table"]
    L1 --> DB[("Database<br/>SQLite / PostgreSQL")]
    L2 --> DB
```

```
src/payload_cache/
  main.py               # app factory create_app() + module-level `app` for uvicorn
  api/
    routes.py           # POST /payload, GET /payload/{id}, GET /health
    schemas.py          # Pydantic request/response models
    deps.py             # DI: session, transformer
  core/
    config.py           # BaseSettings: DATABASE_URL, TRANSFORMER_LATENCY_MS, CACHE_VERSION
    hashing.py          # canonical JSON -> payload id
  services/
    payload.py          # PayloadService: dedupe, memoize, interleave, persist
    transformer.py      # Transformer protocol + UppercaseTransformer (latency + counter)
    cache.py            # TransformCache repository
  db/
    models.py           # SQLModel: Payload, TransformCache
    session.py          # engine + session factory + get_session dependency
  cli/
    main.py             # cache-cli entry point (pydantic-settings CliApp)
```

Dependency direction: `api → services → (db models, core)`; `cli → (http) → api`.

**Two cache levels.** Level 1 is the payload cache keyed by the content-addressed
payload id; a repeat of the same input returns the stored output with **zero**
transformer calls. Level 2 is the transform cache keyed by
`(CACHE_VERSION, raw_string)`; it memoizes the transformer's per-string output so
only strings never seen before are sent to the transformer, and duplicate strings
within or across the two lists are deduplicated before transforming.

## API

### `POST /payload`

Request:

```json
{ "list_1": ["first string", "second string", "third string"],
  "list_2": ["other string", "another string", "last string"] }
```

Response `200`:

```json
{ "id": "22c4b390197bae32474ac9f44fe65e84", "cached": false }
```

`id` is the 32-hex-character content address of the input (see [Design
decisions](#design-decisions)). `cached` is `true` when the payload already
existed — creation is idempotent and the status is always `200`; the flag
distinguishes a newly generated payload from a re-used one.

Validation: `list_1` and `list_2` must have equal length, otherwise the request
is rejected with `422`.

### `GET /payload/{id}`

Response `200`:

```json
{ "output": "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING" }
```

An unknown `id` returns `404`. When both lists are empty the stored `output` is
the empty string `""`.

### `GET /health`

Returns `{"status": "ok"}`; used by the Docker `HEALTHCHECK`.

## CLI

`cache-cli` is implemented with Pydantic Settings (`BaseSettings` + `CliApp`).
It POSTs the payload, then GETs it back, once per `--repeat` iteration.

```
usage: cache-cli [-h] [--host str] [--repeat int] [--input {str,null}]
                 [--json_input {str,null}] [--output str]

options:
  -h, --help            show this help message and exit
  --host str            (default: http://localhost:8000)
  --repeat int, -r int  (default: 1)
  --input {str,null}, -i {str,null}
                        (default: null)
  --json_input {str,null}, --json {str,null}, -j {str,null}
                        (default: null)
  --output str, -o str  (default: -)
```

| Flag | Default | Notes |
|---|---|---|
| `--host URL` | `http://localhost:8000` | Base URL of the server. |
| `-r`, `--repeat N` | `1` | Number of POST+GET iterations; must be `>= 1`. |
| `-i`, `--input FILE\|-` | — | Read the JSON request from a file; `-` means stdin. |
| `-j`, `--json JSON` | — | Inline JSON request (properly shell-escaped). `--json` is an alias of `--json_input`. |
| `-o`, `--output FILE\|-` | `-` | Write the output to a file; `-` means stdout. |
| `-h`, `--help` | — | Print help and exit. |

- **`-h` means help, not host.** The task synopsis showed `-h` for both; the host
  flag deliberately has **no** short form so `-h/--help` stays help. All the other
  documented short flags (`-r/-i/-j/-o`) are present; only `--host` lacks one.
- The model field is named `json_input` (a field literally named `json` would
  shadow a `BaseModel` method); `cli_shortcuts` exposes it as `--json` (and `-j`).
- Exactly one of `--json` / `--input` is required.

**Output contract.** stdout carries *only* the payload output (one line per
iteration, pipe-friendly); the id, cache status, and timing are written to
stderr. Exit codes: `0` success, `1` runtime/connection error, `2` argument or
validation error.

Examples:

```bash
# Inline JSON, stdout (only payload lines appear here) ...
uv run cache-cli --json '{"list_1":["a","b"],"list_2":["c","d"]}'
# A, C, B, D

# ... while the diagnostics go to stderr:
# [1/1] id=4c9643a382988f0463e7fa0d29316fad cached=False 0.048s

# Pipe stdin to stdout, three iterations reusing the same id:
cat payload.json | uv run cache-cli --input - --repeat 3 > output.txt

# Point at a non-default server and write the output to a file:
uv run cache-cli --host http://localhost:8000 --json '{"list_1":["x"],"list_2":["y"]}' --output out.txt
```

## Design decisions

**Content-addressed ids.** The payload id is derived from the *input*, never the
output, so a repeat request is served before any transform runs. The id is
`sha256(canonical).hexdigest()[:32]` (128-bit, URL-safe), where `canonical` is:

```python
json.dumps(
    {"v": CACHE_VERSION, "list_1": list_1, "list_2": list_2},
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)
```

`CACHE_VERSION` is folded into the hashed material as `"v"` (and into the
transform-cache key), so bumping it invalidates stale ids and cached
transformations rather than serving wrong output. On a payload-cache hit the
stored canonical input is compared to the incoming one; a mismatch (a sha256
collision) raises rather than returning a wrong answer.

**Two-level cache minimizing transformer calls.** Level 1 (`Payload`) returns a
repeat input's stored output with zero transformer calls. Level 2
(`transform_cache`, keyed by `(version, raw_string)`) memoizes per-string
results; the service deduplicates the union of both lists, reads the cache for
all of them, and calls the transformer only for the misses. A second request that
overlaps the first therefore transforms only the genuinely new strings.

**Savepoint race handling.** Each cache row and the payload row are inserted
inside a SAVEPOINT (`session.begin_nested()`). If a concurrent request inserted
the same key first, the duplicate-key `IntegrityError` rolls back only that
savepoint, the row is skipped, and the existing row is re-read — portable across
SQLite and PostgreSQL without holding locks.

**Transformer invoked outside the transaction.** The read-cache → call-transformer
→ write-cache sequence keeps the slow external call outside the DB write
transaction: no lock is held across the network hop. Cache misses are transformed,
the new rows are committed, and only then is the payload row written.

## Assumptions & limitations

- **Uppercase transformer.** The transformer's semantics (uppercase) are inferred
  from the sample output; it is behind a `Transformer` protocol so the behavior is
  swappable. `TRANSFORMER_LATENCY_MS` simulates the external-service delay.
- **No Unicode NFC normalization.** Cache keys are the exact raw strings, so
  composed (`café`) and decomposed (`cafe\u0301`) forms hash and cache
  differently. This is a deliberate simplification.
- **Rare duplicate transformer call.** Two concurrent *first* requests for the
  same new input may each call the transformer for the same misses. Correctness
  is preserved by the savepoint-guarded inserts; eliminating the duplicate call
  would require a distributed lock, which is out of scope.
- **Schema creation.** Tables are created on startup with `create_all`; Alembic
  is the intended production migration path but is not included.
- No authentication, authorization, or rate limiting (non-goals).

## Running locally

Requires Python 3.12 and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync

# Optional: copy the example environment file to configure the service.
cp .env.example .env

uv run uvicorn payload_cache.main:app --reload
```

The service then listens on `http://localhost:8000`. Exercise it:

```bash
curl -s http://localhost:8000/health
# {"status":"ok"}

curl -s -X POST http://localhost:8000/payload \
  -H "Content-Type: application/json" \
  -d '{"list_1":["first string","second string","third string"],"list_2":["other string","another string","last string"]}'
# {"id":"22c4b390197bae32474ac9f44fe65e84","cached":false}

curl -s http://localhost:8000/payload/22c4b390197bae32474ac9f44fe65e84
# {"output":"FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"}
```

Configuration is read from the environment (and an optional `.env` file):

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./payload_cache.db` | SQLAlchemy URL. SQLite is the default; PostgreSQL is selected with a `postgresql+psycopg://` URL. |
| `TRANSFORMER_LATENCY_MS` | `50` | Simulated per-string latency of the transformer. |
| `CACHE_VERSION` | `1` | Folded into the payload id and the transform-cache key. |

Interactive API docs are available at `http://localhost:8000/docs` while the
server runs.

## Running with Docker

Build and run with the defaults (SQLite, stored on a named volume):

```bash
docker compose up --build
# or, without compose:
docker build -t payload-cache-service .
docker run -p 8000:8000 payload-cache-service
```

The image runs as the non-root user `app`, exposes port `8000`, and ships a
`HEALTHCHECK` that polls `/health`. The compose `app` service mounts the
`payload-cache-data` volume at `/data` and sets
`DATABASE_URL=sqlite:////data/payload_cache.db` — the four slashes mean an
absolute path (`/data/payload_cache.db`) inside the container.

### PostgreSQL

A `postgres` service is available behind the `postgres` compose profile. Start
just the database:

```bash
docker compose --profile postgres up -d postgres
```

Then run the app against it using the `psycopg` v3 driver (a bundled runtime
dependency) and the credentials from `docker-compose.yml`:

```bash
DATABASE_URL=postgresql+psycopg://payload:payload@localhost:5432/payload_cache \
  uv run uvicorn payload_cache.main:app --reload
```

The same `create_all` startup, savepoint race handling, and cache logic apply
unchanged. SQLite remains the default; the `psycopg` driver is only imported for
PostgreSQL URLs.

> This PostgreSQL path (compose `postgres` profile + `psycopg` URL) has been
> exercised end-to-end and verified.

To stop the database and remove its volume:

```bash
docker compose --profile postgres down -v
```

## Testing

```bash
# Full suite (unit + integration)
uv run pytest

# Only the integration tests (TestClient round trips + the live-server CLI test)
uv run pytest -m integration

# With coverage
uv run pytest --cov=payload_cache --cov-report=term-missing
```

The suite has **39 tests** and covers canonicalization/hashing determinism and
version sensitivity, interleaving (including empty lists), the transformer,
the transform-cache repository, payload-service idempotency and the cache-reuse
proof, settings/CLI-flag validation (including the short flags), and the CLI.
Tests marked `integration` include a true end-to-end CLI test that starts a
`uvicorn` instance on a free port; pytest collects them by default.

Lint and type checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

## Hours

The build took approximately **6.5 hours**.
