# 🤖 sdlc-multiagent

> Orchestrate a full software development lifecycle across 9 parallel Claude agents — from PRD to production-ready code — in a single command.

---

## What It Does

`sdlc-multiagent` is a Claude skill that reads a `feature.json` config containing a **Product Requirements Document (PRD)** and a **tech stack**, then fans out the entire SDLC across specialized AI agents running in parallel across three sequential waves.

```
Wave 1 — Design        (parallel)
  ├── Architecture      → system design, component diagrams, ADRs
  ├── API Contracts     → full API 3.1 spec
  └── DB Schema         → Prisma/SQL schema + migrations

Wave 2 — Implement     (parallel, receives Wave 1 outputs)
  ├── Backend           → Express/Node API implementation
  ├── Frontend          → React UI implementation
  └── DevOps            → Dockerfile, CI/CD pipelines

Wave 3 — Verify        (parallel, receives Wave 1+2 outputs)
  ├── Unit Tests        → >85% branch coverage target
  ├── Integration Tests → E2E + API + DB tests
  └── Docs              → README, API docs, changelog
```

Each wave's outputs are automatically injected as context into the next wave — so implementation agents see the architecture and API contracts, and test agents see the actual code.

---

## Prerequisites

- [Claude Code](https://claude.ai/code) installed and authenticated
- Python 3.9+
- `claude` CLI available on your `PATH`

---

## Installation

1. Download `sdlc-multiagent.skill`
2. Install it into your Claude skills directory:

```bash
unzip sdlc-multiagent.skill -d ~/.claude/skills/sdlc-multiagent
```

---

## Quick Start

### 1. Create your `feature.json`

```json
{
  "version": "2",
  "feature": {
    "name": "Todo App",
    "prd_file": "./docs/prd.md",
    "repo_root": ".",
    "tech_stack": {
      "frontend": "React + TypeScript",
      "backend": "Node.js + Express",
      "database": "PostgreSQL",
      "testing": "Jest",
      "infra": "Docker"
    },
    "output_dir": "./.sdlc-output"
  },
  "sdlc": {
    "model": "claude-sonnet-4-20250514",
    "timeout_seconds": 600,
    "agents": {
      "architecture":      { "wave": 1 },
      "api-contracts":     { "wave": 1 },
      "db-schema":         { "wave": 1 },
      "backend":           { "wave": 2 },
      "frontend":          { "wave": 2 },
      "devops":            { "wave": 2 },
      "unit-tests":        { "wave": 3 },
      "integration-tests": { "wave": 3 },
      "docs":              { "wave": 3 }
    }
  }
}
```

### 2. Write your PRD

Point `prd_file` at a Markdown file with your requirements — user stories, data model, API surface, acceptance criteria. The richer the PRD, the better the output.

Alternatively, use an inline `prd` string for short specs:

```json
"prd": "Users can create, edit, delete todos with tags and due dates."
```

> If both `prd` and `prd_file` are provided, the file contents are appended after the inline string.

### 3. Run the orchestrator

```bash
python run_sdlc.py feature.json
```

---

## Output Structure

Everything lands in `.sdlc-output/` (configurable via `output_dir`):

```
.sdlc-output/
├── architecture/         → ARCHITECTURE.md, TECH_DECISIONS.md
├── api-contracts/        → api.yaml, API_SUMMARY.md
├── db-schema/            → schema.prisma, migrations/001_init.sql
├── backend/              → BACKEND_NOTES.md  (+ code → repo root)
├── frontend/             → FRONTEND_NOTES.md (+ code → repo root)
├── devops/               → INFRA_NOTES.md    (+ Dockerfile, CI workflows)
├── unit-tests/           → TEST_COVERAGE.md  (+ test files co-located)
├── integration-tests/    → E2E_NOTES.md      (+ tests/integration/)
└── docs/                 → README_FEATURE.md, API_DOCS.md, CHANGELOG_ENTRY.md
```

---

## CLI Reference

```bash
# Run the full SDLC
python run_sdlc.py feature.json

# Re-run only a specific agent (e.g. after a failure)
python run_sdlc.py feature.json --only devops

# Re-run an entire wave
python run_sdlc.py feature.json --wave 2

# Run multiple specific agents
python run_sdlc.py feature.json --only backend unit-tests

# Preview all prompts without executing
python run_sdlc.py feature.json --dry-run
```

---

## Sample Run Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SDLC RUN: Todo App  (3 waves, 9 agents)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  WAVE 1 — Design
  ✅ architecture         12.3s  → .sdlc-output/architecture/
  ✅ api-contracts         9.1s  → .sdlc-output/api-contracts/
  ✅ db-schema            11.7s  → .sdlc-output/db-schema/

  WAVE 2 — Implement
  ✅ backend              58.2s  → .sdlc-output/backend/
  ✅ frontend             61.4s  → .sdlc-output/frontend/
  ✅ devops               22.0s  → .sdlc-output/devops/

  WAVE 3 — Verify
  ✅ unit-tests           34.9s  → .sdlc-output/unit-tests/
  ✅ integration-tests    40.1s  → .sdlc-output/integration-tests/
  ✅ docs                 18.3s  → .sdlc-output/docs/

  9 passed · 0 failed · total time: 138.5s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Configuration Reference

### `feature` object

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | ✅ | Human-readable feature name |
| `prd` | string | one of | Inline PRD text |
| `prd_file` | string | one of | Path to a Markdown PRD file |
| `repo_root` | string | | Repo root path. Default: `.` |
| `output_dir` | string | | Agent output directory. Default: `./.sdlc-output` |
| `tech_stack` | object | ✅ | Key/value map of stack choices |

### `sdlc` object

| Field | Type | Default | Description |
|---|---|---|---|
| `model` | string | `claude-sonnet-4-20250514` | Claude model for all agents |
| `max_tokens` | integer | `8192` | Max tokens per agent response |
| `timeout_seconds` | integer | `600` | Per-agent timeout |
| `agents` | object | ✅ | Map of agent ID → config |

### Per-agent options

| Field | Type | Description |
|---|---|---|
| `wave` | 1 \| 2 \| 3 | ✅ Execution wave |
| `enabled` | boolean | Set `false` to skip. Default: `true` |
| `model` | string | Override model for this agent |
| `timeout_seconds` | integer | Override timeout for this agent |
| `prompt_override` | string | Replace the default role prompt (PRD context still prepended) |

---

## Customising Agent Prompts

To override the default prompt for any agent, add `prompt_override` in `feature.json`:

```json
"agents": {
  "backend": {
    "wave": 2,
    "prompt_override": "Focus only on the payment module. Ignore auth endpoints."
  }
}
```

The shared PRD + tech stack context block is always prepended — `prompt_override` only replaces the role-specific instructions.

---

## Error Handling

| Situation | Behaviour |
|---|---|
| No `prd` or `prd_file` | Aborts — prompts user to provide one |
| `prd_file` path not found | Aborts with a clear path error |
| Wave 1 agent fails | Warns but continues; Wave 2 gets partial context |
| All agents in a wave fail | Aborts remaining waves, reports everything |
| `claude` CLI not on PATH | Aborts with install instructions |
| `enabled: false` agent | Skipped silently, noted in summary |

---

## License

MIT
