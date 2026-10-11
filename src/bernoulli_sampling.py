# Databricks notebook source
import json

from sampling import draw_sample, oversampled_fraction, qualified_name


def main():
    print("=== Delta Table Bernoulli Sampler ===")

    # 1. Define Databricks Widgets (Parameters)
    dbutils.widgets.text("catalog", "workspace")
    dbutils.widgets.text("schema", "default")
    dbutils.widgets.text("table", "test_population")
    dbutils.widgets.text("target_size", "385")
    dbutils.widgets.text("output_table", "test_population_sample")
    dbutils.widgets.text("seed", "42")

    # 2. Retrieve values from Widgets
    catalog = dbutils.widgets.get("catalog")
    schema = dbutils.widgets.get("schema")
    table_name = dbutils.widgets.get("table")
    target_sample_size = int(dbutils.widgets.get("target_size"))
    output_table = dbutils.widgets.get("output_table")
    seed = int(dbutils.widgets.get("seed"))

    if target_sample_size <= 0:
        raise ValueError(f"Target sample size must be greater than 0. Got {target_sample_size}.")
    # Unity Catalog names are case-insensitive
    if output_table.lower() == table_name.lower():
        raise ValueError("output_table must differ from table, otherwise the sample overwrites the source table.")

    full_table_name = qualified_name(catalog, schema, table_name)
    full_output_name = qualified_name(catalog, schema, output_table)

    # Note: 'spark' is automatically injected into notebook tasks
    print(f"Counting rows in {full_table_name}...")
    total_rows = spark.table(full_table_name).count()
    if total_rows == 0:
        raise ValueError(f"Table {full_table_name} is empty.")

    expected_rows = min(target_sample_size, total_rows)
    if target_sample_size >= total_rows:
        print(f"Target sample size ({target_sample_size:,}) is not smaller than the table ({total_rows:,} rows). Copying the whole table.")
        fraction = 1.0
    else:
        fraction = oversampled_fraction(target_sample_size, total_rows)

    sample_df = draw_sample(spark.table(full_table_name), target_sample_size, total_rows, seed)
    (
        sample_df.write.mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(full_output_name)
    )

    written_rows = spark.table(full_output_name).count()
    if written_rows < expected_rows:
        raise RuntimeError(
            f"{full_output_name} has {written_rows:,} rows instead of {expected_rows:,}. "
            "The Bernoulli pass fell short (probability below 1e-4). Rerun with a different seed."
        )

    result = {
        "table": full_table_name,
        "population": total_rows,
        "target_size": target_sample_size,
        "bernoulli_fraction": fraction,
        "seed": seed,
        "output_table": full_output_name,
        "sample_rows": written_rows,
    }
    print(json.dumps(result, indent=2))
    dbutils.notebook.exit(json.dumps(result))


if __name__ == "__main__":
    main()
