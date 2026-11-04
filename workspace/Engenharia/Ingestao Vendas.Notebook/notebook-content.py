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

# PARAMETERS CELL ********************

AMBIENTE = "dev"
API_VENDAS_URL = "https://api-dev.vendas.example.com/v1/pedidos"
DATA_REFERENCIA = None  # preenchido pelo pipeline

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

%run funcoes_comuns

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import requests
from datetime import date, timedelta

data_ref = DATA_REFERENCIA or (date.today() - timedelta(days=1)).isoformat()
resposta = requests.get(API_VENDAS_URL, params={"data": data_ref}, timeout=60)
resposta.raise_for_status()

pedidos = spark.createDataFrame(resposta.json()["pedidos"])
(
    com_auditoria(padronizar_colunas(pedidos), origem=API_VENDAS_URL)
    .write.mode("append")
    .saveAsTable("bronze_pedidos")
)
print(f"[{AMBIENTE}] {pedidos.count()} pedidos carregados para {data_ref}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
