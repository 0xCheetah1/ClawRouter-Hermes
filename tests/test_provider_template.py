"""provider_template/ — files must be present and shaped correctly."""

from __future__ import annotations

import ast
import importlib.resources as resources
import sys
import types


def _template_dir():
    return resources.files("clawrouter_hermes").joinpath("provider_template")


def _template_static_fallbacks() -> tuple[str, ...]:
    """Extract the _STATIC_FALLBACKS tuple from the (un-importable) template."""
    source = _template_dir().joinpath("init.py.tmpl").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_STATIC_FALLBACKS"
            for t in node.targets
        ):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("_STATIC_FALLBACKS not found in init.py.tmpl")


def test_template_files_present():
    files = {p.name for p in _template_dir().iterdir()}
    assert "plugin.yaml" in files
    assert "init.py.tmpl" in files


def test_provider_plugin_yaml_declares_model_provider():
    text = _template_dir().joinpath("plugin.yaml").read_text(encoding="utf-8")
    assert "kind: model-provider" in text
    assert "clawrouter" in text


def test_provider_init_template_calls_register_provider():
    text = _template_dir().joinpath("init.py.tmpl").read_text(encoding="utf-8")
    assert "register_provider" in text
    assert "ClawRouterProfile" in text
    assert "base_url" in text
    assert "CLAWROUTER_API_KEY" in text


def test_provider_template_uses_curated_picker_catalog_only():
    text = _template_dir().joinpath("init.py.tmpl").read_text(encoding="utf-8")
    assert "models_url" not in text


def test_template_fallbacks_match_chat_models():
    """The materialized provider's fallback_models must stay in sync with the
    curated picker catalog in models.py. The template is copied verbatim (no
    substitution), so the two lists are hand-maintained duplicates and drift
    silently if only one is edited."""
    from clawrouter_hermes import models

    assert _template_static_fallbacks() == tuple(models.chat_models())


def test_curated_picker_catalog_contains_free_models():
    from clawrouter_hermes import models

    chat_models = models.chat_models()
    free_models = [model for model in chat_models if models.is_free_model(model)]
    assert "blockrun/free" in free_models
    assert any(model.startswith("blockrun/free/") for model in free_models)


def test_curated_picker_catalog_orders_featured_models():
    from clawrouter_hermes import models

    chat_models = models.chat_models()
    positions = {model: idx for idx, model in enumerate(chat_models)}
    assert chat_models[:4] == [
        "blockrun/auto",
        "blockrun/premium",
        "blockrun/eco",
        "blockrun/free",
    ]
    featured_order = [
        "blockrun/anthropic/claude-fable-5",
        "blockrun/anthropic/claude-opus-4.8",
        "blockrun/anthropic/claude-sonnet-5",
        "blockrun/anthropic/claude-sonnet-4.6",
        "blockrun/openai/gpt-5.6-terra",
        "blockrun/openai/gpt-5.6-sol",
        "blockrun/openai/gpt-5.6-luna",
        "blockrun/openai/gpt-5.5",
        "blockrun/google/gemini-3.1-pro",
        "blockrun/xai/grok-4.5",
        "blockrun/xai/grok-4.3",
        "blockrun/zai/glm-5.2",
        "blockrun/minimax/minimax-m3",
        "blockrun/moonshot/kimi-k3",
        "blockrun/qwen/qwen3.7-max",
        "blockrun/deepseek/deepseek-v4-pro",
        "blockrun/free/mistral-large-3-675b",
    ]
    assert [positions[model] for model in featured_order] == sorted(
        positions[model] for model in featured_order
    )
    # All per-model free entries sit contiguously at the end of the picker,
    # and match the live free tier exactly (order mirrors top-models.json,
    # with post-top-models catalog additions appended).
    free_tail = [m for m in chat_models if m.startswith("blockrun/free/")]
    assert chat_models[-len(free_tail):] == free_tail
    assert free_tail == [
        "blockrun/free/mistral-large-3-675b",
        "blockrun/free/qwen3-next-80b-a3b-instruct",
        "blockrun/free/seed-oss-36b",
        "blockrun/free/nemotron-3-nano-omni-30b-a3b-reasoning",
        "blockrun/free/mistral-nemotron",
        "blockrun/free/step-3.7-flash",
        "blockrun/free/nemotron-nano-9b-v2",
        "blockrun/free/nemotron-nano-12b-v2-vl",
    ]
    # Retired models must not reappear in the picker. Append here on every
    # catalog retirement so a bad merge can't resurrect them.
    retired_models = frozenset({
        "blockrun/free/qwen3-coder-480b",  # NVIDIA EOL 2026-06-14
        # Dropped from the live BlockRun catalog by 2026-07-17:
        "blockrun/xai/grok-4-1-fast-reasoning",
        "blockrun/xai/grok-4-0709",
        "blockrun/xai/grok-3",
        "blockrun/free/gpt-oss-120b",
        "blockrun/free/gpt-oss-20b",
        "blockrun/free/qwen3.5-122b-a10b",
        "blockrun/free/llama-4-maverick",
    })
    assert not set(chat_models) & retired_models


def test_patch_hermes_model_catalog_uses_curated_clawrouter_only(monkeypatch):
    import clawrouter_hermes.cli as cli_module
    from clawrouter_hermes import models

    clear_calls = []
    hermes_models = types.ModuleType("hermes_cli.models")
    hermes_models._PROVIDER_MODELS = {}

    def provider_model_ids(provider, *_, **__):
        return ["auto", "eco", "openai/gpt-5.6-sol"] if provider == "clawrouter" else ["other"]

    def cached_provider_model_ids(provider, *_, **__):
        return ["auto", "eco", "openai/gpt-5.6-sol"] if provider == "clawrouter" else ["cached-other"]

    def clear_provider_models_cache(provider=None):
        clear_calls.append(provider)

    hermes_models.provider_model_ids = provider_model_ids
    hermes_models.cached_provider_model_ids = cached_provider_model_ids
    hermes_models.clear_provider_models_cache = clear_provider_models_cache

    hermes_cli = types.ModuleType("hermes_cli")
    hermes_cli.models = hermes_models
    monkeypatch.setitem(sys.modules, "hermes_cli", hermes_cli)
    monkeypatch.setitem(sys.modules, "hermes_cli.models", hermes_models)

    cli_module.patch_hermes_model_catalog()

    assert hermes_models._PROVIDER_MODELS["clawrouter"] == models.chat_models()
    assert hermes_models.provider_model_ids("clawrouter") == models.chat_models()
    assert hermes_models.cached_provider_model_ids("blockrun") == models.chat_models()
    assert hermes_models.provider_model_ids("openai") == ["other"]
    assert hermes_models.cached_provider_model_ids("openai") == ["cached-other"]
    assert clear_calls == ["clawrouter"]


def test_materialize_writes_correct_filenames(tmp_path, monkeypatch):
    """Materializer drops files at $HERMES_HOME/plugins/model-providers/clawrouter/."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    import importlib
    import clawrouter_hermes.cli as cli_module
    importlib.reload(cli_module)

    target = tmp_path / ".hermes" / "plugins" / "model-providers" / "clawrouter"
    cli_module._materialize_provider_plugin(force=False)

    assert (target / "plugin.yaml").is_file()
    assert (target / "__init__.py").is_file()
    assert "register_provider" in (target / "__init__.py").read_text()
    assert "kind: model-provider" in (target / "plugin.yaml").read_text()


def test_install_hermes_compat_writes_provider_env_and_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    import importlib
    import yaml
    import clawrouter_hermes.cli as cli_module
    importlib.reload(cli_module)

    cli_module.install_hermes_compat(force_provider=True, set_default=True)

    hermes_home = tmp_path / ".hermes"
    assert (hermes_home / "plugins" / "model-providers" / "clawrouter" / "__init__.py").is_file()
    assert "CLAWROUTER_API_KEY=clawrouter-local" in (hermes_home / ".env").read_text()

    config = yaml.safe_load((hermes_home / "config.yaml").read_text())
    assert config["model"]["provider"] == "clawrouter"
    assert config["model"]["default"] == "blockrun/auto"
    assert config["providers"]["clawrouter"]["key_env"] == "CLAWROUTER_API_KEY"
    assert config["providers"]["clawrouter"]["discover_models"] is False
    assert "blockrun/auto" in config["providers"]["clawrouter"]["models"]



def test_setup_preserves_existing_default_model_without_force(tmp_path, monkeypatch):
    """Without set_default=True, an existing model.default must not be clobbered."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    import importlib
    import yaml
    import clawrouter_hermes.cli as cli_module
    importlib.reload(cli_module)

    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    (hermes_home / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "model": {"default": "anthropic/claude-opus-4.7", "provider": "anthropic"},
                "unrelated": {"key": "value"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    cli_module.install_hermes_compat(force_provider=True, set_default=False)

    config = yaml.safe_load((hermes_home / "config.yaml").read_text())
    assert config["model"]["default"] == "anthropic/claude-opus-4.7"
    assert config["model"]["provider"] == "anthropic"
    assert "base_url" not in config["model"]
    assert config["unrelated"] == {"key": "value"}
    assert config["providers"]["clawrouter"]["key_env"] == "CLAWROUTER_API_KEY"


def test_install_hermes_compat_is_idempotent(tmp_path, monkeypatch):
    """Running setup twice produces no diff on the second run."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    import importlib
    import clawrouter_hermes.cli as cli_module
    importlib.reload(cli_module)

    cli_module.install_hermes_compat(force_provider=True, set_default=True)
    hermes_home = tmp_path / ".hermes"
    first_config = (hermes_home / "config.yaml").read_text()
    first_env = (hermes_home / ".env").read_text()

    cli_module.install_hermes_compat(force_provider=False, set_default=True)
    second_config = (hermes_home / "config.yaml").read_text()
    second_env = (hermes_home / ".env").read_text()

    assert first_config == second_config
    assert first_env == second_env


def test_hermes_home_env_var_respected(tmp_path, monkeypatch):
    """When HERMES_HOME is set, materializer writes there (not ~/.hermes)."""
    custom = tmp_path / "custom_hermes_root"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_HOME", str(custom))
    import importlib
    import clawrouter_hermes.cli as cli_module
    importlib.reload(cli_module)

    cli_module._materialize_provider_plugin(force=False)

    target = custom / "plugins" / "model-providers" / "clawrouter"
    assert (target / "plugin.yaml").is_file()
    assert (target / "__init__.py").is_file()
    # Default ~/.hermes location must NOT have been touched.
    legacy = tmp_path / ".hermes" / "plugins" / "model-providers" / "clawrouter"
    assert not legacy.exists()
