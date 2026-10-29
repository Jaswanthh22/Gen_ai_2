# TalentVerse — Skills & Career Intelligence

TalentVerse is a full-stack CSB312 Mini Project 2 implementation for Option 9. It accepts text input and turns it into a validated, schema-guided career insight. The frontend previews the structured result, then saves an approved record to the backend's local database file.

## Run locally

```bash
python3 server.py
```

Open http://localhost:3000.

## Deploy on Streamlit Cloud

Create the app from this repository with `app.py` as the main file. Do not
select `server.py` as the Streamlit entry point: it is the local HTTP-server
version of the app. Add `GEMINI_API_KEY` in the app's Streamlit Secrets to
enable Gemini; without it, the local demo fallback remains available.

## Deploy on Render

Use a Render **Web Service** connected to this repository and the `main`
branch. The included `render.yaml` can also be used as a Blueprint. For a
manual setup, use `pip install -r requirements.txt` as the build command and
`python3 server.py` as the start command. Add `GEMINI_API_KEY` as an
environment variable if Gemini extraction is required. Render provides the
`PORT` value automatically; the server binds to the required public host.

The JSON file is local to the service instance, so saved insights are not
durable across instance replacement on the free plan. Use a persistent disk
or an external database if those records must survive redeploys.

Copy `.env.example` to `.env` and add your Gemini key. The key is read only by the Python backend and is never sent to the browser.

```bash
cp .env.example .env
python3 server.py
```

If Gemini is unavailable, the app stays usable in local demo mode and shows a clear provider warning instead of breaking the presentation.

## Demonstrated workflow

`Text input → schema-guided extraction → validation → POST /api/records → data/talentverse.json → frontend confirmation`

The five lenses map to the five TalentVerse automation ideas: profile builder, skill-gap map, role match, portfolio brief, and interview debrief. Short or missing input is rejected with a 422-style validation message, and all saves require an explicit preview/save action.

## API

- `GET /api/health` — service/database status
- `GET /api/records` — saved insights
- `POST /api/analyze` — `{ type, text }`
- `POST /api/records` — `{ type, result, source }`

## Technology and design notes

- Frontend: semantic HTML, CSS, vanilla JavaScript.
- Backend: Python standard-library `http.server`.
- Database: atomic JSON-file persistence in `data/talentverse.json`.
- AI: Gemini `generateContent` with `responseMimeType: application/json` and a per-mode `responseSchema`, plus a validated local fallback.
- Safeguard: analysis is shown as a reviewable preview before a record is persisted.

## Complete `server.py` walkthrough

`server.py` is the backend and local web server for TalentVerse. It uses only
Python's standard library, so it does not need Flask, Django, or another web
framework. The file performs four jobs:

1. Serves the files in `public/`.
2. Exposes JSON API endpoints for analysis and saved records.
3. Sends analysis requests to Gemini when an API key is configured.
4. Stores approved insights in `data/talentverse.json`.

### 1. Imports

The imports at the top of the file provide the building blocks for the
backend:

- `json` reads, writes, and serializes request and response data.
- `os` reads environment variables such as `PORT` and `GEMINI_API_KEY`.
- `re` performs small text-extraction tasks for the local demo fallback.
- `urllib.request` and `urllib.error` call the Gemini REST API without an
  external dependency.
- `uuid` generates a unique ID for every saved insight.
- `datetime` records the UTC creation time of each insight.
- `http.server` provides `SimpleHTTPRequestHandler` for static files and
  `ThreadingHTTPServer` for concurrent browser requests.
- `pathlib.Path` creates platform-independent file paths.
- `typing.Any` documents values whose shape varies between analysis modes.

### 2. Paths and configuration

The following constants define where the application reads and writes files:

```python
ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
DATA_DIR = ROOT / "data"
DB_FILE = DATA_DIR / "talentverse.json"
```

`ROOT` is the project directory. `PUBLIC` contains `index.html`, `app.js`,
and `styles.css`. `DATA_DIR` contains the JSON data file used as the small
application database.

`load_dotenv()` reads a local `.env` file without overwriting environment
variables that already exist. This lets local development use a `.env` file
while Render and Streamlit Cloud can provide secrets through their settings.

The runtime configuration is then loaded:

- `PORT` uses the hosting platform's port, or `3000` locally.
- `HOST` defaults to `0.0.0.0`, which allows Render to reach the service.
- `GEMINI_API_KEY` enables Gemini-powered extraction when present.
- `GEMINI_MODEL` selects the preferred Gemini model.
- `GEMINI_FALLBACK_MODEL` provides a second model attempt if the preferred
  model is unavailable.

The API key remains on the backend. The browser only calls the local `/api`
routes and never receives the key.

### 3. Schemas and supported skills

`SCHEMAS` describes the fields expected for each of the five analysis types:

- `profile` creates a name, headline, skills, experience, education, and
  years of experience.
- `gap` creates a target role, current skills, skill gaps, milestones, and a
  time horizon.
- `match` compares a candidate with a role and calculates a fit score.
- `portfolio` proposes a project problem, skills, deliverables, and a stretch
  goal.
- `interview` summarizes strengths, improvement areas, and practice tasks.

Each entry has `required` fields and all possible `fields`. The required
fields are used by `validate()` before data is shown or saved.

`GEMINI_SCHEMAS` contains the same output contract in Gemini's schema format.
It tells Gemini the expected JSON types, such as strings, arrays, integers,
and numbers. This reduces unstructured or inconsistent model responses.

`SKILL_BANK` is a small list of known skills used by the local fallback. It is
not a complete skills database; it simply helps the demo mode identify common
skills in plain text.

### 4. JSON database functions

`ensure_db()` creates the `data/` directory and initializes
`talentverse.json` with this structure when the file does not exist:

```json
{"records": []}
```

`read_db()` calls `ensure_db()`, parses the JSON, and verifies that the root
value is an object containing a list called `records`. If the file is missing,
invalid, or has the wrong shape, it safely returns an empty record list.

`write_db()` writes the updated content to a temporary file first and then
replaces the original file. This is an atomic-write pattern: a partially
written JSON file is less likely if the process is interrupted during a save.

On Render's free plan, this file is temporary because the service filesystem
does not persist across restarts. Use a database or persistent storage for
production records.

### 5. Text helper functions

- `skills_in(text)` finds known skills in the input and removes duplicates
  while preserving their original order.
- `sentences(text)` splits text at periods, exclamation marks, and question
  marks.
- `first_sentence(text, fallback)` returns the first sentence or a fallback
  message when the input has no usable sentence.
- `title_from(text, fallback)` removes simple introductory phrases such as
  “I want to” and turns the first few words into a short title.

These helpers support the local demo mode and keep its output readable.

### 6. `demo_extract()` local fallback

`demo_extract(kind, text)` creates structured results without making a network
request. It has one branch for each analysis type:

- The profile branch looks for a possible name, skills, education, and years
  of experience.
- The gap branch identifies a target role and creates three learning phases.
- The match branch compares the input with a fixed set of role requirements
  and calculates `fitScore` from the number of matches.
- The portfolio branch creates a project title, problem statement, skills,
  and proof-of-work deliverables.
- The interview branch separates positive and improvement-oriented sentences
  and turns them into practice tasks.

The fallback is intentionally conservative. It provides a useful demo when
there is no API key or when Gemini is temporarily unavailable, but it should
not be treated as a full language model.

### 7. Validation with `validate()`

`validate(kind, data)` checks that a result is safe to display and save:

1. The analysis type must be supported.
2. The result must be a JSON object.
3. Required fields must not be missing or empty.
4. List fields must actually contain arrays.
5. A role-match `fitScore` must be a number between `0` and `100`.

It returns an object such as:

```json
{"valid": true, "errors": []}
```

or, when a result is invalid:

```json
{"valid": false, "errors": ["skills must be an array"]}
```

The same validator is used for Gemini responses and save requests, so invalid
data is not silently persisted.

### 8. Gemini integration with `gemini_extract()`

`gemini_extract(kind, text)` sends a structured request to Gemini:

1. It builds a prompt instructing Gemini to use only facts supported by the
   user's text.
2. It creates a request payload containing the system instruction, user
   input, JSON response mode, and the mode-specific response schema.
3. It calls the Gemini `generateContent` REST endpoint using the API key in an
   HTTP header.
4. It tries the configured model first, then the fallback model for temporary
   `404`, `429`, `500`, or `503` responses.
5. It extracts the JSON text from Gemini's response.
6. It parses and validates that JSON before returning it.

Clear `RuntimeError` messages are generated for invalid keys, unavailable
models, network failures, empty responses, invalid JSON, and schema failures.
The raw provider error is not sent to the browser.

### 9. Provider selection with `extract()`

`extract(kind, text)` is the single entry point used by the API:

- If `GEMINI_API_KEY` exists, it tries Gemini.
- If Gemini succeeds, it returns the structured result and provider name.
- If Gemini fails, it returns a local demo result plus a warning.
- If no API key exists, it immediately uses local demo mode.

This means the application remains usable for demonstrations even when an AI
credential or network connection is unavailable.

### 10. `TalentVerseHandler`

`TalentVerseHandler` extends `SimpleHTTPRequestHandler`, so it can serve both
the JSON API and the static frontend.

#### Constructor and logging

The constructor sets the static-file directory to `public/`. This makes a
request to `/` return `public/index.html`, and allows the browser to load the
JavaScript and CSS files from the same server.

`log_message()` only prints API requests. Static asset requests are omitted
from the terminal output to keep local logs readable.

#### JSON utilities

`send_json(status, data)` serializes a Python dictionary and sends it with the
correct JSON content type, cache-control header, content length, and HTTP
status code.

`read_json()` reads a request body, limits it to one megabyte, parses JSON, and
requires the body to be an object. Invalid JSON and oversized input are
converted into user-facing API errors.

### 11. GET routes

`do_GET()` handles two API routes:

#### `GET /api/health`

Returns service status, the current provider, and whether an API key is
configured. It is useful for Render health checks and quick diagnostics.

Example response:

```json
{
  "ok": true,
  "database": "json-file",
  "provider": "Local demo mode",
  "aiConfigured": false
}
```

#### `GET /api/records`

Reads saved records and returns them newest first. All other GET paths are
passed to `SimpleHTTPRequestHandler` so the frontend files are served.

### 12. POST routes

`do_POST()` parses the request body and routes it based on the URL path.

#### `POST /api/analyze`

Expected body:

```json
{"type": "profile", "text": "I am a Python student..."}
```

The route checks the analysis type, requires at least 20 characters, calls
`extract()`, validates the result, and returns the result, provider, warning,
schema, and validation status. The frontend displays this as a preview.

#### `POST /api/records`

Expected body:

```json
{
  "type": "profile",
  "result": {"name": "...", "headline": "..."},
  "source": "original user input"
}
```

The route validates the result again, creates a UUID and UTC timestamp, keeps
a short source preview, appends the record to the JSON database, and returns
HTTP `201` when the save succeeds.

#### Error handling

The handler converts malformed JSON into HTTP `400`, invalid input into HTTP
`422`, unknown paths into HTTP `404`, and unexpected failures into HTTP `500`.
The response intentionally contains a short safe message instead of exposing
internal exception details.

### 13. Program entry point

The final `if __name__ == "__main__":` block runs only when the file is
started directly with `python3 server.py`:

1. It ensures the JSON database exists.
2. It creates a threaded HTTP server on `HOST` and `PORT`.
3. It calls `serve_forever()` so the server accepts requests.
4. It handles `Ctrl+C` cleanly during local development.
5. It closes the listening socket in the `finally` block.

Render supplies its own `PORT`, while local development uses port `3000`.

### 14. End-to-end request flow

The complete analysis flow is:

```text
Browser
  → POST /api/analyze
  → read_json()
  → extract()
  → Gemini or demo_extract()
  → validate()
  → JSON preview in browser
  → POST /api/records after user approval
  → validate()
  → write_db()
  → data/talentverse.json
```

This two-step design lets the user review an insight before it is saved.
