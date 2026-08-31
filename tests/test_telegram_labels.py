"""_patch_telegram_model_labels — wraps the adapter keyboard, relabels only
the model-selection buttons, and degrades gracefully when the adapter has no
keyboard to patch."""

from __future__ import annotations

import sys
import types

import pytest


class _FakeButton:
    def __init__(self, text, callback_data=None):
        self.text = text
        self.callback_data = callback_data


class _FakeMarkup:
    def __init__(self, inline_keyboard):
        self.inline_keyboard = inline_keyboard


def _make_adapter_class(*, with_keyboard: bool):
    """A stand-in TelegramAdapter whose original _build_model_keyboard mirrors
    the real adapter's callback-data scheme (``mm:<idx>`` for model buttons,
    ``mg:``/``mb``/``mx`` for nav)."""

    class TelegramAdapter:
        _MODEL_PAGE_SIZE = 4

        if with_keyboard:

            def _build_model_keyboard(self, model_list, page):
                page_size = self._MODEL_PAGE_SIZE
                start = page * page_size
                end = min(start + page_size, len(model_list))
                rows = [
                    [
                        _FakeButton(str(model_list[i]), callback_data=f"mm:{i}")
                        for i in range(start, end)
                    ],
                    [
                        _FakeButton("◀ Back", callback_data="mb"),
                        _FakeButton("✗ Cancel", callback_data="mx"),
                    ],
                ]
                return _FakeMarkup(rows), f" ({start + 1}–{end})"

    return TelegramAdapter


def _install_fake_gateway(monkeypatch, adapter_cls):
    """Wire a fake ``gateway.platforms.telegram`` into sys.modules."""
    telegram = types.ModuleType("gateway.platforms.telegram")
    telegram.TelegramAdapter = adapter_cls
    telegram.InlineKeyboardButton = _FakeButton
    telegram.InlineKeyboardMarkup = _FakeMarkup

    platforms = types.ModuleType("gateway.platforms")
    platforms.telegram = telegram
    gateway = types.ModuleType("gateway")
    gateway.platforms = platforms

    monkeypatch.setitem(sys.modules, "gateway", gateway)
    monkeypatch.setitem(sys.modules, "gateway.platforms", platforms)
    monkeypatch.setitem(sys.modules, "gateway.platforms.telegram", telegram)
    return telegram


def _install_fake_plugin_telegram(monkeypatch, adapter_cls):
    """Wire a fake ``plugins.platforms.telegram.adapter`` into sys.modules."""
    telegram = types.ModuleType("plugins.platforms.telegram.adapter")
    telegram.TelegramAdapter = adapter_cls
    telegram.InlineKeyboardButton = _FakeButton
    telegram.InlineKeyboardMarkup = _FakeMarkup

    telegram_pkg = types.ModuleType("plugins.platforms.telegram")
    telegram_pkg.adapter = telegram
    platforms = types.ModuleType("plugins.platforms")
    platforms.telegram = telegram_pkg
    plugins = types.ModuleType("plugins")
    plugins.platforms = platforms

    monkeypatch.setitem(sys.modules, "plugins", plugins)
    monkeypatch.setitem(sys.modules, "plugins.platforms", platforms)
    monkeypatch.setitem(sys.modules, "plugins.platforms.telegram", telegram_pkg)
    monkeypatch.setitem(sys.modules, "plugins.platforms.telegram.adapter", telegram)
    return telegram


def test_patch_relabels_only_model_buttons(monkeypatch):
    from clawrouter_hermes import _patch_telegram_model_labels

    adapter_cls = _make_adapter_class(with_keyboard=True)
    _install_fake_gateway(monkeypatch, adapter_cls)

    _patch_telegram_model_labels()
    assert adapter_cls._clawrouter_labels_patched is True

    # blockrun/free is free, blockrun/openai/gpt-5.5 is not.
    models = ["blockrun/free", "blockrun/openai/gpt-5.5"]
    markup, page_info = adapter_cls._build_model_keyboard(adapter_cls(), models, 0)

    model_row, nav_row = markup.inline_keyboard
    free_btn, paid_btn = model_row

    # Model buttons get compact, free-aware labels; callback data is preserved.
    assert free_btn.text == "[FREE] free"
    assert free_btn.callback_data == "mm:0"
    assert paid_btn.text == "gpt-5.5"
    assert paid_btn.callback_data == "mm:1"

    # Nav/back/cancel buttons pass through untouched.
    assert [b.text for b in nav_row] == ["◀ Back", "✗ Cancel"]
    assert [b.callback_data for b in nav_row] == ["mb", "mx"]

    # page_info is forwarded verbatim from the original method.
    assert page_info == " (1–2)"


def test_patch_relabels_active_plugin_telegram_adapter(monkeypatch):
    from clawrouter_hermes import _patch_telegram_model_labels

    adapter_cls = _make_adapter_class(with_keyboard=True)
    _install_fake_plugin_telegram(monkeypatch, adapter_cls)

    _patch_telegram_model_labels()
    assert adapter_cls._clawrouter_labels_patched is True

    models = ["blockrun/free/north-mini-code", "blockrun/openai/gpt-5.6-sol"]
    markup, _page_info = adapter_cls._build_model_keyboard(adapter_cls(), models, 0)

    free_btn, paid_btn = markup.inline_keyboard[0]
    assert free_btn.text == "[FREE] north-mini-code"
    assert free_btn.callback_data == "mm:0"
    assert paid_btn.text == "gpt-5.6-sol"
    assert paid_btn.callback_data == "mm:1"


def test_patch_is_idempotent(monkeypatch):
    from clawrouter_hermes import _patch_telegram_model_labels

    adapter_cls = _make_adapter_class(with_keyboard=True)
    _install_fake_gateway(monkeypatch, adapter_cls)

    _patch_telegram_model_labels()
    first = adapter_cls._build_model_keyboard
    _patch_telegram_model_labels()  # second call must not re-wrap
    assert adapter_cls._build_model_keyboard is first


def test_patch_noop_when_adapter_lacks_keyboard(monkeypatch):
    from clawrouter_hermes import _patch_telegram_model_labels

    adapter_cls = _make_adapter_class(with_keyboard=False)
    _install_fake_gateway(monkeypatch, adapter_cls)

    assert _patch_telegram_model_labels() is False  # must not raise
    assert getattr(adapter_cls, "_clawrouter_labels_patched", False) is False
    assert not hasattr(adapter_cls, "_build_model_keyboard")


def _install_fake_hermes_plugins_adapter(monkeypatch, adapter_cls):
    """Wire a fake Hermes ≥ 0.18 ``hermes_plugins.telegram.adapter`` into
    sys.modules — the lazily-loaded platform-plugin module name."""
    telegram = types.ModuleType("hermes_plugins.telegram.adapter")
    telegram.TelegramAdapter = adapter_cls
    telegram.InlineKeyboardButton = _FakeButton
    telegram.InlineKeyboardMarkup = _FakeMarkup
    monkeypatch.setitem(sys.modules, "hermes_plugins.telegram.adapter", telegram)
    return telegram


def test_patch_relabels_lazy_hermes_plugins_adapter(monkeypatch):
    """Hermes ≥ 0.18 loads the adapter as hermes_plugins.telegram.adapter."""
    from clawrouter_hermes import _patch_telegram_model_labels

    adapter_cls = _make_adapter_class(with_keyboard=True)
    _install_fake_hermes_plugins_adapter(monkeypatch, adapter_cls)

    assert _patch_telegram_model_labels() is True
    models = ["blockrun/free/north-mini-code", "blockrun/openai/gpt-5.6-sol"]
    markup, _page_info = adapter_cls._build_model_keyboard(adapter_cls(), models, 0)
    free_btn, paid_btn = markup.inline_keyboard[0]
    assert free_btn.text == "[FREE] north-mini-code"
    assert paid_btn.text == "gpt-5.6-sol"


def test_patch_never_imports_the_adapter_module():
    """Only modules already in sys.modules may be patched — importing the
    lazily-loaded adapter ourselves would patch a second, unused copy and
    re-add the startup cost the lazy loader exists to avoid."""
    from clawrouter_hermes import _patch_telegram_model_labels

    assert "hermes_plugins.telegram.adapter" not in sys.modules
    assert _patch_telegram_model_labels() is False
    assert "hermes_plugins.telegram.adapter" not in sys.modules


def test_typing_any_placeholder_degrades_to_passthrough(monkeypatch):
    """Until Hermes lazy-installs the telegram SDK, the adapter publishes
    typing.Any placeholders (not None) for the keyboard classes. The wrapper
    must return the original keyboard untouched instead of raising."""
    import typing

    from clawrouter_hermes import _patch_telegram_model_labels

    adapter_cls = _make_adapter_class(with_keyboard=True)
    telegram = _install_fake_hermes_plugins_adapter(monkeypatch, adapter_cls)
    telegram.InlineKeyboardButton = typing.Any
    telegram.InlineKeyboardMarkup = typing.Any

    assert _patch_telegram_model_labels() is True
    models = ["blockrun/free", "blockrun/openai/gpt-5.5"]
    markup, page_info = adapter_cls._build_model_keyboard(adapter_cls(), models, 0)
    # Pass-through: original labels, original markup type, no exception.
    assert [b.text for b in markup.inline_keyboard[0]] == models
    assert page_info == " (1–2)"


def test_sdk_installed_after_patch_enables_labels(monkeypatch):
    """The adapter rebinds the real classes on its module after the lazy SDK
    install; the wrapper resolves them at call time, so labels start working
    without a re-patch."""
    import typing

    from clawrouter_hermes import _patch_telegram_model_labels

    adapter_cls = _make_adapter_class(with_keyboard=True)
    telegram = _install_fake_hermes_plugins_adapter(monkeypatch, adapter_cls)
    telegram.InlineKeyboardButton = typing.Any
    telegram.InlineKeyboardMarkup = typing.Any
    assert _patch_telegram_model_labels() is True

    telegram.InlineKeyboardButton = _FakeButton
    telegram.InlineKeyboardMarkup = _FakeMarkup
    models = ["blockrun/free", "blockrun/openai/gpt-5.5"]
    markup, _page_info = adapter_cls._build_model_keyboard(adapter_cls(), models, 0)
    assert markup.inline_keyboard[0][0].text == "[FREE] free"


def test_deferred_hook_patches_late_loading_adapter(monkeypatch):
    """The pre_llm_call retry hook picks up an adapter that loads after the
    register-time attempt, then becomes a no-op."""
    import clawrouter_hermes as pkg

    monkeypatch.setattr(pkg, "_labels_patch_applied", False)
    pkg._apply_telegram_label_patch_once()  # nothing loaded yet
    assert pkg._labels_patch_applied is False

    adapter_cls = _make_adapter_class(with_keyboard=True)
    _install_fake_hermes_plugins_adapter(monkeypatch, adapter_cls)
    pkg._apply_telegram_label_patch_once()
    assert pkg._labels_patch_applied is True
    assert adapter_cls._clawrouter_labels_patched is True
