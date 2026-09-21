# release-scribe

> **Semana:** 3 · **Core:** `llm-dev-core` 0.3.0

## Problema

Escribir release notes es una de esas tareas que nadie quiere hacer dos veces: hay que
repasar el historial, clasificar tipo/alcance, detectar breaking changes y escribir
resúmenes para humanos. Este CLI toma un rango de commits (`from..to`) y **genera la
release note como JSON validado** contra un esquema Pydantic (`schema-validate`), con
reparación automática si el modelo responde JSON inválido.

## Demo

```bash
cd tu-repo
release-scribe --from-ref v1.0.0 --to-ref v1.1.0 --version 1.1.0 --out RELEASE.json
```

La salida es JSON validado de la forma:

```json
{
  "version": "1.1.0",
  "title": "…",
  "changes": [
    {"type": "feat", "scope": null, "description": "…", "breaking": false}
  ]
}
```

## Arquitectura

```
┌─────────────────────┐  git log    ┌────────────────────────────────┐
│ tu repo (cwd)       │ ──────────▶ │ release-scribe (este proyecto)  │
└─────────────────────┘             │  · render del prompt            │
                                    │  · SchemaRegistry               │
                                    │  · LlmClient + schema-validate  │
                                    │  · span JSONL → stderr          │
                                    └──────────────┬──────────────────┘
                                                   │ provider
                                                   ▼
                                   ┌──────────────────────────────────┐
                                   │ opencode run (tu sesión, free)   │
                                   │   · o ReplayProvider (cassettes) │
                                   └──────────────────────────────────┘
```

La novedad frente a la semana 2: la salida del LLM **no se imprime cruda** — pasa por
`schema-validate`; si no valida, `llm-client` re-pregunta con los errores (hasta 2
intentos) y el span lo registra (`repaired_attempts`).

## Recicla de

| Módulo del core | Qué aporta |
|---|---|
| `llm-client` | Llamadas LLM con retry+backoff, span de 20 campos, costo, record/replay sin API key y el **lazo de reparación** (presupuesto 2 + cap) |
| `schema-validate` | La salida del LLM es input no confiable: valida contra el esquema, extrae `parsed` y alimenta la reparación (`release-notes-v1`) |

## Limitaciones

- El título lo propone el modelo; la versión de la release note la pasas tú (`--version`).
- Clasificar `type` depende de que los commits sigan Conventional Commits: si no, el modelo adivina.
- Los commits salen del repo tal cual: si el historial tiene secretos, tú decides qué compartir.
- `opencode run` spawnea un servidor por llamada: latencia de inicio (~segundos) incluida en el span.

## Roadmap

- [ ] Evaluación `eval-smoke` con el dataset de `evals/` (sem. 5, test-kit)
- [ ] `--out` en Markdown además de JSON (composición con `docs-gen`, sem. 12)
- [ ] Detectar breaking changes desde `BREAKING CHANGE` en el pie del commit, no solo del tipo
- [ ] Retrofit al core si la extracción de commits-previos pidiera soporte en `git_diff` (ver `retrofit-issue.md`)