"""Tests for sync.diff — event change detection logic."""

from datetime import datetime, timedelta, timezone

from sync.diff import compute_diff, SyncDiff
from tests.conftest import make_future_event, BRT_OFFSET


def _state_entry(event, google_id: str) -> dict:
    """Build a state dict entry that matches a given CalendarEvent exactly."""
    return {
        "google_id": google_id,
        "sequence": event.sequence,
        "dtstart": event.dtstart.isoformat(),
        "dtend": event.dtend.isoformat(),
        "summary": event.summary,
    }


class TestComputeDiffNewEvents:
    def test_all_new_when_state_empty(self):
        """All events are new when state is empty."""
        e1 = make_future_event(uid="uid-1", summary="Evento 1")
        e2 = make_future_event(uid="uid-2", summary="Evento 2")
        current = {"uid-1": e1, "uid-2": e2}

        diff = compute_diff(current, {})

        assert len(diff.to_create) == 2
        assert len(diff.to_update) == 0
        assert len(diff.to_delete) == 0

    def test_new_event_not_in_state(self):
        """An event not in saved state should be marked as new."""
        existing = make_future_event(uid="uid-existing", summary="Existente")
        new_event = make_future_event(uid="uid-new", summary="Novo")

        state = {"uid-existing": _state_entry(existing, "g-123")}
        current = {"uid-existing": existing, "uid-new": new_event}

        diff = compute_diff(current, state)

        assert len(diff.to_create) == 1
        assert diff.to_create[0].uid == "uid-new"


class TestComputeDiffUpdatedEvents:
    def test_updated_when_sequence_changes(self):
        """An event with changed SEQUENCE should be marked as updated."""
        event = make_future_event(uid="uid-1", summary="Atualizado", sequence=5)
        state = {
            "uid-1": {
                "google_id": "g-456",
                "sequence": 3,  # different from current sequence=5
                "dtstart": event.dtstart.isoformat(),
                "dtend": event.dtend.isoformat(),
                "summary": event.summary,
            }
        }
        current = {"uid-1": event}

        diff = compute_diff(current, state)

        assert len(diff.to_update) == 1
        updated_event, google_id = diff.to_update[0]
        assert updated_event.uid == "uid-1"
        assert google_id == "g-456"

    def test_updated_when_dtstart_changes(self):
        """An event with changed start time should be marked as updated."""
        event = make_future_event(uid="uid-1", summary="Reunião", sequence=0, hours_from_now=4)
        old_start = (event.dtstart + timedelta(hours=1)).isoformat()  # saved as 1h later
        state = {
            "uid-1": {
                "google_id": "g-789",
                "sequence": 0,
                "dtstart": old_start,
                "dtend": event.dtend.isoformat(),
                "summary": event.summary,
            }
        }
        current = {"uid-1": event}

        diff = compute_diff(current, state)

        assert len(diff.to_update) == 1

    def test_updated_when_dtend_changes(self):
        """An event with changed end time should be marked as updated."""
        event = make_future_event(uid="uid-1", summary="Reunião", sequence=0, hours_from_now=4)
        old_end = (event.dtend + timedelta(hours=1)).isoformat()  # saved as 1h later
        state = {
            "uid-1": {
                "google_id": "g-789",
                "sequence": 0,
                "dtstart": event.dtstart.isoformat(),
                "dtend": old_end,
                "summary": event.summary,
            }
        }
        current = {"uid-1": event}

        diff = compute_diff(current, state)

        assert len(diff.to_update) == 1

    def test_updated_when_summary_changes(self):
        """An event with changed summary should be marked as updated."""
        event = make_future_event(uid="uid-1", summary="Título Novo", sequence=0)
        state = {
            "uid-1": {
                "google_id": "g-789",
                "sequence": 0,
                "dtstart": event.dtstart.isoformat(),
                "dtend": event.dtend.isoformat(),
                "summary": "Título Antigo",  # different
            }
        }
        current = {"uid-1": event}

        diff = compute_diff(current, state)

        assert len(diff.to_update) == 1

    def test_no_update_when_nothing_changed(self):
        """An event with same sequence, dtstart, dtend, summary should NOT be updated."""
        event = make_future_event(uid="uid-1", summary="Sem Mudança", sequence=2)
        state = {"uid-1": _state_entry(event, "g-111")}
        current = {"uid-1": event}

        diff = compute_diff(current, state)

        assert len(diff.to_update) == 0
        assert len(diff.to_create) == 0
        assert len(diff.to_delete) == 0


class TestComputeDiffDeletedEvents:
    def test_deleted_when_uid_removed_from_ics(self):
        """An event in state but absent from current ICS should be marked as deleted."""
        kept_event = make_future_event(uid="uid-kept", summary="Mantido")
        state = {
            "uid-deleted": {
                "google_id": "g-del-1", "sequence": 0,
                "dtstart": "2026-01-01T10:00:00", "dtend": "2026-01-01T11:00:00",
                "summary": "Excluído",
            },
            "uid-kept": _state_entry(kept_event, "g-keep-1"),
        }
        current = {"uid-kept": kept_event}

        diff = compute_diff(current, state)

        assert len(diff.to_delete) == 1
        deleted_ids = [gid for gid, _ in diff.to_delete]
        assert "g-del-1" in deleted_ids

    def test_deleted_carries_summary(self):
        """Deleted events should carry their summary for logging."""
        state = {
            "uid-a": {
                "google_id": "g-a", "sequence": 0,
                "dtstart": "2026-01-01T10:00:00", "dtend": "2026-01-01T11:00:00",
                "summary": "Evento A",
            },
        }

        diff = compute_diff({}, state)

        assert len(diff.to_delete) == 1
        google_id, summary = diff.to_delete[0]
        assert google_id == "g-a"
        assert summary == "Evento A"

    def test_all_deleted_when_ics_empty(self):
        """If ICS has no events, all state entries should be deleted."""
        state = {
            "uid-a": {
                "google_id": "g-a", "sequence": 0,
                "dtstart": "2026-01-01T10:00:00", "dtend": "2026-01-01T11:00:00",
                "summary": "A",
            },
            "uid-b": {
                "google_id": "g-b", "sequence": 0,
                "dtstart": "2026-01-02T10:00:00", "dtend": "2026-01-02T11:00:00",
                "summary": "B",
            },
        }

        diff = compute_diff({}, state)

        assert len(diff.to_delete) == 2
        deleted_ids = {gid for gid, _ in diff.to_delete}
        assert deleted_ids == {"g-a", "g-b"}


class TestComputeDiffMixedScenario:
    def test_realistic_mixed_diff(self):
        """Simulate a realistic scenario with new, updated, unchanged, and deleted events."""
        new_event = make_future_event(uid="uid-new", summary="Novo Evento", hours_from_now=4)
        updated_event = make_future_event(uid="uid-updated", summary="Evento Atualizado", sequence=5)
        unchanged_event = make_future_event(uid="uid-unchanged", summary="Sem Mudança", sequence=2)

        current = {
            "uid-new": new_event,
            "uid-updated": updated_event,
            "uid-unchanged": unchanged_event,
        }

        state = {
            # sequence=3 → triggers update (current is 5)
            "uid-updated": {
                "google_id": "g-upd", "sequence": 3,
                "dtstart": updated_event.dtstart.isoformat(),
                "dtend": updated_event.dtend.isoformat(),
                "summary": updated_event.summary,
            },
            # exact match → no update
            "uid-unchanged": _state_entry(unchanged_event, "g-unch"),
            # not in current → deleted
            "uid-deleted": {
                "google_id": "g-del", "sequence": 0,
                "dtstart": "2026-01-01T10:00:00", "dtend": "2026-01-01T11:00:00",
                "summary": "Deletado",
            },
        }

        diff = compute_diff(current, state)

        assert len(diff.to_create) == 1
        assert diff.to_create[0].uid == "uid-new"

        assert len(diff.to_update) == 1
        assert diff.to_update[0][0].uid == "uid-updated"
        assert diff.to_update[0][1] == "g-upd"

        assert len(diff.to_delete) == 1
        deleted_ids = [gid for gid, _ in diff.to_delete]
        assert "g-del" in deleted_ids
