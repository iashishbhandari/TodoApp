#!/usr/bin/env python3
"""
SDLC Orchestrator
Reads feature.json and runs SDLC agents in 3 parallel waves:
  Wave 1 — Design (architecture, api-contracts, db-schema)
  Wave 2 — Implement (backend, frontend, devops)
  Wave 3 — Verify (unit-tests, integration-tests, docs)

Context grows across waves: each wave receives the PRD + all prior wave outputs.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ── Default role prompts ────────────────────────────────────────────────────────

ROLE_PROMPTS = {
    "architecture": """You are the Architecture Agent for the "{feature_name}" feature.
Produce a comprehensive architecture design document.
Deliverables in {output_dir}/:
1. ARCHITECTURE.md — component diagram, data flow, technical decisions, security boundaries
2. TECH_DECISIONS.md — ADRs for non-obvious choices
Ground every decision in the PRD. Be specific about file/folder structure.""",

    "api-contracts": """You are the API Contracts Agent for the "{feature_name}" feature.
Define every API endpoint before any code is written.
Deliverables in {output_dir}/:
1. openapi.yaml — full OpenAPI 3.1 spec (paths, auth, error shapes, examples)
2. API_SUMMARY.md — human-readable overview
Use REST unless the PRD implies otherwise. Every field needs a type and description.""",

    "db-schema": """You are the Database Schema Agent for the "{feature_name}" feature.
Design the full data model before implementation.
Deliverables in {output_dir}/:
1. schema.prisma (or schema.sql) — all tables, fields, PKs, FKs, indexes, enums, relations
2. migrations/001_init.sql — initial migration
3. SCHEMA_NOTES.md — design decisions, normalization choices
Only create tables grounded in the PRD.""",

    "backend": """You are the Backend Implementation Agent for the "{feature_name}" feature.
You have the architecture doc, API spec, and DB schema from the design phase above.
Deliverables — write production code to {repo_root}, stubs to {output_dir}/:
1. Implement all API endpoints from the OpenAPI spec
2. Integrate with the DB schema, run migrations if possible
3. Add input validation, error handling, auth middleware
4. Add JSDoc/TSDoc on all exported functions
5. BACKEND_NOTES.md — note any deviations from spec
Do not deviate from API contracts without documenting it.""",

    "frontend": """You are the Frontend Implementation Agent for the "{feature_name}" feature.
You have the architecture doc and API contracts from the design phase above.
Deliverables — write production code to {repo_root}:
1. Implement all UI screens/flows from the PRD
2. Wire up API calls using the OpenAPI contracts (mock if backend not ready)
3. Add loading, error, and empty states for every async op
4. Mobile-first responsive layout if PRD specifies it
5. FRONTEND_NOTES.md — component decisions, any mocked contracts""",

    "devops": """You are the DevOps/CI Agent for the "{feature_name}" feature.
Set up infrastructure and CI/CD for the feature.
Deliverables in {repo_root} (or {output_dir}/ if repo is read-only):
1. Dockerfile + docker-compose.yml (if multi-service)
2. .github/workflows/ci.yml — lint, test, build
3. .github/workflows/deploy.yml — staging + production gates
4. INFRA_NOTES.md — required env vars, secrets, deployment notes""",

    "unit-tests": """You are the Unit Test Agent for the "{feature_name}" feature.
You have all backend and frontend code from the implementation phase above.
Deliverables — co-locate tests with source or write to __tests__/:
1. Unit tests for all backend service/controller functions
2. Unit tests for all frontend components (render + interaction)
3. Target >85% branch coverage; mock all external deps
4. TEST_COVERAGE.md — what is and isn't covered, why""",

    "integration-tests": """You are the Integration Test Agent for the "{feature_name}" feature.
You have all code, API contracts, and DB schema.
Deliverables in tests/integration/ or e2e/:
1. API integration tests — all endpoints, valid and invalid inputs
2. E2E tests — critical user journeys from the PRD
3. DB integration tests — schema constraints and migrations
4. E2E_NOTES.md — scenarios covered, any gaps
Use transactions + rollback between tests.""",

    "docs": """You are the Documentation Agent for the "{feature_name}" feature.
You have all design docs, code, specs, and tests from all waves.
Deliverables in {output_dir}/:
1. README_FEATURE.md — setup, env vars, how to test, deploy
2. API_DOCS.md — human-readable API docs (from OpenAPI spec)
3. CHANGELOG_ENTRY.md — release notes entry
4. DECISIONS.md — consolidated log of all decisions made across waves
Keep language precise. Include code examples.""",
}

WAVE_NAMES = {1: "Design", 2: "Implement", 3: "Verify"}


# ── Config loading & validation ────────────────────────────────────────────────

def load_config(path: str) -> dict:
    p = Path(path).resolve()
    if not p.exists():
        sys.exit(f"❌ Config not found: {path}")
    text = p.read_text()
    cfg = yaml.safe_load(text) if (HAS_YAML and p.suffix in (".yaml", ".yml")) else json.loads(text)
    cfg["_config_dir"] = str(p.parent)
    return cfg


def validate(cfg: dict) -> None:
    assert cfg.get("version") == "2", "config.version must be '2'"
    feat = cfg.get("feature", {})
    assert feat.get("name"), "feature.name is required"
    assert feat.get("prd") or feat.get("prd_file"), "feature.prd or feature.prd_file is required"
    assert feat.get("tech_stack"), "feature.tech_stack is required"
    agents = cfg.get("sdlc", {}).get("agents", {})
    assert agents, "sdlc.agents must be non-empty"
    ids = list(agents.keys())
    for aid, acfg in agents.items():
        assert "wave" in acfg, f"Agent '{aid}' missing 'wave'"
        assert acfg["wave"] in (1, 2, 3), f"Agent '{aid}' wave must be 1, 2, or 3"


def load_prd(cfg: dict) -> str:
    feat = cfg["feature"]
    parts = []
    if feat.get("prd"):
        parts.append(feat["prd"].strip())
    if feat.get("prd_file"):
        prd_path = Path(cfg["_config_dir"]) / feat["prd_file"]
        if not prd_path.exists():
            sys.exit(f"❌ prd_file not found: {prd_path}")
        parts.append(prd_path.read_text().strip())
    return "\n\n".join(parts)


# ── Context building ───────────────────────────────────────────────────────────

def build_shared_context(prd: str, tech_stack: dict, output_dir: Path,
                          prior_wave_outputs: dict[int, dict[str, str]]) -> str:
    stack_lines = "\n".join(f"- {k}: {v}" for k, v in tech_stack.items())
    ctx = f"=== FEATURE PRD ===\n{prd}\n\n=== TECH STACK ===\n{stack_lines}\n"

    for wave_num in sorted(prior_wave_outputs.keys()):
        wave_data = prior_wave_outputs[wave_num]
        ctx += f"\n=== WAVE {wave_num} OUTPUTS ({WAVE_NAMES[wave_num]}) ===\n"
        for agent_id, content in wave_data.items():
            ctx += f"\n--- {agent_id} ---\n{content}\n"

    return ctx


def read_wave_outputs(agent_ids: list[str], output_dir: Path) -> dict[str, str]:
    outputs = {}
    for aid in agent_ids:
        agent_dir = output_dir / aid
        if not agent_dir.exists():
            continue
        files = list(agent_dir.rglob("*"))
        texts = []
        for f in sorted(files):
            if f.is_file() and f.suffix in (".md", ".yaml", ".yml", ".json", ".sql", ".prisma", ".txt"):
                try:
                    texts.append(f"[{f.name}]\n{f.read_text()}")
                except Exception:
                    pass
        if texts:
            outputs[aid] = "\n\n".join(texts)
    return outputs


# ── Agent execution ────────────────────────────────────────────────────────────

def build_prompt(agent_id: str, agent_cfg: dict, feature: dict,
                 shared_ctx: str, output_dir: Path, repo_root: Path) -> str:
    if agent_cfg.get("prompt_override"):
        role_prompt = agent_cfg["prompt_override"]
    elif agent_id in ROLE_PROMPTS:
        role_prompt = ROLE_PROMPTS[agent_id].format(
            feature_name=feature["name"],
            output_dir=str(output_dir / agent_id),
            repo_root=str(repo_root),
        )
    else:
        role_prompt = f"You are the {agent_id} agent for the '{feature['name']}' feature. Write your outputs to {output_dir / agent_id}/."

    return f"{shared_ctx}\n\n=== YOUR ROLE ===\n{role_prompt}"


def run_agent(agent_id: str, prompt: str, agent_cfg: dict, sdlc_cfg: dict,
              output_dir: Path, cwd: Path, dry_run: bool) -> dict:
    if dry_run:
        print(f"\n  [DRY RUN] {agent_id}")
        print(f"  Prompt preview: {prompt[:300]}…")
        return {"id": agent_id, "success": True, "dry_run": True, "elapsed_seconds": 0,
                "stdout": "", "stderr": ""}

    model = agent_cfg.get("model") or sdlc_cfg.get("model", "claude-sonnet-4-20250514")
    timeout = agent_cfg.get("timeout_seconds") or sdlc_cfg.get("timeout_seconds", 600)
    env = {**os.environ, **agent_cfg.get("env", {})}

    agent_out_dir = output_dir / agent_id
    agent_out_dir.mkdir(parents=True, exist_ok=True)

    start = time.time()
    print(f"    ▶  [{agent_id}] Starting…")
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", model],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = round(time.time() - start, 1)
        success = result.returncode == 0
        icon = "✅" if success else "❌"
        print(f"    {icon}  [{agent_id}] Done in {elapsed}s (exit {result.returncode})")
        print('stdout:', result.stdout[:500])
        print('stderr:', result.stderr[:500])
        return {"id": agent_id, "success": success, "exit_code": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr, "elapsed_seconds": elapsed}
    except subprocess.TimeoutExpired:
        elapsed = round(time.time() - start, 1)
        print(f"    ⏱  [{agent_id}] Timed out after {elapsed}s")
        return {"id": agent_id, "success": False, "exit_code": -1,
                "stdout": "", "stderr": f"Timed out after {timeout}s", "elapsed_seconds": elapsed}


# ── Summary ────────────────────────────────────────────────────────────────────

def print_summary(feature_name: str, all_results: list[dict], output_dir: Path,
                  total_elapsed: float) -> None:
    passed = sum(1 for r in all_results if r["success"])
    failed = sum(1 for r in all_results if not r["success"])
    width = 55
    print("\n" + "━" * width)
    print(f"  SDLC RUN: {feature_name}")
    print("━" * width)

    by_wave: dict[int, list] = {}
    for r in all_results:
        by_wave.setdefault(r["wave"], []).append(r)

    for wave_num in sorted(by_wave.keys()):
        print(f"\n  WAVE {wave_num} — {WAVE_NAMES[wave_num]}")
        for r in by_wave[wave_num]:
            icon = "✅" if r["success"] else "❌"
            agent_dir = output_dir / r["id"]
            location = f"→ {agent_dir}/" if agent_dir.exists() else ""
            elapsed = f"{r['elapsed_seconds']}s" if not r.get("dry_run") else "dry-run"
            print(f"  {icon} {r['id']:<22} {elapsed:<8}  {location}")
            if not r["success"] and r.get("stderr"):
                for line in r["stderr"].strip().splitlines()[:3]:
                    print(f"      {line}")

    print(f"\n  {passed} passed · {failed} failed · total: {round(total_elapsed, 1)}s")
    print("━" * width + "\n")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run full SDLC in parallel waves from a PRD config")
    parser.add_argument("config", help="Path to feature.json or feature.yaml")
    parser.add_argument("--only", nargs="+", metavar="ID", help="Run only specific agent IDs")
    parser.add_argument("--wave", type=int, choices=[1, 2, 3], help="Run only a specific wave")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without running")
    parser.add_argument("--json-output", metavar="FILE", help="Write JSON results to file")
    args = parser.parse_args()

    cfg = load_config(args.config)
    validate(cfg)
    feature = cfg["feature"]
    sdlc_cfg = cfg["sdlc"]
    agents_map = sdlc_cfg["agents"]

    prd = load_prd(cfg)
    repo_root = Path(cfg["_config_dir"]) / feature.get("repo_root", ".")
    output_dir = Path(cfg["_config_dir"]) / feature.get("output_dir", ".sdlc-output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Filter agents
    active_agents = {aid: acfg for aid, acfg in agents_map.items() if acfg.get("enabled", True)}
    if args.only:
        active_agents = {aid: acfg for aid, acfg in active_agents.items() if aid in args.only}
    if args.wave:
        active_agents = {aid: acfg for aid, acfg in active_agents.items() if acfg["wave"] == args.wave}

    if not active_agents:
        print("No agents to run.")
        sys.exit(0)

    print(f"\n🚀 SDLC: {feature['name']}")
    print(f"   {len(active_agents)} agent(s) across waves 1–3\n")

    all_results: list[dict] = []
    prior_wave_outputs: dict[int, dict[str, str]] = {}
    total_start = time.time()

    for wave_num in [1, 2, 3]:
        wave_agents = {aid: acfg for aid, acfg in active_agents.items() if acfg["wave"] == wave_num}
        if not wave_agents:
            continue

        print(f"── Wave {wave_num}: {WAVE_NAMES[wave_num]} ({len(wave_agents)} agent(s)) ──")

        shared_ctx = build_shared_context(prd, feature["tech_stack"], output_dir, prior_wave_outputs)

        def _run(item):
            aid, acfg = item
            prompt = build_prompt(aid, acfg, feature, shared_ctx, output_dir, repo_root)
            result = run_agent(aid, prompt, acfg, sdlc_cfg, output_dir,
                               Path(acfg.get("cwd", str(repo_root))), args.dry_run)
            result["wave"] = wave_num
            return result

        with ThreadPoolExecutor(max_workers=len(wave_agents)) as pool:
            futures = [pool.submit(_run, item) for item in wave_agents.items()]
            wave_results = [f.result() for f in as_completed(futures)]

        all_results.extend(wave_results)
        successful_ids = [r["id"] for r in wave_results if r["success"]]
        prior_wave_outputs[wave_num] = read_wave_outputs(successful_ids, output_dir)

        failed = [r for r in wave_results if not r["success"]]
        if failed and wave_num < 3:
            print(f"  ⚠️  {len(failed)} agent(s) failed in wave {wave_num}. Continuing with partial context.")

    total_elapsed = time.time() - total_start
    print_summary(feature["name"], all_results, output_dir, total_elapsed)

    if args.json_output:
        Path(args.json_output).write_text(json.dumps(all_results, indent=2))
        print(f"Results written to {args.json_output}")

    sys.exit(1 if any(not r["success"] for r in all_results) else 0)


if __name__ == "__main__":
    main()
