import json
import logging
from datetime import datetime, date

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from sync.ics_parser import CalendarEvent

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TITLE_PREFIX = "BS2"


def _get_service(credentials_json: str):
    """Build Google Calendar API service from credentials JSON string."""
    creds_info = json.loads(credentials_json)
    credentials = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _build_event_body(event: CalendarEvent) -> dict:
    """Convert a CalendarEvent into a Google Calendar API event body."""
    title = f"{TITLE_PREFIX} - {event.summary}"

    if event.all_day:
        start = {"date": event.dtstart.isoformat()}
        end = {"date": event.dtend.isoformat()}
    else:
        dtstart = event.dtstart
        dtend = event.dtend
        start = {"dateTime": dtstart.isoformat(), "timeZone": str(dtstart.tzinfo) if dtstart.tzinfo else "UTC"}
        end = {"dateTime": dtend.isoformat(), "timeZone": str(dtend.tzinfo) if dtend.tzinfo else "UTC"}

    body = {
        "summary": title,
        "start": start,
        "end": end,
        # O campo "reminders" abaixo define um lembrete popup no momento do evento.
        # IMPORTANTE: como os eventos são criados por uma Service Account (não por um
        # usuário real), este lembrete fica associado à conta da Service Account, que
        # não possui app nem dispositivo — portanto a notificação push NUNCA é entregue
        # por este mecanismo.
        #
        # Para receber notificações push, configure um lembrete padrão diretamente no
        # app do Google Calendar: selecione o calendário compartilhado → Configurações
        # → "Notificações de eventos" → adicione o lembrete desejado. Isso é aplicado
        # no contexto do usuário real e o app dispara a push normalmente.
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 0},
            ],
        },
    }

    if event.rrule:
        body["recurrence"] = [f"RRULE:{event.rrule}"]
        
    return body


def create_event(
    credentials_json: str, calendar_id: str, event: CalendarEvent
) -> str:
    """Create a new event in Google Calendar. Returns the Google event ID."""
    service = _get_service(credentials_json)
    body = _build_event_body(event)
    result = (
        service.events()
        .insert(calendarId=calendar_id, body=body)
        .execute()
    )
    google_id = result["id"]
    logger.info("Created event '%s' → Google ID %s", event.summary, google_id)
    return google_id


def update_event(
    credentials_json: str,
    calendar_id: str,
    google_event_id: str,
    event: CalendarEvent,
) -> None:
    """Update an existing event in Google Calendar."""
    service = _get_service(credentials_json)
    body = _build_event_body(event)
    service.events().update(
        calendarId=calendar_id, eventId=google_event_id, body=body
    ).execute()
    logger.info("Updated event '%s' (Google ID %s)", event.summary, google_event_id)

def delete_event(
    credentials_json: str, calendar_id: str, google_event_id: str
) -> None:
    """Delete an event from Google Calendar."""
    service = _get_service(credentials_json)
    try:
        service.events().delete(
            calendarId=calendar_id, eventId=google_event_id
        ).execute()
        logger.info("Deleted Google event %s", google_event_id)
    except Exception:
        logger.warning(
            "Failed to delete Google event %s (may already be gone)",
            google_event_id,
        )
