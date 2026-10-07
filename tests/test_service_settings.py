"""Настройки услуги по номеру — фронт пишет, бот читает."""

from backend.services import service_settings as svc


def test_defaults_and_update(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "SETTINGS_PATH", tmp_path / "service_settings.json")
    phone = "79001112233"
    base = svc.get_settings(phone)
    assert base["routing"] == "voice"
    assert base["history"] is True
    assert base["notify"] == "all"

    updated = svc.update_settings(
        phone,
        routing="chat",
        history=False,
        notify="critical",
        mode="loyal",
        hotline=False,
    )
    assert updated["routing"] == "chat"
    assert updated["history"] is False
    assert updated["notify"] == "critical"
    assert updated["mode"] == "loyal"
    assert updated["hotline"] is False
    assert svc.get_settings(phone)["scenarios"] is True

    hybrid = svc.update_settings(
        phone,
        routing="hybrid",
        template_greeting="Привет!",
        template_faq="FAQ",
    )
    assert hybrid["routing"] == "hybrid"
    assert hybrid["template_greeting"] == "Привет!"
    assert hybrid["template_faq"] == "FAQ"

    assert svc.get_settings(phone)["connected"] is False
    on = svc.update_settings(phone, connected=True)
    assert on["connected"] is True
    assert svc.get_settings(phone)["connected"] is True
    off = svc.update_settings(phone, connected=False)
    assert off["connected"] is False


if __name__ == "__main__":
    from pathlib import Path
    import tempfile

    class _MP:
        def setattr(self, obj, name, value):
            setattr(obj, name, value)

    with tempfile.TemporaryDirectory() as td:
        test_defaults_and_update(Path(td), _MP())
    print("ALL TESTS PASSED (1)")
