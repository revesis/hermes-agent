"""Status-bar and prompt-state markers follow the active skin's ``glyphs:`` block.

An emoji-free skin (see ``~/.hermes/skins/ascii.yaml``) sets these to plain ASCII; unset keys
keep the renderer's built-in marker so existing skins are unaffected.
"""

import sys
import time
import types

from hermes_cli import skin_engine as se
from hermes_cli.cli_status_bar_mixin import CLIStatusBarMixin as Bar


def _activate(monkeypatch, glyphs):
    monkeypatch.setattr(se, "get_active_skin", lambda: se.SkinConfig(name="t", glyphs=glyphs))


def test_context_bar_uses_ascii_glyphs(monkeypatch):
    _activate(monkeypatch, {"bar_filled": "#", "bar_empty": "."})
    bar = object.__new__(Bar)
    assert Bar._build_context_bar(bar, 50, 10) == "[#####.....]"


def test_context_bar_keeps_block_glyphs_by_default(monkeypatch):
    _activate(monkeypatch, {})
    bar = object.__new__(Bar)
    assert Bar._build_context_bar(bar, 50, 10) == "[█████░░░░░]"


def test_context_bar_clamps_out_of_range_percent(monkeypatch):
    _activate(monkeypatch, {"bar_filled": "#", "bar_empty": "."})
    bar = object.__new__(Bar)
    assert Bar._build_context_bar(bar, 140, 4) == "[####]"
    assert Bar._build_context_bar(bar, -20, 4) == "[....]"


def test_timer_glyphs(monkeypatch):
    _activate(monkeypatch, {"timer": "t", "timer_frozen": "t"})
    assert Bar._format_prompt_elapsed(None, 0) == "t 0s"
    assert Bar._format_prompt_elapsed(time.time() - 5, 0, live=True).startswith("t ")


def test_timer_glyphs_default_to_clock(monkeypatch):
    _activate(monkeypatch, {})
    assert Bar._format_prompt_elapsed(None, 0) == "⏲ 0s"


def _stub_cli(monkeypatch):
    """``_format_idle_since`` imports ``cli`` for the duration formatter; importing the real
    module does live home I/O, which the test harness forbids."""
    stub = types.SimpleNamespace(format_duration_compact=lambda secs: f"{int(secs)}s")
    monkeypatch.setitem(sys.modules, "cli", stub)


def test_idle_glyph(monkeypatch):
    _activate(monkeypatch, {"idle": "ok"})
    _stub_cli(monkeypatch)
    assert Bar._format_idle_since(time.time() - 5, False).startswith("ok ")


def test_idle_glyph_defaults_to_check(monkeypatch):
    _activate(monkeypatch, {})
    _stub_cli(monkeypatch)
    assert Bar._format_idle_since(time.time() - 5, False).startswith("✓ ")


def test_empty_glyph_value_falls_back(monkeypatch):
    """A blank value must not blank the element."""
    _activate(monkeypatch, {"timer": "   "})
    assert Bar._format_prompt_elapsed(None, 0) == "⏲ 0s"
