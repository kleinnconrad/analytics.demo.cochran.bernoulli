# Databricks notebook source
import json

from sampling import cochran_sample_size, qualified_name, z_score


def main():
    print("=== Delta Table Sample Size Calculator (Cochran) ===")

    # 1. Define Databricks Widgets (Parameters)
    dbutils.widgets.text("catalog", "workspace")
    dbutils.widgets.text("schema", "default")
    dbutils.widgets.text("table", "test_population")
    dbutils.widgets.text("error", "0.05")
    dbutils.widgets.text("proportion", "0.5")
    dbutils.widgets.text("confidence", "95")

    # 2. Retrieve values from Widgets
    catalog = dbutils.widgets.get("catalog")
    schema = dbutils.widgets.get("schema")
    table_name = dbutils.widgets.get("table")
    e = float(dbutils.widgets.get("error"))
    p = float(dbutils.widgets.get("proportion"))
    confidence = float(dbutils.widgets.get("confidence"))

    # Validates the parameters before the table is read
    n0 = cochran_sample_size(e, p, confidence)

    # Note: 'spark' is automatically injected into notebook tasks
    full_table_name = qualified_name(catalog, schema, table_name)
    print(f"Counting rows in {full_table_name}...")
    N = spark.table(full_table_name).count()
    if N == 0:
        raise ValueError(f"Table {full_table_name} is empty.")

    final_sample_size = cochran_sample_size(e, p, confidence, population=N)

    result = {
        "table": full_table_name,
        "population": N,
        "z_score": z_score(confidence),
        "sample_size_infinite_population": n0,
        "sample_size": final_sample_size,
        "fraction": final_sample_size / N,
    }
    print(json.dumps(result, indent=2))

    # Downstream tasks read the value as {{tasks.<task_key>.values.sample_size}}
    dbutils.jobs.taskValues.set(key="sample_size", value=final_sample_size)
    dbutils.notebook.exit(json.dumps(result))


if __name__ == "__main__":
    main()
