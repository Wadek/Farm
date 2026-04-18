# Farm Network – Claude Reference Document

**Repo:** github.com/Wadek/Farm  
**Stack:** Python 3.11, FastAPI, SQLAlchemy, SQLite, Claude Code CLI  
**Hosted:** Local (Linux Chromebook / desktop via network mount)  
**Author:** github.com/Wadek

---

## Doctrine

Follows CyberOW: github.com/Wadek/cyberOW — read `CLAUDE.md` there for full principles.

Short form:
- Evidence-first: consequential outputs go to append-only ledger tables before being acted on
- Pull over push: no automation initiates destructive actions without an explicit trigger
- Least privilege: roles scoped at the API layer, not just the model layer
- No personal data in committed code or git history

---

## Project context

A hyperlocal food network for a community of ~5000 families within 20km.
Gamified with MYC tokens (minted from kcal + CO2 saved vs industrial supply chain, distance-decayed).
Node network delivery — walkable, horse, ATV range.
Farmers range from single grow box to 5-hectare fields.

Prior versions for reference (do not port code blindly — use for concept reference only):
- `~/projects/mycelium` — Flutter/PocketBase version, has HyphaeLogic token engine in Dart
- `~/kariniemi-farms` — Flutter/Firebase version, has auth and marketplace screens

---

## Environment

```
venv:     /home/waka/projects/Farm/venv
run:      ./venv/bin/uvicorn main:app --reload
test:     ./venv/bin/pytest tests/ -v
claude:   /home/waka/.local/bin/claude
db:       data/farm.db (gitignored)
```

---

## Data model summary

| Table              | Purpose                                    | Append-only |
|--------------------|--------------------------------------------|-------------|
| users              | Farmer or buyer accounts                   | No          |
| nodes              | Growing locations with GPS + MYC balance   | No          |
| produce            | What a node grows (kcal, CO2 data)         | No          |
| listings           | Produce offered for trade/sale             | No          |
| transactions       | Ledger of completed exchanges + MYC minted | Yes         |
| messages           | Buyer ↔ farmer comms                       | No          |
| journal_sessions   | Context snapshot for daily tip sessions    | Yes         |
| journal_entries    | Per-question Claude CLI responses          | Yes         |

---

## What is built

- All 8 models with SQLAlchemy
- Journal tip system: context builder (Open-Meteo weather), 10 question templates, Claude CLI runner
- Routes: `POST /tips/daily`, `GET /tips/session/{id}`, `GET /tips/today`
- 15/15 tests passing

## What is not yet built

- MYC token engine (port HyphaeLogic from `~/projects/mycelium/mycelium_network/lib/logic/hyphae_logic.dart`)
- Auth (JWT)
- API routes for nodes, produce, listings, transactions, messages
- Neighbourhood aggregation view
- Frontend (deferred)
- CyberOW test suite integration (see github.com/Wadek/cyberOW `docs/test-suite-spec.md`)

---

## Security notes

- Git identity: `Wadek@users.noreply.github.com`
- Author works in critical infrastructure (do not add employer references to any file)
- All secrets via `.env` (gitignored) — never hardcoded
