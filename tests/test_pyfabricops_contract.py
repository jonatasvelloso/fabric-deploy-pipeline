"""Contrato com o pyfabricops real, sem acessar o Fabric."""

import pyfabricops as pf
from pyfabricops.helpers.dependencies import LocalCatalog, scan_references

from fabric_deploy.items import discover


def test_todos_os_tipos_do_workspace_sao_implantados_pelo_pyfabricops(repo):
    items, _ = discover(repo / "workspace")
    assert {i.type for i in items} <= set(pf.DEPLOY_ORDER)


def test_pyfabricops_empacota_cada_item(repo):
    items, _ = discover(repo / "workspace")
    for item in items:
        parts = {p["path"] for p in pf.pack_item_definition(str(item.folder))["parts"]}
        assert ".platform" in parts, item.key
        assert len(parts) > 1, item.key


def test_dependencias_lidas_pelo_pyfabricops(repo):
    catalog = LocalCatalog.read(str(repo / "workspace"), pf.DEPLOY_ORDER)
    scan = scan_references(catalog, [i.key for i in catalog])
    edges = {(d.source[1], d.target[1]) for d in scan.dependencies}
    assert ("Painel Comercial", "Comercial") in edges  # relatório -> modelo
    assert ("Ingestao Vendas", "Comercial") in edges  # notebook -> lakehouse
    assert ("Ingestao Vendas", "Spark Padrao") in edges  # notebook -> environment
    assert ("Ingestao Vendas", "funcoes_comuns") in edges  # %run
    assert not scan.broken
