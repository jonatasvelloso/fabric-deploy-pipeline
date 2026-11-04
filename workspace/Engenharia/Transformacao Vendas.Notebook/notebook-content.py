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

from pyspark.sql import functions as F

silver = (
    spark.read.table("bronze_pedidos")
    .dropDuplicates(["pedido_id"])
    .withColumn("data_pedido", F.to_date("data_pedido"))
    .withColumn("valor_total", F.col("quantidade") * F.col("preco_unitario"))
)
silver.write.mode("overwrite").saveAsTable("silver_pedidos")

(
    silver.select("produto_id", "produto_nome", "categoria")
    .dropDuplicates(["produto_id"])
    .write.mode("overwrite")
    .saveAsTable("dim_produto")
)
(
    silver.groupBy("data_pedido", "produto_id")
    .agg(F.sum("quantidade").alias("quantidade"), F.sum("valor_total").alias("receita"))
    .write.mode("overwrite")
    .saveAsTable("fato_vendas")
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
