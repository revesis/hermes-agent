"""Tests for get_tool_emoji in agent/display.py — skin + registry integration."""

from unittest.mock import patch as mock_patch, MagicMock

from agent.display import get_tool_emoji


class TestGetToolEmoji:
    """Verify the skin → registry → fallback resolution chain."""





    def test_custom_default(self):
        """Custom default is returned when nothing matches."""
        with mock_patch("agent.display._get_skin", return_value=None):
            mock_reg = MagicMock()
            mock_reg.get_emoji.return_value = ""
            import sys
            mock_module = MagicMock()
            mock_module.registry = mock_reg
            with mock_patch.dict(sys.modules, {"tools.registry": mock_module}):
                result = get_tool_emoji("x", default="⚙️")
                assert result == "⚙️"

    def test_skin_override_only_for_matching_tool(self):
        """Skin override for one tool doesn't affect others."""
        skin = MagicMock()
        skin.tool_emojis = {"terminal": "⚔"}
        mock_reg = MagicMock()
        mock_reg.get_emoji.return_value = "🔍"
        import sys
        mock_module = MagicMock()
        mock_module.registry = mock_reg
        with mock_patch("agent.display._get_skin", return_value=skin), \
             mock_patch.dict(sys.modules, {"tools.registry": mock_module}):
            assert get_tool_emoji("terminal") == "⚔"  # skin override
            assert get_tool_emoji("web_search") == "🔍"  # registry fallback


class TestSkinConfigToolEmojis:
    """Verify SkinConfig handles tool_emojis field correctly."""



    def test_build_skin_config_includes_tool_emojis(self):
        from hermes_cli.skin_engine import _build_skin_config
        data = {
            "name": "custom",
            "tool_emojis": {"terminal": "🗡️", "patch": "⚒️"},
        }
        skin = _build_skin_config(data)
        assert skin.tool_emojis == {"terminal": "🗡️", "patch": "⚒️"}


class TestGetToolEmojiGlyphFallback:
    """An emoji-free skin can replace the ⚡ fallback via ``glyphs.tool_default``."""

    @staticmethod
    def _skin_with_glyphs(glyphs):
        skin = MagicMock()
        skin.tool_emojis = {}
        skin.get_glyph.side_effect = lambda key, fallback: glyphs.get(key, fallback)
        return skin

    @staticmethod
    def _empty_registry():
        mock_reg = MagicMock()
        mock_reg.get_emoji.return_value = ""
        import sys
        mock_module = MagicMock()
        mock_module.registry = mock_reg
        return mock_patch.dict(sys.modules, {"tools.registry": mock_module})

    def test_skin_glyph_replaces_default(self):
        skin = self._skin_with_glyphs({"tool_default": "*"})
        with mock_patch("agent.display._get_skin", return_value=skin), self._empty_registry():
            assert get_tool_emoji("some_unknown_tool") == "*"

    def test_explicit_default_beats_skin_glyph(self):
        """Callers that name their own marker (gateway's ⚙️) are unaffected by the skin."""
        skin = self._skin_with_glyphs({"tool_default": "*"})
        with mock_patch("agent.display._get_skin", return_value=skin), self._empty_registry():
            assert get_tool_emoji("some_unknown_tool", default="⚙️") == "⚙️"

    def test_no_skin_keeps_emoji_default(self):
        with mock_patch("agent.display._get_skin", return_value=None), self._empty_registry():
            assert get_tool_emoji("some_unknown_tool") == "⚡"

    def test_skin_without_glyphs_keeps_emoji_default(self):
        skin = self._skin_with_glyphs({})
        with mock_patch("agent.display._get_skin", return_value=skin), self._empty_registry():
            assert get_tool_emoji("some_unknown_tool") == "⚡"

