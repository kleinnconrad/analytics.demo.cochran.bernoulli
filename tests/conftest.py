import os
import shutil
import sys

import pytest
from pyspark.sql import SparkSession

# Spark workers must use the interpreter that runs the tests. The PySpark default
# "python3" can point to another interpreter, or to nothing on Windows.
os.environ.setdefault("PYSPARK_PYTHON", sys.executable)


@pytest.fixture(scope="session")
def spark():
    """
    Creates a local Spark session for testing purposes.
    The session is created once for the entire test suite.
    Tests that use it are skipped when no Java runtime is installed.
    """
    if not os.environ.get("JAVA_HOME") and shutil.which("java") is None:
        pytest.skip("Spark tests need Java 17 or newer (no java on PATH and JAVA_HOME not set)")

    spark_session = (
        SparkSession.builder
        .master("local[1]")
        .appName("DatabricksSamplingTests")
        .config("spark.sql.shuffle.partitions", "1")
        # No web UI or console progress bars on the test runner
        .config("spark.ui.enabled", "false")
        .config("spark.ui.showConsoleProgress", "false")
        # Bind to loopback so the session starts regardless of the runner's hostname setup
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.driver.host", "127.0.0.1")
        .getOrCreate()
    )

    yield spark_session

    # Teardown
    spark_session.stop()
