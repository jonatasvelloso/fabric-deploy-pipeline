"""Validação do workspace antes de qualquer chamada ao Fabric.

Roda em todo pull request, sem credenciais. Pega no PR o que de outra forma
só falharia no meio do deploy: `.platform` quebrado, arquivo obrigatório
faltando, JSON inválido, referência a item que não existe, dependência
circular, parâmetro sem valor para algum ambiente e IDs fixos no código.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

from fabric_deploy import item_types
from fabric_deploy.items import PLATFORM_FILE, Item, discover
from fabric_deploy.parameters import Parameters

GUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
ZERO_GUID = "00000000-0000-0000-0000-000000000000"
JSON_SUFFIXES = {".json", ".pbir", ".pbism"}


@dataclass(frozen=True)
class Issue:
    level: str  # "erro" | "aviso"
    where: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.where}: {self.message}"


def _structure(items: list[Item]) -> list[Issue]:
    issues = []
    seen_ids: dict[str, str] = {}
    seen_keys: set[str] = set()
    for item in items:
        expected = f"{item.display_name}.{item.type}"
        if item.folder.name != expected:
            issues.append(Issue("erro", item.folder.name, f"a pasta deve se chamar '{expected}'"))
        if not GUID.fullmatch(item.logical_id):
            issues.append(Issue("erro", item.key, f"logicalId '{item.logical_id}' não é um GUID"))
        if item.logical_id.lower() in seen_ids:
            issues.append(Issue("erro", item.key, f"logicalId repetido em {seen_ids[item.logical_id.lower()]}"))
        seen_ids[item.logical_id.lower()] = item.key
        if item.key in seen_keys:
            issues.append(Issue("erro", item.key, "nome e tipo repetidos no repositório"))
        seen_keys.add(item.key)

        files = item.files()
        if not item_types.is_known(item.type):
            issues.append(Issue("aviso", item.key, f"tipo '{item.type}' sem regras específicas: validação genérica"))
        for missing in item_types.missing_files(item.type, set(files)):
            issues.append(Issue("erro", item.key, f"arquivo obrigatório ausente: {missing}"))
        for path, file in files.items():
            if file.suffix in JSON_SUFFIXES or path == PLATFORM_FILE:
                try:
                    json.loads(file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    issues.append(Issue("erro", f"{item.key}/{path}", f"JSON inválido ({exc})"))
    return issues


def _references(workspace_dir: Path) -> list[Issue]:
    """Referências entre itens, lidas pelo próprio pyfabricops (mesma regra do deploy)."""
    from pyfabricops import DEPLOY_ORDER
    from pyfabricops.helpers.dependencies import LocalCatalog, scan_references

    catalog = LocalCatalog.read(str(workspace_dir), DEPLOY_ORDER)
    scan = scan_references(catalog, [item.key for item in catalog])
    issues = [
        Issue("erro", f"{name}.{kind}", problem)
        for (kind, name), problems in scan.broken.items()
        for problem in problems
    ]
    graph: dict[tuple, set[tuple]] = {}
    for dep in scan.dependencies:
        graph.setdefault(dep.source, set()).add(dep.target)
    try:
        TopologicalSorter(graph).prepare()
    except CycleError as exc:
        chain = " -> ".join(f"{n}.{t}" for t, n in exc.args[1])
        issues.append(Issue("erro", "workspace", f"dependência circular: {chain}"))
    return issues


def _hardcoded_ids(items: list[Item], params: Parameters) -> list[Issue]:
    """GUID que não é logicalId de item do repositório nem está parametrizado."""
    allowed = {i.logical_id.lower() for i in items} | {ZERO_GUID} | params_literals(params)
    issues = []
    for item in items:
        for path, file in item.files().items():
            if path == PLATFORM_FILE:
                continue
            try:
                text = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            # lineageTag é identificador interno do modelo semântico, não um ID de ambiente
            relevant = "\n".join(line for line in text.splitlines() if "lineageTag" not in line)
            for guid in sorted({g.lower() for g in GUID.findall(relevant)} - allowed):
                issues.append(
                    Issue("aviso", f"{item.key}/{path}", f"ID fixo {guid}: parametrize em config/parameters.yml")
                )
    return issues


def params_literals(params: Parameters) -> set[str]:
    return {r.find.lower() for r in params.rules if not r.regex}


def validate(workspace_dir: Path, params: Parameters, environments: list[str]) -> list[Issue]:
    items, errors = discover(workspace_dir)
    issues = [Issue("erro", "workspace", str(e)) for e in errors]
    if not items and not errors:
        issues.append(Issue("erro", "workspace", f"nenhum item encontrado em {workspace_dir}"))
    issues += _structure(items)
    issues += [Issue("erro", "config/parameters.yml", m) for m in params.missing_environments(environments)]
    issues += _hardcoded_ids(items, params)
    if not any(i.level == "erro" for i in issues):
        issues += _references(workspace_dir)
    return issues
