"""Tests for sync.diff — event change detection logic."""

from datetime import datetime, timedelta, timezone

from sync.diff import compute_diff, SyncDiff
from tests.conftest import make_future_event, BRT_OFFSET


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

        state = {
            "uid-existing": {"google_id": "g-123", "sequence": 0, "last_modified": ""},
        }
        current = {"uid-existing": existing, "uid-new": new_event}

        diff = compute_diff(current, state)

        assert len(diff.to_create) == 1
        assert diff.to_create[0].uid == "uid-new"


class TestComputeDiffUpdatedEvents:
    def test_updated_when_sequence_changes(self):
        """An event with changed SEQUENCE should be marked as updated."""
        event = make_future_event(uid="uid-1", summary="Atualizado", sequence=5)
        state = {"uid-1": {"google_id": "g-456", "sequence": 3, "last_modified": ""}}
        current = {"uid-1": event}

        diff = compute_diff(current, state)

        assert len(diff.to_update) == 1
        updated_event, google_id = diff.to_update[0]
        assert updated_event.uid == "uid-1"
        assert google_id == "g-456"

    def test_updated_when_last_modified_changes(self):
        """An event with changed LAST-MODIFIED should be marked as updated."""
        mod = datetime(2026, 3, 19, 10, 0, 0, tzinfo=timezone.utc)
        event = make_future_event(uid="uid-1", summary="Teste", sequence=0, last_modified=mod)
        state = {
            "uid-1": {
                "google_id": "g-789",
                "sequence": 0,
                "last_modified": "2026-03-18T10:00:00+00:00",
            }
        }
        current = {"uid-1": event}

        diff = compute_diff(current, state)

        assert len(diff.to_update) == 1

    def test_no_update_when_nothing_changed(self):
        """An event with same SEQUENCE and LAST-MODIFIED should NOT be updated."""
        event = make_future_event(uid="uid-1", summary="Sem Mudança", sequence=2)
        state = {"uid-1": {"google_id": "g-111", "sequence": 2, "last_modified": ""}}
        current = {"uid-1": event}

        diff = compute_diff(current, state)

        assert len(diff.to_update) == 0
        assert len(diff.to_create) == 0
        assert len(diff.to_delete) == 0


class TestComputeDiffDeletedEvents:
    def test_deleted_when_uid_removed_from_ics(self):
        """An event in state but absent from current ICS should be marked as deleted."""
        state = {
            "uid-deleted": {"google_id": "g-del-1", "sequence": 0, "last_modified": ""},
            "uid-kept": {"google_id": "g-keep-1", "sequence": 0, "last_modified": ""},
        }
        kept_event = make_future_event(uid="uid-kept", summary="Mantido")
        current = {"uid-kept": kept_event}

        diff = compute_diff(current, state)

        assert len(diff.to_delete) == 1
        assert "g-del-1" in diff.to_delete

    def test_all_deleted_when_ics_empty(self):
        """If ICS has no events, all state entries should be deleted."""
        state = {
            "uid-a": {"google_id": "g-a", "sequence": 0, "last_modified": ""},
            "uid-b": {"google_id": "g-b", "sequence": 0, "last_modified": ""},
        }

        diff = compute_diff({}, state)

        assert len(diff.to_delete) == 2
        assert set(diff.to_delete) == {"g-a", "g-b"}


class TestComputeDiffMixedScenario:
    def test_realistic_mixed_diff(self):
        """Simulate a realistic scenario with new, updated, unchanged, and deleted events."""
        now = datetime.now(BRT_OFFSET)

        # Current ICS events
        new_event = make_future_event(uid="uid-new", summary="Novo Evento", hours_from_now=4)
        updated_event = make_future_event(uid="uid-updated", summary="Evento Atualizado", sequence=5)
        unchanged_event = make_future_event(uid="uid-unchanged", summary="Sem Mudança", sequence=2)

        current = {
            "uid-new": new_event,
            "uid-updated": updated_event,
            "uid-unchanged": unchanged_event,
        }

        # Saved state
        state = {
            "uid-updated": {"google_id": "g-upd", "sequence": 3, "last_modified": ""},
            "uid-unchanged": {"google_id": "g-unch", "sequence": 2, "last_modified": ""},
            "uid-deleted": {"google_id": "g-del", "sequence": 0, "last_modified": ""},
        }

        diff = compute_diff(current, state)

        assert len(diff.to_create) == 1
        assert diff.to_create[0].uid == "uid-new"

        assert len(diff.to_update) == 1
        assert diff.to_update[0][0].uid == "uid-updated"
        assert diff.to_update[0][1] == "g-upd"

        assert len(diff.to_delete) == 1
        assert "g-del" in diff.to_delete
