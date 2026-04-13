from pathlib import Path


def test_deploy_files_exist():
    root = Path(__file__).resolve().parents[2]

    required = [
        root / "deploy" / "Caddyfile",
        root / "deploy" / "systemd" / "messgo.service",
        root / "deploy" / "scripts" / "deploy.sh",
        root / ".github" / "workflows" / "ci.yml",
        root / ".github" / "workflows" / "deploy.yml",
        root / ".github" / "SECRETS.md",
    ]

    missing = [str(path) for path in required if not path.exists()]
    assert not missing, f"Отсутствуют файлы: {missing}"
