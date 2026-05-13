from pathlib import Path


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
