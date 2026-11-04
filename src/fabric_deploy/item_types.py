"""Regras de validação por tipo de item do Fabric.

A esteira implanta qualquer tipo de item que o pyfabricops e a API do Fabric
aceitem. Este registro só acrescenta checagens estruturais antes do deploy:
um tipo que não está aqui é validado de forma genérica (`.platform` e JSON).
"""

from __future__ import annotations

NOTEBOOK_SOURCES = (
    "notebook-content.py",
    "notebook-content.sql",
    "notebook-content.scala",
    "notebook-content.r",
    "notebook-content.ipynb",
)

# Cada tupla interna é um grupo: ao menos um dos arquivos deve existir.
REQUIRED_FILES: dict[str, tuple[tuple[str, ...], ...]] = {
    "Lakehouse": (("lakehouse.metadata.json",),),
    "Notebook": (NOTEBOOK_SOURCES,),
    "DataPipeline": (("pipeline-content.json",),),
    "SemanticModel": (("definition.pbism",), ("definition/model.tmdl", "model.bim")),
    "Report": (("definition.pbir",),),
    "SparkJobDefinition": (("SparkJobDefinitionV1.json",),),
    "Dataflow": (("mashup.pq",),),
    "VariableLibrary": (("variables.json",),),
    "Environment": (),
    "Warehouse": (),
    "Eventhouse": (),
    "KQLDatabase": (),
    "CopyJob": (("copyjob-content.json",),),
}


def is_known(item_type: str) -> bool:
    return item_type in REQUIRED_FILES


def missing_files(item_type: str, files: set[str]) -> list[str]:
    """Grupos de arquivos obrigatórios ausentes, já formatados para a mensagem."""
    missing = []
    for group in REQUIRED_FILES.get(item_type, ()):
        if not any(f in files for f in group):
            missing.append(" ou ".join(group))
    return missing
