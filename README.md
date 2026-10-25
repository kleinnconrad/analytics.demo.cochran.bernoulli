[![Test and Deploy](https://github.com/kleinnconrad/analytics.demo.cochran.bernoulli/actions/workflows/deploy_bundle.yml/badge.svg)](https://github.com/kleinnconrad/analytics.demo.cochran.bernoulli/actions/workflows/deploy_bundle.yml)

# Delta Table Sampling Utilities

This repository provides Python utilities packaged as a **Databricks Asset Bundle (DAB)**. They calculate the sample size required to estimate a proportion in a Delta table (Cochran's formula) and write a simple random sample of that size to a new Delta table using PySpark.

## Table of Contents
1. [Overview](#overview)
2. [Repository Structure](#repository-structure)
3. [Sample Size Calculator (Cochran)](#sample-size-calculator-cochran)
4. [Sample Drawing (Bernoulli)](#sample-drawing-bernoulli)
5. [Deployment & Execution](#deployment--execution)
6. [Local Development](#local-development)
7. [CI/CD Pipeline](#cicd-pipeline)
8. [Test Suite](#test-suite)

---

## Overview
Taking the first rows of a table (e.g., `LIMIT 10000`) does not produce a random sample: which rows are returned depends on file layout and write order, and the size is chosen without a statistical basis. The bundle provides two jobs for this task:

* **`cochran_sample_size`**: Calculates the minimum sample size for estimating a proportion with a given margin of error and confidence level.
* **`bernoulli_sample_drawing`**: Calculates that sample size and writes a simple random sample of exactly that many rows to a Delta table.

**Scope:** Cochran's formula applies to estimating a single proportion from a simple random sample (for example, the share of rows with a given property). It is not a power analysis. Sample sizes for A/B tests, which compare two groups, require a two-sample power calculation with an effect size and a statistical power.

**Cost:** Both jobs read the full source table. `count()` on a Delta table is usually answered from table metadata, but `.sample()` scans every row. Sampling reduces the amount of data used downstream, not the cost of the sampling step.

---

## Repository Structure
* **`databricks.yml`**: Bundle configuration: bundle name, the `dev` workspace target, and the default job parameters (`variables`).
* **`resources/`**: Job definitions for serverless Databricks Jobs.
  * `sample_size_job.yml`: Cochran sample size calculation.
  * `sample_drawing.yml`: Cochran calculation followed by sample drawing.
* **`src/`**: Code deployed to the workspace.
  * `sampling.py`: Calculation and sampling functions. Plain Python module, imported by the notebooks and the tests.
  * `cochran.py`, `bernoulli_sampling.py`: Databricks notebooks that read the job parameters and call `sampling.py`.
* **`tests/`**: Unit tests and Spark integration tests.
* **`pyproject.toml`, `uv.lock`**: Development dependencies, managed with [uv](https://docs.astral.sh/uv/).
* **`.github/`**: CI/CD workflow, Dependabot configuration, and Dependabot auto-approval.

---

## Sample Size Calculator (Cochran)

Cochran's formula calculates the minimum sample size based on the desired margin of error and confidence level. It works in two steps.

### 1. Base Sample Size (Infinite Population)
Assumes an infinitely large population.

$$n_0 = \frac{Z^2 p q}{e^2}$$

* **Z**: Two-sided z-value for the confidence level, computed from the standard normal distribution (e.g., 1.960 for 95%, 2.576 for 99%).
* **p**: Expected proportion. 0.5 gives the largest sample size and is used when no estimate is available.
* **q**: 1 - p.
* **e**: Margin of error as an absolute proportion. 0.05 means +/- 5 percentage points, not 5% of p.

### 2. Finite Population Correction
Reduces the sample size based on the row count of the Delta table.

$$n = \frac{n_0}{1 + \frac{n_0 - 1}{N}}$$

* **n**: Final sample size, rounded up to the next integer.
* **N**: Population size (row count of the table).

With the default parameters (95% confidence, p = 0.5, e = 0.05), n<sub>0</sub> rounds up to 385 rows. For a table with 1,000 rows, the correction reduces this to 278 rows.

### Output
The `cochran.py` notebook:
* prints the population, z-value, base and corrected sample size, and the sampling fraction n / N,
* returns the same values as JSON (`dbutils.notebook.exit`), visible in the job run output,
* stores the sample size as the task value `sample_size` for downstream tasks.

The run fails if the table cannot be read, the table is empty, or a parameter is out of range (confidence outside 50-100, p or e outside 0-1).

---

## Sample Drawing (Bernoulli)

The `bernoulli_sample_drawing` job runs two tasks. `compute_sample_size` runs `cochran.py`. `draw_sample` runs `bernoulli_sampling.py` and receives the sample size n through the task value.

`bernoulli_sampling.py` draws the sample in two steps:

1. **Bernoulli pass:** Each row is kept independently with probability f. A Bernoulli sample with f = n / N has an expected size of n and contains fewer than n rows in about half of all runs. The fraction is therefore increased so that the expected row count m satisfies m - 4 * sqrt(m) = n. For n = 385, m is about 472. A result below n rows then has a probability below 1e-4.
2. **Exact size:** The rows from step 1 are put in random order, and the first n rows are kept. This step processes only the small result of step 1.

The result is a simple random sample without replacement of exactly n rows, which is the sampling design Cochran's formula assumes. If the table has n rows or fewer, the whole table is written.

The sample is written to `output_table` in the same catalog and schema; an existing table with that name is overwritten. The run fails if:
* `output_table` equals `table` (this would overwrite the source table),
* the source table is empty or cannot be read,
* the written table has fewer than n rows (probability below 1e-4; rerun with a different `seed`).

**Reproducibility:** Spark derives the random numbers per partition. The same `seed` therefore reproduces a sample only as long as the table version and its file layout are unchanged. New writes, `OPTIMIZE`, or a different compute configuration produce a different sample. To keep a sample, keep the output table.

The notebook can also be run interactively with a fixed sample size: open `bernoulli_sampling.py` in the workspace and set the `target_size` widget.

---

## Deployment & Execution

Both jobs run on serverless compute: the job definitions specify no cluster, so Databricks uses serverless compute for the notebook tasks. Serverless compute must be enabled in the workspace.

### Prerequisites
Install the Databricks CLI and authenticate with the workspace:
```bash
databricks auth login --host "https://<your-workspace-url>"
```

### 1. Deployment
The bundle has a single target, `dev`, which uses `mode: development`. In this mode, the job names are prefixed with `[dev <user name>]` and the files are deployed to the user's workspace folder.

```bash
# Validate the bundle configuration
databricks bundle validate

# Deploy the bundle to the dev target
databricks bundle deploy
```

### 2. Execution
```bash
# Calculate the sample size only
databricks bundle run cochran_sample_size

# Calculate the sample size and write the sample to output_table
databricks bundle run bernoulli_sample_drawing
```

### 3. Parameters
Default values are defined as `variables` in `databricks.yml`.

| Parameter | Default | Job | Description |
|---|---|---|---|
| `catalog` | `workspace` | both | Catalog of the source table |
| `schema` | `default` | both | Schema of the source table and the output table |
| `table` | `test_population` | both | Source table (population) |
| `error` | `0.05` | both | Margin of error, absolute (0.05 = +/- 5 percentage points) |
| `proportion` | `0.5` | both | Expected proportion, between 0 and 1 |
| `confidence` | `95` | both | Confidence level in percent, between 50 and 100 |
| `output_table` | `test_population_sample` | drawing | Table the sample is written to (overwritten on each run) |
| `seed` | `42` | drawing | Random seed |

Override parameters for a single run:
```bash
databricks bundle run bernoulli_sample_drawing --params table=orders,output_table=orders_sample
```

Change the defaults for a deployment:
```bash
databricks bundle deploy --var="table=orders"
```

---

## Local Development

Requirements:
* Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).
* Java 17 or newer for the Spark integration tests. Without Java, these tests are skipped.

```bash
# Install the development dependencies (PySpark, pytest)
uv sync

# Run all tests
uv run pytest
```

PySpark is a development dependency only; Databricks provides it at runtime. Its version is pinned to the Spark version of the Databricks serverless environment (Spark 4.1). Update the pin in `pyproject.toml` when the serverless environment moves to a new Spark version.

---

## CI/CD Pipeline

The workflow `.github/workflows/deploy_bundle.yml` runs on pull requests to `main` and on pushes to `main`, if at least one of these paths changed:
* `src/**/*.py`, `tests/**/*.py`
* `resources/**/*.yml`, `databricks.yml`
* `pyproject.toml`, `uv.lock`
* `.github/**`

The workflow can also be started manually: **Actions** tab > **Test and Deploy Databricks Bundle** > **Run workflow**. A manual run on `main` runs the tests and deploys; a manual run on another branch only runs the tests.

### Jobs
1. **Run Tests** (pull requests, pushes, and manual runs):
   1. Check out the repository.
   2. Install Java 17 (Temurin) for the local Spark session.
   3. Install uv.
   4. Install the dependencies with `uv sync --locked`. The job fails if `uv.lock` does not match `pyproject.toml`.
   5. Run `uv run pytest`.
2. **Validate and Deploy** (pushes to `main` and manual runs on `main`, after the tests have passed):
   1. Check out the repository.
   2. Install the Databricks CLI. The `databricks/setup-cli` action is pinned to a commit, which also pins the CLI version.
   3. Run `databricks bundle validate`.
   4. Run `databricks bundle deploy` to the `dev` target.

Deployments run one at a time. A deployment that starts while another is running waits for it to finish.

### Authentication
The workspace URL is read from `databricks.yml`. The deployment authenticates with the GitHub Actions secret **`DATABRICKS_TOKEN`**, a personal access token (PAT). The workflow token has read-only access to the repository contents.

### Dependency Updates
* Dependabot checks weekly for updates of the uv dependencies (`uv.lock`) and the GitHub Actions used in the workflows. PySpark receives only patch updates, so that it stays on the Spark version of the serverless environment.
* `.github/workflows/approve-dependabot.yml` approves pull requests opened by Dependabot. The tests run on these pull requests like on any other; the approval does not merge them.

---

## Test Suite

The tests import the functions from `src/sampling.py`, the same code the notebooks run on Databricks.

### Test Configuration (`conftest.py`)
* Starts a local PySpark session (`local[1]`) once per test run. This is a real Spark engine, not a mock, so no Databricks compute is needed.
* Skips the Spark tests when no Java runtime is found.

### Calculation Tests (`test_sampling_logic.py`)
These tests do not use Spark.
* **z-value:** Matches the tabulated values for 90, 95, 98, and 99% confidence; rejects values outside 50-100, including the fraction `0.95`.
* **Cochran sample size:** 385 rows for an infinite population, 278 rows for 1,000 rows, never more rows than the population, 0 for an empty table, and errors for out-of-range margin of error, proportion, confidence, or population.
* **Oversampled fraction:** The expected row count lies four standard deviations above the target size; the fraction keeps its precision for tables with billions of rows and is capped at 1.0.
* **Table names:** Each part is quoted with backticks.

### Spark Integration Tests (`test_spark_integration.py`)
These tests run `draw_sample` on a DataFrame of 1,000 rows.
* **Exact size:** A target of 100 rows returns exactly 100 rows with the source columns.
* **Distinct source rows:** The sample contains no duplicate IDs and only IDs from the source.
* **Seed:** The same seed returns the same sample; different seeds return different samples.
* **Small tables:** A target size not smaller than the table returns all rows.
