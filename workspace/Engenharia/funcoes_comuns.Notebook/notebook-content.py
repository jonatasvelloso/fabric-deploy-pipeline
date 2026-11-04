# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "6b1f6a3e-2c4d-4e8a-9f1b-3a7c5d2e8f01",
# META       "default_lakehouse_name": "Comercial",
# META       "default_lakehouse_workspace_id": "00000000-0000-0000-0000-000000000000"
# META     },
# META     "environment": {
# META       "environmentId": "a2c9e4d7-8b1f-4c3a-9e6d-5f2b7a1c3d02",
# META       "workspaceId": "00000000-0000-0000-0000-000000000000"
# META     }
# META   }
# META }

# CELL ********************

from pyspark.sql import DataFrame, functions as F


def padronizar_colunas(df: DataFrame) -> DataFrame:
    """Nomes de coluna em snake_case, sem acento."""
    import unicodedata

    def limpar(nome: str) -> str:
        sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
        return sem_acento.strip().lower().replace(" ", "_")

    return df.toDF(*[limpar(c) for c in df.columns])


def com_auditoria(df: DataFrame, origem: str) -> DataFrame:
    return df.withColumn("_origem", F.lit(origem)).withColumn("_carregado_em", F.current_timestamp())

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
