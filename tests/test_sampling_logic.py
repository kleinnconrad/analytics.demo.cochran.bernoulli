import math

import pytest

from sampling import cochran_sample_size, oversampled_fraction, qualified_name, z_score


class TestZScore:
    @pytest.mark.parametrize(
        "confidence, expected",
        [(90, 1.645), (95, 1.960), (98, 2.326), (99, 2.576)],
    )
    def test_common_confidence_levels(self, confidence, expected):
        assert z_score(confidence) == pytest.approx(expected, abs=1e-3)

    def test_accepts_widget_strings(self):
        # Widget values arrive as strings
        assert z_score("95") == z_score(95)

    @pytest.mark.parametrize("confidence", [0.95, 50, 100, 101, -95])
    def test_rejects_values_outside_50_to_100_percent(self, confidence):
        # 0.95 is the typical mistake of passing a fraction instead of a percentage
        with pytest.raises(ValueError):
            z_score(confidence)


class TestCochranCalculator:
    def test_infinite_population(self):
        # 95% confidence, 50% proportion, 5% margin of error: textbook baseline of 385
        assert cochran_sample_size(0.05, 0.5, 95) == 385

    def test_finite_population_correction(self):
        # Adjusting the 385 base requirement for a small 1,000 row table
        assert cochran_sample_size(0.05, 0.5, 95, population=1000) == 278

    def test_large_population_approaches_infinite_case(self):
        assert cochran_sample_size(0.05, 0.5, 95, population=10**9) == 385

    @pytest.mark.parametrize("population", [1, 2, 10, 100, 385, 386])
    def test_never_exceeds_population(self, population):
        assert cochran_sample_size(0.05, 0.5, 95, population=population) <= population

    def test_empty_table_returns_zero(self):
        assert cochran_sample_size(0.05, 0.5, 95, population=0) == 0

    @pytest.mark.parametrize(
        "error, proportion",
        [(0, 0.5), (1, 0.5), (-0.05, 0.5), (0.05, 0), (0.05, 1), (0.05, 1.5), (0.05, -0.5)],
    )
    def test_rejects_invalid_error_or_proportion(self, error, proportion):
        with pytest.raises(ValueError):
            cochran_sample_size(error, proportion, 95, population=1000)

    def test_rejects_invalid_confidence(self):
        with pytest.raises(ValueError):
            cochran_sample_size(0.05, 0.5, 0.95, population=1000)

    def test_rejects_negative_population(self):
        with pytest.raises(ValueError):
            cochran_sample_size(0.05, 0.5, 95, population=-1)


class TestOversampledFraction:
    @pytest.mark.parametrize("target_size", [1, 5, 100, 385, 10_000])
    def test_target_lies_four_sigma_below_expected_count(self, target_size):
        population = 10**8
        expected_count = oversampled_fraction(target_size, population) * population
        assert expected_count - 4 * math.sqrt(expected_count) == pytest.approx(target_size)

    def test_keeps_precision_for_very_large_tables(self):
        # 385 rows out of 10 billion: the fraction must not round to zero
        fraction = oversampled_fraction(385, 10**10)
        assert fraction > 0
        assert fraction * 10**10 > 385

    def test_caps_at_one(self):
        assert oversampled_fraction(900, 1000) == 1.0

    @pytest.mark.parametrize("target_size, population", [(0, 1000), (-5, 1000), (100, 0)])
    def test_rejects_invalid_inputs(self, target_size, population):
        with pytest.raises(ValueError):
            oversampled_fraction(target_size, population)


class TestQualifiedName:
    def test_quotes_each_part(self):
        assert qualified_name("workspace", "default", "my-table") == "`workspace`.`default`.`my-table`"

    def test_escapes_backticks(self):
        assert qualified_name("c", "s", "a`b") == "`c`.`s`.`a``b`"
