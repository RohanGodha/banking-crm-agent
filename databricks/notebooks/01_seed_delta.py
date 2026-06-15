# Databricks notebook source
# MAGIC %md
# MAGIC # banking_crm — Delta seed
# MAGIC
# MAGIC Idempotent notebook that creates the catalog, schema, and six Delta tables
# MAGIC used by `banking-crm-agent`. Run it once after setting up your Free Edition
# MAGIC workspace + serverless SQL warehouse.

# COMMAND ----------

CATALOG = "banking_crm"
SCHEMA = "core"

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE SCHEMA  IF NOT EXISTS {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Table DDLs

DDLS = [
    f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.customers (
        id STRING, name STRING, age INT, city STRING, segment STRING, employment STRING,
        monthly_income DOUBLE, account_open_date DATE, kyc_status STRING, phone STRING,
        email STRING, risk_appetite STRING
    ) USING DELTA
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.accounts (
        id STRING, customer_id STRING, type STRING, balance DOUBLE,
        avg_balance_6m DOUBLE, opened_at DATE
    ) USING DELTA
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.transactions (
        id STRING, customer_id STRING, ts TIMESTAMP, amount DOUBLE,
        category STRING, channel STRING, merchant STRING
    ) USING DELTA
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.products (
        id STRING, name STRING, category STRING, interest_rate DOUBLE,
        min_income DOUBLE, min_age INT, max_age INT, description STRING,
        eligibility_json STRING
    ) USING DELTA
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.holdings (
        customer_id STRING, product_id STRING, opened_at DATE, status STRING
    ) USING DELTA
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.interactions (
        id STRING, customer_id STRING, ts TIMESTAMP, channel STRING, summary STRING
    ) USING DELTA
    """,
]

for d in DDLS:
    spark.sql(d)
print("Tables created.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Loading data
# MAGIC
# MAGIC Upload the CSV exports produced by `backend/scripts/export_sqlite_to_csv.py`
# MAGIC to `/Volumes/banking_crm/core/seed/` (a Unity Catalog Volume). Then run the
# MAGIC cells below to MERGE them into the Delta tables.

VOLUME = f"/Volumes/{CATALOG}/{SCHEMA}/seed"
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.seed")

def load(table: str, schema: str | None = None):
    path = f"{VOLUME}/{table}.csv"
    df = (
        spark.read.option("header", True)
        .option("inferSchema", True)
        .csv(path)
    )
    if schema:
        for col, typ in schema.items():
            df = df.withColumn(col, df[col].cast(typ))
    df.write.format("delta").mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.{table}")
    print(f"loaded {table}: {df.count()} rows")

load("customers")
load("accounts")
load("transactions")
load("products")
load("holdings")
load("interactions")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify

for t in ["customers", "accounts", "transactions", "products", "holdings", "interactions"]:
    cnt = spark.sql(f"SELECT COUNT(*) c FROM {CATALOG}.{SCHEMA}.{t}").first()["c"]
    print(f"{t:20s} {cnt:>8d} rows")
