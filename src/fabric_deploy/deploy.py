"""Orquestração do deploy sobre o pyfabricops.

O pyfabricops faz o trabalho com a API do Fabric: identifica os itens
alterados desde um commit, resolve dependências e ordem, troca logicalIds
pelos IDs do workspace de destino, converte o relatório para `byConnection`
e cria ou atualiza cada item. Esta camada acrescenta o que uma esteira de
produção precisa em volta disso:

- validação estrutural antes de autenticar;
- build isolado: os parâmetros do ambiente são aplicados em uma cópia do
  repositório, nunca nos arquivos versionados;
- proteções: deploy completo bloqueado em ambiente protegido e exclusão de
  itens só onde o ambiente permite;
- plano (dry-run) e relatório no resumo do GitHub Actions.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from fabric_deploy.config import Environment
from fabric_deploy.items import discover
from fabric_deploy.parameters import Parameters
from fabric_deploy.validate import Issue, validate

NULL_COMMIT = "0" * 40
BUILD_IGNORE = shutil.ignore_patterns(".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", "build")


class DeploymentBlocked(RuntimeError):
    """Execução recusada por uma regra de proteção ou validação."""


@dataclass
class DeployRequest:
    environment: Environment
    repo_root: Path
    workspace_dir: Path
    parameters: Parameters
    environments: list[str]
    mode: str = "selective"  # selective | full
    base_ref: str | None = None
    item_types: list[str] | None = None
    allow_deletions: bool = False
    force_full: bool = False
    plan_only: bool = False
    notes: list[str] = field(default_factory=list)

    def effective_mode(self) -> str:
        """Push de branch nova chega com base nula: não há com o que comparar."""
        if self.mode == "selective" and (not self.base_ref or self.base_ref == NULL_COMMIT):
            self.notes.append("Sem commit de referência: executando como deploy completo.")
            return "full"
        return self.mode


def check_protections(request: DeployRequest) -> tuple[str, bool]:
    mode = request.effective_mode()
    env = request.environment
    if mode == "full" and env.protected and not request.force_full and not request.plan_only:
        raise DeploymentBlocked(
            f"deploy completo bloqueado no ambiente protegido '{env.name}'. "
            "Use o modo seletivo ou confirme com --force-full."
        )
    deletions = request.allow_deletions and mode == "selective"
    if request.allow_deletions and not env.allow_deletions:
        raise DeploymentBlocked(f"o ambiente '{env.name}' não permite exclusão de itens (allow_deletions: false)")
    return mode, deletions


def build(request: DeployRequest, target: Path) -> tuple[Path, dict[str, int]]:
    """Copia o repositório (com .git, para o diff seletivo) e aplica os parâmetros."""
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(request.repo_root, target, ignore=BUILD_IGNORE, symlinks=True)
    workspace = target / request.workspace_dir.resolve().relative_to(request.repo_root.resolve())
    items, _ = discover(workspace)
    counts = request.parameters.apply(items, request.environment.name)
    return workspace, counts


def run(request: DeployRequest, fabric=None):
    """Executa plano ou deploy. `fabric` é o módulo pyfabricops (injetável nos testes)."""
    issues = validate(request.workspace_dir, request.parameters, request.environments)
    errors = [i for i in issues if i.level == "erro"]
    if errors:
        raise DeploymentBlocked("validação falhou:\n" + "\n".join(map(str, errors)))
    mode, deletions = check_protections(request)

    if fabric is None:
        import pyfabricops as fabric

    with tempfile.TemporaryDirectory(prefix="fabric-build-") as tmp:
        repo_copy = Path(tmp) / "repo"
        workspace, counts = build(request, repo_copy)
        fabric.set_auth_provider("env")
        kwargs = dict(
            workspace=request.environment.resolve_workspace(),
            path=str(workspace),
            item_types=request.item_types or None,
            baseline_commit=request.base_ref if mode == "selective" else None,
            repository_path=str(repo_copy),
            environment=request.environment.name,
            allow_deletions=deletions,
        )
        if request.plan_only:
            result = fabric.plan_all_items(**kwargs)
        else:
            result = fabric.deploy_all_items(**kwargs, fail_fast=False)
    return Outcome(mode=mode, deletions=deletions, parameter_counts=counts, result=result, issues=issues)


@dataclass
class Outcome:
    mode: str
    deletions: bool
    parameter_counts: dict[str, int]
    result: object
    issues: list[Issue]
