from __future__ import annotations

import argparse
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import yaml
from llm_client import CompletionRequest, LlmClient, ReplayProvider, Span
from llm_client.providers.opencode_cli import OpenCodeCLI
from schema_validate import SchemaRegistry

from .models import ReleaseNotes

DEFAULT_MODEL = "opencode/big-pickle"
SCHEMA_ID = "release-notes-v1"
ROOT = Path(__file__).resolve().parents[2]
PROMPT_FILE = ROOT / "prompts" / "release-notes-generator.md"


def load_prompt() -> tuple[str, str, str]:
    text = PROMPT_FILE.read_text()
    if not text.startswith("---"):
        raise SystemExit(f"{PROMPT_FILE}: falta frontmatter")
    _, frontmatter, body = text.split("---", 2)
    data = yaml.safe_load(frontmatter)
    return data["id"], data["version"], body.strip()


def render_prompt(prompt_id: str, prompt_version: str, variables: dict) -> list[dict]:
    _, _, body = load_prompt()
    system_part = body.split("## Sistema\n", 1)[1].split("## Usuario\n", 1)[0].strip()
    user_part = body.split("## Usuario\n", 1)[1].strip().format(version=variables["version"], commits=variables["commits"])
    return [
        {"role": "system", "content": system_part},
        {"role": "user", "content": user_part},
    ]


def git_log(root: Path, from_ref: str, to_ref: str) -> str:
    cmd = ["git", "-C", str(root), "log", "--format=%s", "--reverse", f"{from_ref}..{to_ref}"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.exit(1)
    return proc.stdout.strip()


def build_emitter(span_file: Path | None):
    def emit(span: Span, _result) -> None:
        if span_file is not None:
            with span_file.open("a") as handle:
                handle.write(span.as_jsonl() + "\n")
        else:
            sys.stderr.write(span.as_jsonl() + "\n")

    return emit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="release-scribe", description="Release notes JSON validadas")
    parser.add_argument("--from-ref", required=True, help="ref inicial del rango git (excluida)")
    parser.add_argument("--to-ref", default="HEAD", help="ref final del rango git (incluida)")
    parser.add_argument("--version", default="next", help="versión a anotar en la release note")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"modelo opencode (default: {DEFAULT_MODEL})")
    parser.add_argument("--replay", metavar="DIR", default=None, help="reproducir cassettes en vez de llamar al LLM")
    parser.add_argument("--span-file", metavar="PATH", default=None, help="escribir spans a un archivo JSONL")
    parser.add_argument("--cost-cap", metavar="USD", type=Decimal, default=None, help="costo semanal por llamada")
    parser.add_argument("--out", metavar="PATH", default=None, help="escribir la release note JSON a un archivo")
    parser.add_argument("--repo", default=None, help="raíz del repo a inspeccionar (default: cwd)")
    args = parser.parse_args(argv)

    root = Path(args.repo).resolve() if args.repo else Path.cwd()
    commits = git_log(root, args.from_ref, args.to_ref)
    if not commits:
        sys.stderr.write("release-scribe: no hay commits en el rango\n")
        return 1

    if args.replay:
        provider = ReplayProvider(args.replay, record=False)
    else:
        provider = OpenCodeCLI(args.model, cwd=str(root))

    registry = SchemaRegistry()
    registry.register(SCHEMA_ID, ReleaseNotes)

    prompt_id, prompt_version, _ = load_prompt()
    client = LlmClient(
        provider,
        consumer_repo="release-scribe",
        model_aliases={"fast": args.model},
        emitter=build_emitter(Path(args.span_file) if args.span_file else None),
        cost_cap_usd=args.cost_cap,
        renderer=render_prompt,
        validator=registry.make_validator(SCHEMA_ID),
    )
    result = client.complete(
        CompletionRequest(
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            variables={"version": args.version, "commits": commits},
            model_alias="fast",
            response_schema=SCHEMA_ID,
            tags=["release-scribe", "week-3"],
        )
    )

    if not result.validation.ok:
        sys.stderr.write(f"release-scribe: respuesta no válida ({', '.join(result.validation.errors)})\n")
        return 2

    notes = result.parsed
    payload = json.dumps(notes.model_dump(), indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(payload + "\n")
        sys.stderr.write(f"release-scribe: escritas {len(notes.changes)} cambios en {args.out}\n")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())