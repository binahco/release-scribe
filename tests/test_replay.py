from __future__ import annotations

from pathlib import Path

import pytest
from llm_client import CompletionRequest, LlmClient, ReplayProvider
from schema_validate import SchemaRegistry

from release_scribe.models import ReleaseNotes
from release_scribe.main import load_prompt, render_prompt

CASSETTES = Path(__file__).resolve().parents[1] / "cassettes"
COMMITS = """feat: add retry with backoff
fix: clamp per-call cost
feat: add replay provider without api key
docs: record span contract"""


def _has_tape() -> bool:
    return CASSETTES.is_dir() and list(CASSETTES.glob("complete-*.jsonl"))


@pytest.mark.skipif(not _has_tape(), reason="tape real no grabada (scripts/record_tape_opencode.py)")
def test_release_notes_replay_validates_and_populates_parsed() -> None:
    registry = SchemaRegistry()
    registry.register("release-notes-v1", ReleaseNotes)

    provider = ReplayProvider(CASSETTES, record=False)
    prompt_id, prompt_version, _ = load_prompt()
    client = LlmClient(
        provider,
        consumer_repo="release-scribe",
        model_aliases={"fast": "opencode/big-pickle"},
        renderer=render_prompt,
        validator=registry.make_validator("release-notes-v1"),
    )
    result = client.complete(
        CompletionRequest(
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            variables={"version": "0.1.0", "commits": COMMITS},
            model_alias="fast",
            response_schema="release-notes-v1",
            tags=["replay", "week-3"],
        )
    )

    assert result.provider == "replay"
    assert result.validation.ok is True
    assert isinstance(result.parsed, ReleaseNotes)
    assert result.parsed.version == "0.1.0"
    assert len(result.parsed.changes) >= 2