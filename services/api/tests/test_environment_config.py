import os

import pytest

from app.environment import load_api_env


@pytest.fixture(autouse=True)
def restore_ai_env():
    keys = ["OPENAI_API_KEY", "OPENAI_BASE_URL", "REELSTRUCT_VISION_MODEL", "REELSTRUCT_STRUCTURE_MODEL"]
    original = {key: os.environ.get(key) for key in keys}
    yield
    for key, value in original.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_load_api_env_reads_dotenv_values(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "# local AI provider",
                "OPENAI_API_KEY=relay-key",
                'OPENAI_BASE_URL="https://relay.example.com/v1"',
                "REELSTRUCT_VISION_MODEL='vision-model'",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("REELSTRUCT_VISION_MODEL", raising=False)

    load_api_env(env_path)

    assert os.environ["OPENAI_API_KEY"] == "relay-key"
    assert os.environ["OPENAI_BASE_URL"] == "https://relay.example.com/v1"
    assert os.environ["REELSTRUCT_VISION_MODEL"] == "vision-model"


def test_load_api_env_does_not_override_existing_environment(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=file-key\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "shell-key")

    load_api_env(env_path)

    assert os.environ["OPENAI_API_KEY"] == "shell-key"
