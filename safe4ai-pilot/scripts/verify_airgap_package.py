"""Static verifier for the Safe4AI air-gap deployment package."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

REQUIRED_OLLAMA_MODELS = ("qwen3.5:9b", "nomic-embed-text")
REQUIRED_RUNBOOK_MARKERS = (
    "docker save",
    "docker load",
    "docker compose -f docker-compose.yml -f docker-compose.ollama.yml",
    "verify_airgap_package.py",
    "AUDIT_ARCHIVE_DIR",
    "no outbound",
)


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def verify_airgap_package(root: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    app_dockerfile = _read(root_path, "app/Dockerfile")
    compose = yaml.safe_load(_read(root_path, "docker-compose.yml"))
    ollama_compose = yaml.safe_load(_read(root_path, "docker-compose.ollama.yml"))
    runbook_path = root_path / "docs" / "air-gap-runbook.md"
    runbook = runbook_path.read_text(encoding="utf-8") if runbook_path.exists() else ""

    app_volumes = compose["services"]["app"].get("volumes", [])
    ollama_init = ollama_compose["services"].get("ollama-init", {})
    ollama_command = str(ollama_init.get("command", ""))

    checks = {
        "app_reranker_prebaked": "CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')" in app_dockerfile,
        "ollama_overlay_pulls_required_models": all(
            model in ollama_command for model in REQUIRED_OLLAMA_MODELS
        ),
        "default_compose_excludes_ollama": "ollama" not in compose["services"],
        "audit_archive_volume": any("data/audit-archive" in str(volume) for volume in app_volumes),
        "runbook_present": runbook_path.exists()
        and all(marker.lower() in runbook.lower() for marker in REQUIRED_RUNBOOK_MARKERS),
    }
    return {"ok": all(checks.values()), "checks": checks}


def main() -> int:
    report = verify_airgap_package(Path(__file__).resolve().parents[1])
    print(json.dumps(report, sort_keys=True, indent=2))  # noqa: T201
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
