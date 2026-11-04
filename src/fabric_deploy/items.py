"""Leitura dos itens no formato de Git do Fabric.

Cada item é uma pasta `<Nome>.<Tipo>` com um arquivo `.platform`
(metadados + logicalId) e os arquivos da definição: o mesmo formato que a
integração nativa do Fabric com Git exporta e que o pyfabricops implanta.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PLATFORM_FILE = ".platform"


class ItemError(ValueError):
    """Pasta de item com `.platform` ilegível."""


@dataclass(frozen=True)
class Item:
    folder: Path
    type: str
    display_name: str
    logical_id: str

    @property
    def key(self) -> str:
        return f"{self.display_name}.{self.type}"

    def files(self) -> dict[str, Path]:
        """Arquivos do item por caminho relativo (posix)."""
        return {p.relative_to(self.folder).as_posix(): p for p in sorted(self.folder.rglob("*")) if p.is_file()}


def read_item(folder: Path) -> Item:
    try:
        platform = json.loads((folder / PLATFORM_FILE).read_text(encoding="utf-8"))
        return Item(
            folder=folder,
            type=platform["metadata"]["type"],
            display_name=platform["metadata"]["displayName"],
            logical_id=platform["config"]["logicalId"],
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ItemError(f"{folder.name}: .platform inválido ({exc})") from exc


def discover(root: Path) -> tuple[list[Item], list[ItemError]]:
    """Todos os itens sob `root`, em qualquer profundidade (pastas do workspace)."""
    items, errors = [], []
    for platform in sorted(root.rglob(PLATFORM_FILE)):
        try:
            items.append(read_item(platform.parent))
        except ItemError as exc:
            errors.append(exc)
    return sorted(items, key=lambda i: (i.type, i.display_name)), errors
