import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path) -> Path:
    """Cópia do projeto em um repositório Git temporário, com um commit inicial."""
    target = tmp_path / "repo"
    target.mkdir()
    for name in ("workspace", "config"):
        shutil.copytree(ROOT / name, target / name)
    _git(target, "init", "-q", "-b", "main")
    _git(target, "add", "-A")
    _git(target, "commit", "-qm", "inicial")
    return target


@pytest.fixture
def git():
    return _git
