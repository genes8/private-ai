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


def test_vite_dev_proxy_covers_chat_namespace() -> None:
    vite_config = (ROOT / "frontend" / "vite.config.ts").read_text()

    assert '"/chat":' in vite_config


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


def test_phase_e_customer_security_pack_artifacts_exist() -> None:
    required_docs = [
        ROOT / "docs" / "helm-package-plan.md",
        ROOT / "docs" / "dokploy-deployment-guide.md",
        ROOT / "docs" / "prometheus-grafana-plan.md",
        ROOT / "docs" / "vllm-openai-compatible-preset.md",
        ROOT / "docs" / "security-pack" / "README.md",
        ROOT / "docs" / "security-pack" / "data-flow-diagram.md",
        ROOT / "docs" / "security-pack" / "threat-model.md",
        ROOT / "docs" / "security-pack" / "backup-restore-deletion-verification.md",
        ROOT / "docs" / "security-pack" / "controls-mapping.md",
        ROOT / "docs" / "security-pack" / "worm-storage-guide.md",
        ROOT / "docs" / "security-pack" / "image-signing-verification.md",
    ]

    for path in required_docs:
        assert path.exists(), f"Missing Phase E artifact: {path.relative_to(ROOT)}"


def test_release_workflow_signs_published_images() -> None:
    workflow = yaml.safe_load((ROOT.parent / ".github" / "workflows" / "release.yml").read_text())
    assert workflow["permissions"]["id-token"] == "write"

    image_steps = workflow["jobs"]["images"]["steps"]
    assert any(step.get("uses", "").startswith("sigstore/cosign-installer@") for step in image_steps)
    sign_step = next(step for step in image_steps if step.get("name") == "Sign published images")

    # Images must be signed by immutable digest, not the mutable tag.
    assert "cosign sign --yes" in sign_step["run"]
    assert "RepoDigests" in sign_step["run"]
    assert 'cosign sign --yes "$BACKEND_IMAGE:$VERSION"' not in sign_step["run"]
    assert 'cosign sign --yes "$FRONTEND_IMAGE:$VERSION"' not in sign_step["run"]


def test_release_workflow_sets_required_test_secret_key() -> None:
    workflow = yaml.safe_load((ROOT.parent / ".github" / "workflows" / "release.yml").read_text())

    assert len(workflow["env"]["SECRET_KEY"]) >= 16


def test_backend_dockerfile_pins_cpu_torch() -> None:
    dockerfile = (ROOT / "app" / "Dockerfile").read_text()

    assert "pip install --no-cache-dir --timeout 300 torch==2.11.0" in dockerfile


def test_release_workflow_audits_dependencies_with_only_documented_exception() -> None:
    workflow = yaml.safe_load((ROOT.parent / ".github" / "workflows" / "release.yml").read_text())
    gate_steps = workflow["jobs"]["gates"]["steps"]

    install_step = next(step for step in gate_steps if step.get("name") == "Install Python dependencies")
    assert "python -m pip install --upgrade pip==26.1.2" in install_step["run"]

    audit_step = next(step for step in gate_steps if step.get("name") == "Audit dependencies")
    assert audit_step["run"] == (
        "pip-audit --skip-editable --desc --ignore-vuln GHSA-rrmf-rvhw-rf47"
    )


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
    assert all(step["with"]["trivyignores"] == ".trivyignore" for step in trivy_steps)

    release_step = next(
        step for step in image_steps if step.get("uses") == "softprops/action-gh-release@v2"
    )
    release_files = release_step["with"]["files"]
    assert "release-evidence/license-reports/license-report-backend.md" in release_files
    assert "release-evidence/license-reports/license-report-frontend.md" in release_files
