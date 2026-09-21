from pathlib import Path

from llm_client import CompletionRequest, LlmClient, ReplayProvider
from llm_client.providers.opencode_cli import OpenCodeCLI
from schema_validate import SchemaRegistry

from release_scribe.main import load_prompt, render_prompt
from release_scribe.models import ReleaseNotes

MODEL = "opencode/big-pickle"
CASSETTES = Path(__file__).resolve().parents[1] / "cassettes"

COMMITS = """feat: add retry with backoff
fix: clamp per-call cost
feat: add replay provider without api key
docs: record span contract"""


def main() -> None:
    registry = SchemaRegistry()
    registry.register("release-notes-v1", ReleaseNotes)
    recorder = ReplayProvider(CASSETTES, record=True, inner=OpenCodeCLI(MODEL))
    prompt_id, prompt_version, _ = load_prompt()
    client = LlmClient(
        recorder,
        consumer_repo="release-scribe",
        model_aliases={"fast": MODEL},
        retries=1,
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
            tags=["record", "seed-week3"],
        )
    )
    print(f"validated={result.validation.ok} parsed={result.parsed}")


if __name__ == "__main__":
    main()