from pathlib import Path

from lectern.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def test_the_example_env_file_loads_once_keys_are_added(tmp_path):
    """The README says: copy .env.example to .env and add keys. That must start cleanly."""
    env = tmp_path / ".env"
    env.write_text((ROOT / ".env.example").read_text().replace("GEMINI_API_KEY=", "GEMINI_API_KEY=abc", 1))
    settings = Settings(_env_file=env)
    assert settings.llm_provider is None and settings.access_token is None
    assert settings.resolve_writer() == ("gemini", "gemini-flash-latest")
    assert settings.public_status()["access_protected"] is False


def test_blank_example_env_has_no_model():
    settings = Settings(_env_file=ROOT / ".env.example")
    assert settings.resolve_writer() is None
