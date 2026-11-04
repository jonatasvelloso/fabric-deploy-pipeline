from fabric_deploy.cli import main


def test_validate_ok(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    assert main(["validate"]) == 0
    assert "Nenhum problema" in capsys.readouterr().out


def test_validate_com_erro(repo, monkeypatch):
    monkeypatch.chdir(repo)
    (repo / "workspace/Engenharia/Comercial.Lakehouse/lakehouse.metadata.json").unlink()
    assert main(["validate"]) == 1


def test_resumo_no_github_actions(repo, monkeypatch, tmp_path):
    monkeypatch.chdir(repo)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    main(["validate"])
    assert "Validação do workspace" in summary.read_text()


def test_deploy_full_em_prd_recusado(repo, monkeypatch):
    monkeypatch.chdir(repo)
    monkeypatch.setenv("FABRIC_WORKSPACE", "Comercial-PRD")
    assert main(["deploy", "--env", "prd", "--mode", "full"]) == 1


def test_render(repo, monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(repo)
    assert main(["render", "--env", "dev", "--out", str(tmp_path / "out")]) == 0
    assert (tmp_path / "out/workspace/Analytics/Painel Comercial.Report/definition.pbir").exists()


def test_ambiente_inexistente(repo, monkeypatch):
    monkeypatch.chdir(repo)
    assert main(["plan", "--env", "hml"]) == 2
