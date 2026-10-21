"""Shared ANSI color utilities for Hermes CLI modules."""

import os
import sys


def should_use_color() -> bool:
    """Return True when colored output is appropriate."""
    if os.environ.get("NO_COLOR") is not None or os.environ.get("TERM") == "dumb":
        return False
    return bool(sys.stdout.isatty())


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"


def color(text: str, *codes) -> str:
    """Apply color codes to text (only when color output is appropriate).

    The text is first run through the active skin's ``glyph_aliases``, so every CLI subcommand
    that colors a banner or a warning (``hermes status``, ``doctor``, ``setup``, ``update`` …)
    honors an ASCII-only skin. A skin without aliases changes nothing.
    """
    try:
        from hermes_cli.skin_engine import apply_glyph_aliases
        text = apply_glyph_aliases(text)
    except Exception:
        pass
    if not should_use_color():
        return text
    return "".join(codes) + text + Colors.RESET
