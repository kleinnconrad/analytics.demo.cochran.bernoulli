import pytest
from pyspark.sql.types import StructType, StructField, IntegerType, StringType

from sampling import draw_sample


class TestDrawSample:

    @pytest.fixture(autouse=True)
    def setup_data(self, spark):
        """Creates a mock DataFrame of 1,000 rows for the tests to act on."""
        schema = StructType([
            StructField("id", IntegerType(), True),
            StructField("device_type", StringType(), True)
        ])

        # Generate 1000 dummy rows
        self.population = 1000
        data = [(i, "sensor_a" if i % 2 == 0 else "sensor_b") for i in range(self.population)]
        self.df = spark.createDataFrame(data, schema)

    def sampled_ids(self, target_size, seed):
        return [row.id for row in draw_sample(self.df, target_size, self.population, seed).collect()]

    def test_returns_exact_target_size(self):
        sampled_df = draw_sample(self.df, 100, self.population, seed=42)

        assert sampled_df.count() == 100
        assert sampled_df.columns == self.df.columns

    def test_returns_distinct_rows_of_the_source(self):
        ids = self.sampled_ids(100, seed=42)

        assert len(set(ids)) == len(ids)
        assert all(0 <= i < self.population for i in ids)

    def test_same_seed_gives_same_sample(self):
        assert set(self.sampled_ids(100, seed=7)) == set(self.sampled_ids(100, seed=7))

    def test_different_seeds_give_different_samples(self):
        assert set(self.sampled_ids(100, seed=1)) != set(self.sampled_ids(100, seed=2))

    def test_target_not_smaller_than_population_returns_all_rows(self):
        assert draw_sample(self.df, 5000, self.population, seed=42).count() == self.population

    def test_rejects_non_positive_target(self):
        with pytest.raises(ValueError):
            draw_sample(self.df, 0, self.population, seed=42)
