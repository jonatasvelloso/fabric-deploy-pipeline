"""Parametrização por ambiente (config/parameters.yml).

O pyfabricops já troca o que é estrutural: logicalId -> ID do item no
workspace de destino, GUID zerado -> ID do workspace e `byPath` -> `byConnection`
no relatório. O que é de negócio fica aqui: endpoints, nomes de bancos,
parâmetros de notebook, URLs de API que mudam entre DEV e PRD.

Cada regra é um find/replace com valor por ambiente, filtrável por tipo de
item, nome de item e padrão de arquivo. Valores `$ENV:NOME` vêm de variáveis
de ambiente (secrets do GitHub), então nada sensível fica no repositório.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from fabric_deploy.items import PLATFORM_FILE, Item

ENV_PREFIX = "$ENV:"


class ParameterError(ValueError):
    """Regra de parâmetro inválida ou valor indisponível."""


@dataclass(frozen=True)
class Rule:
    find: str
    replace: dict[str, str | None]
    description: str = ""
    regex: bool = False
    item_types: tuple[str, ...] = ()
    item_names: tuple[str, ...] = ()
    file_pattern: str | None = None

    @property
    def label(self) -> str:
        return self.description or self.find

    def applies_to(self, item: Item, path: str) -> bool:
        if path == PLATFORM_FILE:
            return False  # metadados do item nunca são parametrizados
        if self.item_types and item.type not in self.item_types:
            return False
        if self.item_names and item.display_name not in self.item_names:
            return False
        return not (self.file_pattern and not re.search(self.file_pattern, path))

    def value_for(self, environment: str) -> str | None:
        """Valor do ambiente; None quando a regra não se aplica a ele."""
        raw = self.replace.get(environment)
        if raw is None or not raw.startswith(ENV_PREFIX):
            return raw
        name = raw.removeprefix(ENV_PREFIX)
        value = os.getenv(name)
        if not value:
            raise ParameterError(f"variável de ambiente {name} não definida (regra: {self.label})")
        return value

    def env_vars(self) -> set[str]:
        return {v.removeprefix(ENV_PREFIX) for v in self.replace.values() if v and v.startswith(ENV_PREFIX)}


@dataclass(frozen=True)
class Parameters:
    rules: tuple[Rule, ...] = field(default_factory=tuple)

    @classmethod
    def load(cls, path: Path) -> Parameters:
        if not path.exists():
            return cls()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        rules = []
        for i, raw in enumerate(data.get("find_replace") or []):
            where = f"find_replace[{i}]"
            if not isinstance(raw, dict) or not raw.get("find") or not isinstance(raw.get("replace"), dict):
                raise ParameterError(f"{where}: 'find' e 'replace' (um valor por ambiente) são obrigatórios")
            if raw.get("regex"):
                try:
                    re.compile(raw["find"])
                except re.error as exc:
                    raise ParameterError(f"{where}: regex inválida ({exc})") from exc
            rules.append(
                Rule(
                    find=str(raw["find"]),
                    replace={str(k): (None if v is None else str(v)) for k, v in raw["replace"].items()},
                    description=raw.get("description", ""),
                    regex=bool(raw.get("regex", False)),
                    item_types=tuple(raw.get("item_types") or ()),
                    item_names=tuple(raw.get("item_names") or ()),
                    file_pattern=raw.get("file_pattern"),
                )
            )
        return cls(tuple(rules))

    def missing_environments(self, environments: list[str]) -> list[str]:
        """Regras sem decisão explícita para algum ambiente (erro de configuração)."""
        return [
            f"{rule.label}: sem valor para {env}"
            for rule in self.rules
            for env in environments
            if env not in rule.replace
        ]

    def apply(self, items: list[Item], environment: str) -> dict[str, int]:
        """Aplica as regras nos arquivos dos itens (em uma cópia de build).

        Retorna quantas substituições cada regra fez, para o relatório.
        """
        counts = {rule.label: 0 for rule in self.rules}
        for item in items:
            for path, file in item.files().items():
                try:
                    text = file.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue  # binários (imagens de relatório) ficam como estão
                new = text
                for rule in self.rules:
                    if not rule.applies_to(item, path):
                        continue
                    value = rule.value_for(environment)
                    if value is None:
                        continue
                    if rule.regex:
                        new, n = re.subn(rule.find, value, new)
                    else:
                        n = new.count(rule.find)
                        new = new.replace(rule.find, value)
                    counts[rule.label] += n
                if new != text:
                    file.write_text(new, encoding="utf-8")
        return counts
