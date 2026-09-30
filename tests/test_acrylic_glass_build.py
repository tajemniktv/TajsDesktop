"""Build-phase regressions; these do not test loading the effect in KWin."""

from unittest.mock import Mock

import pytest

from steps import acrylic_glass


@pytest.fixture
def build_context(tmp_path, monkeypatch):
    src = tmp_path / "source"
    src.mkdir()
    build = tmp_path / "build"
    monkeypatch.setattr(acrylic_glass, "SRC", src)
    monkeypatch.setattr(acrylic_glass, "BUILD", build)
    compile_effect = Mock()
    monkeypatch.setattr(acrylic_glass, "cmake_build", compile_effect)

    # Fail at the boundary so a regression never reaches a real desktop.
    monkeypatch.setattr(acrylic_glass, "kw_write", Mock(
        side_effect=AssertionError("build must not write KDE settings")))
    monkeypatch.setattr(acrylic_glass, "qdbus_call", Mock(
        side_effect=AssertionError("build must not contact live D-Bus")))
    return src, build, compile_effect


@pytest.mark.parametrize("build_succeeded", [True, False], ids=["success", "failure"])
def test_build_preserves_live_settings_and_effects(build_context, build_succeeded):
    src, build, compile_effect = build_context
    (src / "CMakeLists.txt").write_text("# build source\n")
    compile_effect.return_value = build_succeeded

    assert acrylic_glass.build() is None

    compile_effect.assert_called_once_with(src, build, "Acrylic Glass")
    acrylic_glass.kw_write.assert_not_called()
    acrylic_glass.qdbus_call.assert_not_called()


def test_build_exception_preserves_live_settings_and_effects(build_context):
    src, build, compile_effect = build_context
    (src / "CMakeLists.txt").write_text("# build source\n")
    compile_effect.side_effect = OSError("compiler unavailable")

    with pytest.raises(OSError, match="compiler unavailable"):
        acrylic_glass.build()

    compile_effect.assert_called_once_with(src, build, "Acrylic Glass")
    acrylic_glass.kw_write.assert_not_called()
    acrylic_glass.qdbus_call.assert_not_called()


def test_build_skips_missing_source_without_live_changes(build_context):
    _, _, compile_effect = build_context

    assert acrylic_glass.build() is None

    compile_effect.assert_not_called()
    acrylic_glass.kw_write.assert_not_called()
    acrylic_glass.qdbus_call.assert_not_called()
