import json
import shutil

from fabric_deploy.parameters import Parameters
from fabric_deploy.validate import validate

ENVS = ["dev", "prd"]


def _issues(repo, params=None):
    params = params or Parameters.load(repo / "config/parameters.yml")
    return validate(repo / "workspace", params, ENVS)


def _errors(issues):
    return [str(i) for i in issues if i.level == "erro"]


def test_workspace_do_repositorio_e_valido(repo):
    assert _issues(repo) == []


def test_platform_invalido(repo):
    (repo / "workspace/Engenharia/Comercial.Lakehouse/.platform").write_text("{quebrado")
    assert any(".platform inválido" in e for e in _errors(_issues(repo)))


def test_pasta_com_nome_diferente_do_item(repo):
    ws = repo / "workspace/Engenharia"
    (ws / "Comercial.Lakehouse").rename(ws / "Outro.Lakehouse")
    assert any("deve se chamar 'Comercial.Lakehouse'" in e for e in _errors(_issues(repo)))


def test_arquivo_obrigatorio_ausente(repo):
    (repo / "workspace/Engenharia/Carga Diaria Comercial.DataPipeline/pipeline-content.json").unlink()
    assert any("pipeline-content.json" in e for e in _errors(_issues(repo)))


def test_logical_id_duplicado(repo):
    ws = repo / "workspace/Engenharia"
    shutil.copytree(ws / "Ingestao Vendas.Notebook", ws / "Copia.Notebook")
    platform = ws / "Copia.Notebook/.platform"
    data = json.loads(platform.read_text())
    data["metadata"]["displayName"] = "Copia"
    platform.write_text(json.dumps(data))
    assert any("logicalId repetido" in e for e in _errors(_issues(repo)))


def test_json_invalido_em_arquivo_da_definicao(repo):
    (repo / "workspace/Analytics/Painel Comercial.Report/definition/report.json").write_text("{")
    assert any("JSON inválido" in e for e in _errors(_issues(repo)))


def test_relatorio_apontando_para_modelo_inexistente(repo):
    pbir = repo / "workspace/Analytics/Painel Comercial.Report/definition.pbir"
    pbir.write_text(
        json.dumps({"version": "4.0", "datasetReference": {"byPath": {"path": "../Nao Existe.SemanticModel"}}})
    )
    assert any("Nao Existe.SemanticModel" in e for e in _errors(_issues(repo)))


def _notebook(ws, name, logical_id, body):
    folder = ws / f"{name}.Notebook"
    folder.mkdir()
    (folder / ".platform").write_text(
        json.dumps({"metadata": {"type": "Notebook", "displayName": name}, "config": {"logicalId": logical_id}})
    )
    (folder / "notebook-content.py").write_text(f"# Fabric notebook source\n\n# CELL ********************\n\n{body}\n")


def test_dependencia_circular_entre_notebooks(repo):
    ws = repo / "workspace/Engenharia"
    _notebook(ws, "nb_a", "1a1a1a1a-0000-4000-8000-000000000001", "%run nb_b")
    _notebook(ws, "nb_b", "2b2b2b2b-0000-4000-8000-000000000002", "%run nb_a")
    assert any("dependência circular" in e for e in _errors(_issues(repo)))


def test_id_fixo_gera_aviso(repo):
    notebook = repo / "workspace/Engenharia/Transformacao Vendas.Notebook/notebook-content.py"
    notebook.write_text(notebook.read_text() + '\nWORKSPACE_PRD = "11111111-2222-3333-4444-555555555555"\n')
    avisos = [str(i) for i in _issues(repo) if i.level == "aviso"]
    assert any("11111111-2222-3333-4444-555555555555" in a for a in avisos)


def test_parametro_sem_valor_para_um_ambiente(repo):
    (repo / "config/parameters.yml").write_text(
        "find_replace:\n  - find: x\n    description: regra incompleta\n    replace: {dev: y}\n"
    )
    assert any("sem valor para prd" in e for e in _errors(_issues(repo)))


def test_tipo_desconhecido_e_aceito_com_aviso(repo):
    ws = repo / "workspace/Engenharia/Alertas.Reflex"
    ws.mkdir()
    (ws / ".platform").write_text(
        json.dumps(
            {
                "metadata": {"type": "Reflex", "displayName": "Alertas"},
                "config": {"logicalId": "0f0e0d0c-0b0a-4908-8706-050403020100"},
            }
        )
    )
    issues = _issues(repo)
    assert _errors(issues) == []
    assert any("Reflex" in str(i) and i.level == "aviso" for i in issues)
