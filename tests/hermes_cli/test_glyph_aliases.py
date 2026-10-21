"""``glyph_aliases``: a skin rewrites emoji baked into locale catalogs.

The ASCII skin maps ``⚠️``/``✓``/``✦``/``↻`` … to plain tokens; every ``t()`` result is run
through the map, and skins without aliases (all built-ins) are untouched.
"""

from pathlib import Path

from hermes_cli import skin_engine as se
from hermes_cli.skin_engine import _build_skin_config, apply_glyph_aliases


def _activate(monkeypatch, aliases):
    skin = se.SkinConfig(name="t", glyph_aliases=aliases)
    monkeypatch.setattr(se, "get_active_skin", lambda: skin)


def test_build_parses_aliases_longest_first():
    skin = _build_skin_config({"name": "x", "glyph_aliases": {"⚠": "!", "⚠️": "!", "✓": "ok"}})
    # "⚠️" (2 codepoints) must be tried before "⚠", or a stray VS16 survives.
    assert list(skin.glyph_aliases) == ["⚠️", "⚠", "✓"]


def test_build_drops_junk_aliases():
    """Non-string and empty *source* markers are dropped; an empty replacement means 'delete'."""
    skin = _build_skin_config({"name": "x", "glyph_aliases": {"ok": "", 3: "!", "": "z"}})
    assert skin.glyph_aliases == {"ok": ""}


def test_apply_rewrites_markers(monkeypatch):
    _activate(monkeypatch, {"⚠️": "!", "✓": "ok", "✦": "*"})
    assert apply_glyph_aliases("⚠️ Tip: hi") == "! Tip: hi"
    assert apply_glyph_aliases("✓ done ✦") == "ok done *"


def test_apply_leaves_plain_text_alone(monkeypatch):
    _activate(monkeypatch, {"⚠️": "!"})
    assert apply_glyph_aliases("nothing to do here") == "nothing to do here"


def test_apply_strips_stray_variation_selector(monkeypatch):
    _activate(monkeypatch, {"⚠": "!"})
    assert apply_glyph_aliases("⚠️ warn") == "! warn"
    assert "\ufe0f" not in apply_glyph_aliases("⚠️ warn")


def test_no_aliases_is_a_noop(monkeypatch):
    _activate(monkeypatch, {})
    assert apply_glyph_aliases("⚠️ untouched") == "⚠️ untouched"


def test_translation_runs_through_aliases(monkeypatch):
    from agent import i18n

    monkeypatch.setattr(i18n, "_current_home", lambda: Path("/nonexistent"))
    monkeypatch.setattr(i18n, "_resolve_language", lambda home: "en")
    monkeypatch.setattr(i18n, "_load_catalog", lambda lang, home: {
        "cli.resume.resumed_many": "↻ Resumed session **{title}** ({count} messages).",
        "cli.tip_line": "✦ Tip: {tip}",
    })
    _activate(monkeypatch, {"↻": "R", "✦": "*"})
    assert i18n.t("cli.resume.resumed_many", title="x", count=7) == "R Resumed session **x** (7 messages)."
    assert i18n.t("cli.tip_line", tip="hi") == "* Tip: hi"
