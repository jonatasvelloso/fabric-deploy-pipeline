"""Orquestração do deploy com o pyfabricops substituído por um dublê."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from fabric_deploy.config import load_environments
from fabric_deploy.deploy import NULL_COMMIT, DeploymentBlocked, DeployRequest, run
from fabric_deploy.parameters import Parameters


class FakeFabric:
    """Registra as chamadas e inspeciona a cópia de build no momento do deploy."""

    def __init__(self):
        self.calls = []

    def set_auth_provider(self, source):
        self.calls.append(("auth", source))

    def _record(self, name, kwargs):
        ws = Path(kwargs["path"])
        ingestao = (ws / "Engenharia/Ingestao Vendas.Notebook/notebook-content.py").read_text()
        self.calls.append((name, kwargs, ingestao, (Path(kwargs["repository_path"]) / ".git").exists()))

    def plan_all_items(self, **kwargs):
        self._record("plan", kwargs)
        return SimpleNamespace(actions=[])

    def deploy_all_items(self, **kwargs):
        self._record("deploy", kwargs)
        return SimpleNamespace(results=[], ok=True)


@pytest.fixture(autouse=True)
def secrets(monkeypatch):
    monkeypatch.setenv("FABRIC_WORKSPACE", "Comercial-PRD")
    monkeypatch.setenv("FABRIC_SQL_ENDPOINT", "comercial.datawarehouse.fabric.example.com")


def _request(repo, env="prd", **kwargs):
    envs = load_environments(repo / "config/environments.yml")
    return DeployRequest(
        environment=envs[env],
        repo_root=repo,
        workspace_dir=repo / "workspace",
        parameters=Parameters.load(repo / "config/parameters.yml"),
        environments=list(envs),
        **kwargs,
    )


def test_deploy_seletivo_em_build_parametrizado(repo, git):
    base = git(repo, "rev-parse", "HEAD")
    fabric = FakeFabric()
    outcome = run(_request(repo, base_ref=base), fabric=fabric)

    name, kwargs, ingestao, has_git = fabric.calls[-1]
    assert (name, outcome.mode) == ("deploy", "selective")
    assert kwargs["workspace"] == "Comercial-PRD"
    assert kwargs["baseline_commit"] == base
    assert kwargs["allow_deletions"] is False
    assert has_git, "a cópia de build precisa do .git para o diff seletivo"
    assert "api.vendas.example.com" in ingestao and "api-dev" not in ingestao
    # o repositório versionado continua com os valores de DEV
    original = (repo / "workspace/Engenharia/Ingestao Vendas.Notebook/notebook-content.py").read_text()
    assert "api-dev.vendas.example.com" in original


def test_full_bloqueado_em_ambiente_protegido(repo):
    with pytest.raises(DeploymentBlocked, match="protegido"):
        run(_request(repo, mode="full"), fabric=FakeFabric())


def test_full_liberado_com_confirmacao(repo):
    fabric = FakeFabric()
    run(_request(repo, mode="full", force_full=True), fabric=fabric)
    assert fabric.calls[-1][1]["baseline_commit"] is None


def test_plano_completo_nao_precisa_de_confirmacao(repo):
    fabric = FakeFabric()
    run(_request(repo, mode="full", plan_only=True), fabric=fabric)
    assert fabric.calls[-1][0] == "plan"


def test_base_nula_vira_deploy_completo_no_dev(repo):
    request = _request(repo, env="dev", base_ref=NULL_COMMIT)
    outcome = run(request, fabric=FakeFabric())
    assert outcome.mode == "full"
    assert any("deploy completo" in n for n in request.notes)


def test_exclusao_recusada_em_producao(repo, git):
    with pytest.raises(DeploymentBlocked, match="não permite exclusão"):
        run(_request(repo, base_ref=git(repo, "rev-parse", "HEAD"), allow_deletions=True), fabric=FakeFabric())


def test_exclusao_permitida_no_dev(repo, git):
    fabric = FakeFabric()
    run(_request(repo, env="dev", base_ref=git(repo, "rev-parse", "HEAD"), allow_deletions=True), fabric=fabric)
    assert fabric.calls[-1][1]["allow_deletions"] is True


def test_validacao_falha_antes_de_autenticar(repo):
    (repo / "workspace/Engenharia/Comercial.Lakehouse/lakehouse.metadata.json").unlink()
    fabric = FakeFabric()
    with pytest.raises(DeploymentBlocked, match="validação falhou"):
        run(_request(repo, mode="full", force_full=True), fabric=fabric)
    assert fabric.calls == []


def test_filtro_de_tipos(repo):
    fabric = FakeFabric()
    run(_request(repo, env="dev", mode="full", item_types=["Notebook", "Report"]), fabric=fabric)
    assert fabric.calls[-1][1]["item_types"] == ["Notebook", "Report"]
