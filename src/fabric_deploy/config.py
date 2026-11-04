"""Ambientes de destino (config/environments.yml)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from fabric_deploy.parameters import ENV_PREFIX

DEFAULT_ENVIRONMENTS = Path("config/environments.yml")
DEFAULT_PARAMETERS = Path("config/parameters.yml")


class ConfigError(ValueError):
    """Configuração de ambiente inválida."""


@dataclass(frozen=True)
class Environment:
    name: str
    workspace: str
    protected: bool = False
    allow_deletions: bool = False

    def resolve_workspace(self) -> str:
        """Nome ou ID do workspace; `$ENV:NOME` lê de um secret."""
        if not self.workspace.startswith(ENV_PREFIX):
            return self.workspace
        var = self.workspace.removeprefix(ENV_PREFIX)
        value = os.getenv(var)
        if not value:
            raise ConfigError(f"ambiente {self.name}: variável {var} não definida")
        return value


def load_environments(path: Path = DEFAULT_ENVIRONMENTS) -> dict[str, Environment]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    envs = {}
    for name, raw in (data.get("environments") or {}).items():
        if not isinstance(raw, dict) or not raw.get("workspace"):
            raise ConfigError(f"ambiente {name}: 'workspace' é obrigatório")
        envs[name] = Environment(
            name=name,
            workspace=str(raw["workspace"]),
            protected=bool(raw.get("protected", False)),
            allow_deletions=bool(raw.get("allow_deletions", False)),
        )
    if not envs:
        raise ConfigError(f"nenhum ambiente declarado em {path}")
    return envs
