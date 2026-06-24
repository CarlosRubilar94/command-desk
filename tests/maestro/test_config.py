"""Tests for env/config loading."""

from __future__ import annotations

from maestro.config import MaestroConfig
from maestro.env import get_bool, get_int, get_str, parse_dotenv


def test_parse_dotenv_basic():
    text = '# comment\nexport A=1\nB="two words"\nC=\'q\'\nbad line\nD=4\n'
    env = parse_dotenv(text)
    assert env == {"A": "1", "B": "two words", "C": "q", "D": "4"}


def test_env_getters():
    env = {"X": "true", "Y": "12", "Z": "  hi  "}
    assert get_bool(env, "X") is True
    assert get_bool(env, "missing", True) is True
    assert get_int(env, "Y", 0) == 12
    assert get_int(env, "missing", 5) == 5
    assert get_str(env, "Z") == "hi"


def test_hostinger_empresa_account_loaded():
    env = {
        "HERMES_HOME": "/tmp/h",
        "MAESTRO_HOSTINGER_EMPRESA_USER": "user@empresa.com",
        "MAESTRO_HOSTINGER_EMPRESA_APP_PASSWORD": "secret",
    }
    cfg = MaestroConfig.from_env(env)
    assert len(cfg.imap_accounts) == 1
    acct = cfg.imap_accounts[0]
    assert acct.account == "hostinger_empresa"
    assert acct.host == "imap.hostinger.com"
    assert acct.port == 993
    assert acct.is_complete is True
    assert "hostinger_empresa" in cfg.account_labels()


def test_titan_provider_selects_titan_host():
    env = {
        "MAESTRO_HOSTINGER_EMPRESA_USER": "u",
        "MAESTRO_HOSTINGER_EMPRESA_APP_PASSWORD": "p",
        "MAESTRO_HOSTINGER_EMPRESA_PROVIDER": "titan",
    }
    cfg = MaestroConfig.from_env(env)
    assert cfg.imap_accounts[0].host == "imap.titan.email"


def test_incomplete_imap_account_is_skipped():
    env = {"MAESTRO_HOSTINGER_EMPRESA_USER": "only-user"}
    cfg = MaestroConfig.from_env(env)
    # Present but incomplete → still listed so print-config can flag it,
    # but not counted as ready.
    assert all(not a.is_complete for a in cfg.imap_accounts)


def test_whatsapp_target_falls_back_to_home_channel():
    env = {"WHATSAPP_HOME_CHANNEL": "5511999990000"}
    cfg = MaestroConfig.from_env(env)
    assert cfg.whatsapp_target == "5511999990000"


def test_gemini_key_from_either_var_and_claude_args_split():
    cfg = MaestroConfig.from_env({"GOOGLE_API_KEY": "gk", "MAESTRO_CLAUDE_ARGS": "-p --output-format text"})
    assert cfg.gemini_api_key == "gk"
    assert cfg.claude_args == ["-p", "--output-format", "text"]


def test_phase2_disabled_by_default():
    cfg = MaestroConfig.from_env({})
    assert cfg.phase2_actions_enabled is False
