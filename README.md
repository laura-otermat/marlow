# Marlow

[![Tests](https://github.com/laura-otermat/marlow/actions/workflows/tests.yml/badge.svg)](https://github.com/laura-otermat/marlow/actions/workflows/tests.yml)

Marlow is an AI household memory assistant. It reduces the mental load of
running a household by remembering family preferences, recurring events and
important details from plain conversation, then turning them into a short
weekly to-do list.

Instead of maintaining lists, you just tell Marlow things:

- "My children don't wear school uniforms."
- "We use snowsuits every winter."
- "Our wedding anniversary is in June."

Marlow extracts a structured memory from each message, stores it for the
household, and later uses everything it knows to answer "what should we be
doing this week?"

> This is a public snapshot of a personal project, shared to show how it is
> built. It is not maintained as an open-source product.

The web client lives in [marlow-ui](https://github.com/laura-otermat/marlow-ui), a React and TypeScript app that signs users in with Supabase Auth and calls this API.

## What it does

| Endpoint | Purpose |
| --- | --- |
| `POST /remember` | Turns a free-text message into a structured memory (category, subject, value, confidence) using an LLM with a typed output schema, and saves it to the household. |
| `GET /ask` | Summarises everything the household has told Marlow, grouping related details and refusing to invent anything not in the memories. |
| `GET /plan` | Picks the three most useful actions for the current week, judging urgency against an explicit, timezone-aware date range. Answers "Nothing urgent." when appropriate. |
| `POST /households` | Platform admin creates a household and invites its first owner by email. |
| `POST /households/{id}/invitations` | A household owner invites another member. |

## How it's built

- **API:** Python, FastAPI, Pydantic models with input normalisation and validation
- **AI:** OpenAI Responses API, with structured output parsed straight into a Pydantic `Memory` model
- **Data and auth:** Supabase (PostgreSQL + Supabase Auth)
- **Tests and CI:** pytest, run offline on every push with GitHub Actions

### Design decisions worth a look

- **Security is enforced in the database, not just the API.** Each request
  uses the caller's own Supabase access token, so PostgreSQL row-level security
  policies ([`supabase/migrations`](supabase/migrations)) decide what a user can
  read or write. The API checks household membership too, as defence in depth.
- **Least-privilege credentials.** The Supabase service-role key is used only
  for the two server-side flows that need it (creating households, sending
  invitations). Everything else runs with user-scoped credentials.
- **Callers can't spoof authorship.** `created_by_user_id` is always taken from
  the validated token, never from the request body, and RLS rejects inserts
  where it doesn't match.
- **Privacy-aware extraction.** The extraction prompt tells the model to skip
  confidential or interpersonal details and small talk, so only useful
  household facts get stored.
- **Deterministic, offline tests.** LLM and Supabase clients are injected, so
  the whole suite runs without network access or API keys, including tests
  that check private memory content never leaks into logs.

## Project layout

```
app/
  main.py                  FastAPI app and CORS
  routes.py                HTTP endpoints
  auth.py                  Bearer-token validation and role checks
  models/                  Pydantic request/response and Memory models
  services/
    llm.py                 Memory extraction (structured LLM output)
    agent.py               Summaries and weekly planning
    memory_repository.py   Persistence
    household_account.py   Household creation and invitations
supabase/migrations/       Schema and row-level security policies
tests/                     Offline pytest suite
```

## Running it locally

Requires Python 3.10+ and a Supabase project.

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env   # then fill in your keys
```

Apply [`supabase/migrations`](supabase/migrations) to your Supabase project,
then start the API:

```bash
uvicorn app.main:app --reload
```

Protected endpoints expect a Supabase Auth access token in an
`Authorization: Bearer <token>` header.

## Tests

```bash
python -m pytest tests
```

The suite uses mocked provider responses and needs no credentials.
`tests/manual_test.py` calls the real OpenAI API and only runs when
`RUN_LIVE_LLM_TESTS=1` and `OPENAI_API_KEY` are set.
