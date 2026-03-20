# CalendarSync — Outlook ICS → Google Calendar

## Context
- **Source**: Outlook calendar (Company A) via published .ics URL
- **Destination**: Google Calendar (personal Gmail account)
- **Direction**: Unidirectional (Outlook → Google)
- **Fields**: Title only, format: "BS2 - {original title}"
- **Latency**: 5 minutes (polling)
- **Hosting**: Azure Functions (Consumption Plan)
- **Language**: Python 3.11+

## Architecture
Azure Function (Timer Trigger, 3 min interval) → Fetch .ics → Parse → Diff with saved state → Sync to Google Calendar API → Save state to Azure Blob Storage

## Project Structure
```
CalendarSync/
├── function_app.py          # Timer trigger entry point (every 5 min)
├── host.json                # Azure Functions config
├── requirements.txt         # Python dependencies
├── local.settings.json      # Environment variables (local, not committed)
├── .funcignore              # Deploy exclusions
└── sync/
    ├── __init__.py
    ├── ics_parser.py        # Fetch + parse .ics using icalendar lib
    ├── diff.py              # Diff logic (new, updated, deleted events)
    ├── google_calendar.py   # Google Calendar API wrapper (create/update/delete)
    └── state.py             # State management via Azure Blob Storage
```

## Sync Flow
1. **Fetch** — Download .ics from published Outlook calendar URL
2. **Parse** — Extract VEVENT components: UID, DTSTART, DTEND, SUMMARY, SEQUENCE, LAST-MODIFIED
3. **Diff** — Compare with saved state:
   - **New**: UID not in state → `events.insert()` in Google Calendar
   - **Updated**: UID exists but SEQUENCE/LAST-MODIFIED changed → `events.update()`
   - **Deleted**: UID in state but absent from .ics → `events.delete()`
4. **Persist** — Save updated state to Azure Blob Storage as JSON:
   ```json
   { "outlook_uid": { "google_id": "...", "sequence": 0, "last_modified": "..." } }
   ```

## Tech Stack
| Component | Technology |
|---|---|
| Runtime | Python 3.11+ |
| Hosting | Azure Functions (Consumption Plan — 1M exec/month free, ~14.4K exec/month at 3 min interval) |
| State | Azure Blob Storage (included with Function App) |
| ICS parsing | `icalendar` Python lib |
| Google API | `google-api-python-client` + `google-auth` |
| Auth | Google Service Account |

## Decisions
- Unidirectional only (Outlook → Google), no write-back
- Title only copied, format "BS2 - {original title}" — no description, participants, location
- Polling every 3 minutes via Timer Trigger (no webhook available for .ics)
- Python chosen for robust icalendar parsing ecosystem
- Azure Functions Consumption Plan (effectively zero cost for this volume)
