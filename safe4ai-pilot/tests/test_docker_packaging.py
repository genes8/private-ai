from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_app_dockerfile_copies_all_runtime_packages() -> None:
    dockerfile = (ROOT / "app" / "Dockerfile").read_text()

    assert "COPY app/ ./app/" in dockerfile
    assert "COPY observability/ ./observability/" in dockerfile
    assert "COPY scripts/ ./scripts/" in dockerfile


def test_compose_override_mounts_runtime_packages_for_reload() -> None:
    override = (ROOT / "docker-compose.override.yml").read_text()

    assert "./app:/app/app" in override
    assert "./observability:/app/observability" in override
    assert "./scripts:/app/scripts" in override


def test_default_compose_does_not_require_ollama() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    services = compose["services"]

    assert "ollama" not in services
    assert "ollama-init" not in services
    assert "ollama" not in services["app"].get("depends_on", {})


def test_ollama_override_contains_local_llm_services() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.ollama.yml").read_text())
    services = compose["services"]

    assert "ollama" in services
    assert "ollama-init" in services


def test_airgap_package_verifier_passes() -> None:
    from scripts.verify_airgap_package import verify_airgap_package

    report = verify_airgap_package(ROOT)

    assert report["ok"] is True
    assert report["checks"]["app_reranker_prebaked"] is True
    assert report["checks"]["ollama_overlay_pulls_required_models"] is True
    assert report["checks"]["runbook_present"] is True
    assert report["checks"]["audit_archive_volume"] is True


def test_release_workflow_attaches_license_reports_and_blocks_high_vulnerabilities() -> None:
    workflow = yaml.safe_load((ROOT.parent / ".github" / "workflows" / "release.yml").read_text())
    image_steps = workflow["jobs"]["images"]["steps"]

    trivy_steps = [
        step for step in image_steps if step.get("uses") == "aquasecurity/trivy-action@master"
    ]
    assert trivy_steps
    assert all(step["with"]["severity"] == "CRITICAL,HIGH" for step in trivy_steps)
    assert all(step["with"]["exit-code"] == "1" for step in trivy_steps)

    release_step = next(
        step for step in image_steps if step.get("uses") == "softprops/action-gh-release@v2"
    )
    release_files = release_step["with"]["files"]
    assert "release-evidence/license-reports/license-report-backend.md" in release_files
    assert "release-evidence/license-reports/license-report-frontend.md" in release_files
