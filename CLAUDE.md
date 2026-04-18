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

Test farm coordinates: 60.5522, 24.7050 (Korpiharjuntie, Yli-Solttila, Hyvinkää — road centroid, exact GPS pending)

---

## Data model summary

| Table            | Purpose                                           | Append-only |
|------------------|---------------------------------------------------|-------------|
| users            | Farmer or buyer accounts (JWT auth, bcrypt)       | No          |
| nodes            | Growing locations with GPS + MYC balance          | No          |
| produce          | What a node grows (kcal, CO2 data)                | No          |
| listings         | Produce offered for trade/sale                    | No          |
| transactions     | Ledger of completed exchanges + MYC minted        | Yes         |
| messages         | Buyer ↔ farmer comms                              | No          |
| journal_sessions | Context snapshot for daily tip sessions           | Yes         |
| journal_entries  | Per-question Claude CLI responses                 | Yes         |
| regional_config  | Weekly-cached spot price + regional constants     | Yes         |
| sensor_readings  | Unified Ruuvi + Ajax + manual sensor data         | Yes         |

---

## What is built (51/51 tests passing)

### Auth
- `POST /auth/register` — farmer or buyer
- `POST /auth/token` — OAuth2 password → 7-day JWT
- `GET /auth/me` — current user
- bcrypt direct (no passlib — incompatible with bcrypt 5.x)

### Nodes
- `POST /nodes` — create node (auth required)
- `GET /nodes` — list user's nodes with latest Ruuvi inline
- `GET /nodes/{id}` — node detail
- `POST /nodes/{id}/ruuvi` — manual Ruuvi reading
- `GET /nodes/{id}/ruuvi/latest` — latest Ruuvi reading
- `POST /nodes/ruuvi/webhook` — Ruuvi Station iOS webhook endpoint
- `POST /nodes/{id}/sync` — pull from Ruuvi Cloud + Ajax Cloud
- `GET /nodes/{id}/sensors` — latest reading per sensor type (unified)

### MYC Token Engine
- Port of HyphaeLogic from mycelium Dart: CO2 savings + kcal energy value
- Distance decay: `exp(-0.15 * km)` from Haversine
- Dynamic regional constants via `RegionalConstants` dataclass
- `POST /transactions/complete` — calculate + mint tokens, append to ledger
- `GET /transactions/node/{id}` — full ledger

### Regional Constants (dynamic, weekly-cached)
- `app/services/regional_service.py` — country detected by coordinate bounding box (FI/SE/NO)
- Finland: live electricity spot price from PorssisÄhkö API (`api.porssisahko.net`)
- Weekly DB snapshot in `regional_config` table (append-only)
- Supply chain constants (import_distance_km, transport_factor) are PLACEHOLDER — need data engine

### Sensor Integration
- `app/models/sensor_reading.py` — unified append-only table
- `app/services/ruuvi_cloud.py` — polls Ruuvi Cloud API (needs credentials)
- `app/services/ajax_cloud.py` — polls Ajax Systems API (needs API approval + credentials)
- Device type mapping: DoorProtect→door, MotionProtect→motion, LeaksProtect→leak, etc.

### Daily Tips (Claude CLI)
- `app/services/claude_runner.py` — isolated subprocess: `claude -p "question"`
- `POST /tips/daily` — builds context (Open-Meteo weather), fires 10 questions async
- `GET /tips/session/{id}` — poll progress
- `GET /tips/today` — latest session

### UI
- `static/index.html` — terminal-style SPA: black bg (#000), green (#00ff88), monospace
- Sections: Login, Register, Node list, Node detail (sensor panel + ledger), Daily tips
- Temperature displayed large (3rem, glowing green); Ajax status amber on triggered/open
- SYNC button calls `/nodes/{id}/sync`
- Touch-friendly: 48px targets, usable from phone

---

## Pending credentials (not in .env yet)

```
# Ruuvi Cloud — create account at ruuvi.com, sync your Ruuvi tag
RUUVI_EMAIL=
RUUVI_PASSWORD=

# Ajax Systems Cloud — request access at ajax.systems/api-request/
AJAX_EMAIL=
AJAX_PASSWORD=
```

Without these, `/nodes/{id}/sync` returns 0 readings but does not error.

---

## TODO — next session start here

1. **Update CLAUDE.md in CyberOW** — `projects/CyberOW/docs/pilots/farm.md` still shows old state
2. **Produce + Listing CRUD routes** — models exist, no API routes yet
   - `POST /nodes/{id}/produce` — add what a node grows (kcal_per_kg, co2_per_kg)
   - `POST /produce/{id}/listings` — create offer (quantity, price, available_until)
   - `GET /listings` — public browse (filter by distance from lat/lng)
3. **Ruuvi tag MAC → node mapping** — `nodes.ruuvi_mac` column needed; webhook currently falls back to first node (single-node only)
4. **Ruuvi Cloud account** — sign up, add credentials to .env, test `/nodes/{id}/sync`
5. **Ajax API access** — request at ajax.systems/api-request/, add credentials, map devices to nodes
6. **Weekly regional config auto-refresh** — currently on-demand; add a background task or cron trigger
7. **Exact GPS coordinates** — Korpiharjuntie 363, Hyvinkää — update default_lat/lng once confirmed from phone
8. **Server as a service** — currently started manually; write a systemd unit or startup script
9. **Tailscale** — needed for iPhone → Chromebook when testing from phone
10. **CyberOW test suite** — spec at `projects/CyberOW/docs/test-suite-spec.md`, not yet implemented
11. **Supply chain data engine** — import_distance_km and transport factors are PLACEHOLDER; need real data source
12. **Desktop PostgreSQL migration** — SQLite now, 4TB SSD available; migration when scale warrants it

---

## Known fixes (don't redo these)

- `passlib` removed — use `import bcrypt` directly (passlib incompatible with bcrypt>=4.0)
- `pydantic_settings` v2: use `model_config = SettingsConfigDict(env_file=".env")`
- `JournalEntry.session_id` needs explicit `ForeignKey("journal_sessions.id")`
- `python-multipart` required for OAuth2 form login
- Test haversine: use precise city centres (60.6304,24.8603 → 60.1699,24.9384), expect ~51km

---

## Security notes

- Git identity: `Wadek@users.noreply.github.com`
- Author works in critical infrastructure (do not add employer references to any file)
- All secrets via `.env` (gitignored) — never hardcoded
- Sensor webhook (`POST /nodes/ruuvi/webhook`) is unauthenticated by design — local network only
