from personal_defaults import desired_defaults, preview_missing


def test_machine_profile_requires_explicit_selection():
    common = desired_defaults()
    assert "powerdevilrc" not in common
    assert desired_defaults("local-laptop")["powerdevilrc"]


def test_preview_preserves_present_and_explicit_empty_values(tmp_path):
    (tmp_path / "dolphinrc").write_text(
        "[MainWindow]\nMenuBar=\n[InformationPanel]\ndateFormat=LongFormat\n")
    preview = preview_missing(config_home=tmp_path)
    assert not any(x["key"] in {"MenuBar", "dateFormat"} for x in preview)
    assert any(x["key"] == "NewTabButton" for x in preview)


def test_no_private_or_machine_identifiers_in_profiles():
    import json
    from personal_defaults import PROFILE_DIR
    for name in ("common", "local-laptop"):
        payload = json.dumps(desired_defaults(name)).lower()
        assert not any(token in payload for token in (
            "/home/", "uuid", "password", "token", "ssid", "deviceid",
            "serial", "cookie", "sessionstore"))
        assert (PROFILE_DIR / f"{name}.json").exists()
