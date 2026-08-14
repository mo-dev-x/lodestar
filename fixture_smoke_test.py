def test_fixture_smoke(tmp_path, monkeypatch):
    p = tmp_path / "x.txt"
    p.write_text("ok", encoding="utf-8")
    monkeypatch.setenv("FIXTURE_SMOKE", "1")
    assert p.read_text(encoding="utf-8") == "ok"
