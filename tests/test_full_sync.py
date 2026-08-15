from jellyfin_kodi import full_sync
from jellyfin_kodi.full_sync import FullSync


def test_mapping_resumes_pending_sync_without_dialog(monkeypatch):
    restore_point = {"params": {"StartIndex": 100}}
    sync_state = {
        "Libraries": ["library-id"],
        "RestorePoint": restore_point,
    }
    instance = FullSync.__new__(FullSync)
    instance.sync = sync_state
    saved = []

    def unexpected_dialog(*args, **kwargs):
        raise AssertionError("Interrupted sync recovery must not show a dialog")

    monkeypatch.setattr(full_sync, "dialog", unexpected_dialog)
    monkeypatch.setattr(full_sync, "save_sync", saved.append)

    instance.mapping()

    assert instance.sync["Libraries"] == ["library-id"]
    assert instance.sync["RestorePoint"] == restore_point
    assert saved == [sync_state]
