"""Sample size calculation and sample drawing shared by the notebooks and the tests.

This file has no "# Databricks notebook source" header, so the bundle uploads it
as a plain workspace file and the notebooks in this folder can import it.
"""
import math
from statistics import NormalDist

from pyspark.sql import functions as F


def z_score(confidence):
    """Two-sided z-score for a confidence level given in percent (e.g. 95 -> 1.96)."""
    confidence = float(confidence)
    if not 50 < confidence < 100:
        raise ValueError(
            f"Confidence must be a percentage between 50 and 100 (exclusive), e.g. 95. Got {confidence}."
        )
    return NormalDist().inv_cdf(0.5 + confidence / 200)


def cochran_sample_size(margin_of_error, proportion, confidence, population=None):
    """Minimum sample size to estimate a proportion within +/- margin_of_error.

    margin_of_error and proportion are absolute values: 0.05 means +/- 5 percentage points.
    population=None assumes an infinite population (no finite population correction).
    """
    z = z_score(confidence)
    if not 0 < margin_of_error < 1:
        raise ValueError(f"Margin of error must be between 0 and 1 (exclusive). Got {margin_of_error}.")
    if not 0 < proportion < 1:
        raise ValueError(f"Proportion must be between 0 and 1 (exclusive). Got {proportion}.")
    if population is not None and population < 0:
        raise ValueError(f"Population must not be negative. Got {population}.")

    n0 = (z**2) * proportion * (1 - proportion) / (margin_of_error**2)
    if population is None:
        return math.ceil(n0)
    if population == 0:
        return 0
    # min() guards against floating point error pushing the result above the population
    return min(math.ceil(n0 / (1 + (n0 - 1) / population)), population)


def oversampled_fraction(target_size, population, sigmas=4.0):
    """Bernoulli fraction whose expected row count lies `sigmas` standard deviations above target_size.

    The row count of a Bernoulli sample with expected count m has a standard deviation
    of at most sqrt(m). Solving m - sigmas * sqrt(m) = target_size for m makes a count
    below target_size a 4-sigma event (probability below 1e-4).
    """
    if target_size <= 0:
        raise ValueError(f"Target sample size must be greater than 0. Got {target_size}.")
    if population <= 0:
        raise ValueError(f"Population must be greater than 0. Got {population}.")
    sqrt_m = (sigmas + math.sqrt(sigmas**2 + 4 * target_size)) / 2
    return min(sqrt_m**2 / population, 1.0)


def draw_sample(df, target_size, population, seed):
    """Simple random sample (without replacement) of exactly min(target_size, population) rows.

    A Bernoulli pass with an oversampled fraction reduces the table to slightly more than
    target_size rows. A random ordering of that subset then keeps exactly target_size rows.
    The result has fewer rows only if the Bernoulli pass falls short (probability below 1e-4).
    """
    if target_size <= 0:
        raise ValueError(f"Target sample size must be greater than 0. Got {target_size}.")
    if target_size >= population:
        return df
    fraction = oversampled_fraction(target_size, population)
    return (
        df.sample(withReplacement=False, fraction=fraction, seed=seed)
        .orderBy(F.rand(seed))
        .limit(target_size)
    )


def qualified_name(catalog, schema, table):
    """Backtick-quoted three-part table name; works for names with hyphens or other special characters."""
    return ".".join(f"`{part.replace('`', '``')}`" for part in (catalog, schema, table))
