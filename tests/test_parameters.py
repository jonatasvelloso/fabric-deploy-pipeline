import pytest

from fabric_deploy.items import discover
from fabric_deploy.parameters import ParameterError, Parameters


def _render(repo, env):
    items, _ = discover(repo / "workspace")
    counts = Parameters.load(repo / "config/parameters.yml").apply(items, env)
    return counts, repo / "workspace"


def _read(ws, path):
    return (ws / path).read_text()


def test_prd_recebe_valores_de_producao(repo, monkeypatch):
    monkeypatch.setenv("FABRIC_SQL_ENDPOINT", "comercial.datawarehouse.fabric.example.com")
    counts, ws = _render(repo, "prd")
    assert 'Sql.Database("comercial.datawarehouse' in _read(
        ws, "Analytics/Comercial.SemanticModel/definition/expressions.tmdl"
    )
    ingestao = _read(ws, "Engenharia/Ingestao Vendas.Notebook/notebook-content.py")
    assert "https://api.vendas.example.com" in ingestao and 'AMBIENTE = "prd"' in ingestao
    assert '"defaultValue": "prd"' in _read(ws, "Engenharia/Carga Diaria Comercial.DataPipeline/pipeline-content.json")
    assert all(n > 0 for n in counts.values())


def test_filtro_por_nome_de_item(repo, monkeypatch):
    monkeypatch.setenv("FABRIC_SQL_ENDPOINT", "x")
    _, ws = _render(repo, "prd")
    transformacao = _read(ws, "Engenharia/Transformacao Vendas.Notebook/notebook-content.py")
    assert 'AMBIENTE = "prd"' in transformacao  # regra por tipo
    assert "api.vendas" not in transformacao  # regra restrita à ingestão


def test_secret_ausente_interrompe(repo, monkeypatch):
    monkeypatch.delenv("FABRIC_SQL_ENDPOINT", raising=False)
    with pytest.raises(ParameterError, match="FABRIC_SQL_ENDPOINT"):
        _render(repo, "prd")


def test_platform_nunca_e_alterado(repo, monkeypatch):
    monkeypatch.setenv("FABRIC_SQL_ENDPOINT", "x")
    (repo / "config/parameters.yml").write_text(
        "find_replace:\n  - find: Comercial\n    replace: {dev: Comercial, prd: Vendas}\n"
    )
    _, ws = _render(repo, "prd")
    assert '"displayName": "Comercial"' in _read(ws, "Engenharia/Comercial.Lakehouse/.platform")


def test_regex(repo):
    (repo / "config/parameters.yml").write_text(
        'find_replace:\n  - find: "AMBIENTE = \\"\\\\w+\\""\n    regex: true\n'
        '    replace: {dev: "AMBIENTE = \\"dev\\"", prd: "AMBIENTE = \\"homolog\\""}\n'
    )
    _, ws = _render(repo, "prd")
    assert 'AMBIENTE = "homolog"' in _read(ws, "Engenharia/Transformacao Vendas.Notebook/notebook-content.py")


def test_regra_sem_replace_e_rejeitada(tmp_path):
    path = tmp_path / "p.yml"
    path.write_text("find_replace:\n  - find: x\n")
    with pytest.raises(ParameterError, match="obrigatórios"):
        Parameters.load(path)
