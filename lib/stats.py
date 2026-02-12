"""
Statistical Analysis Module - Arsenal Module
Copy-paste ready: Pure Python statistical functions

Note: The following functions are currently unused but reserved for future
analysis dashboard features (comparative run analysis, confidence intervals):
- chi_square_test() - Compare distributions between runs
- wilson_confidence_interval() - Proportion confidence intervals
- bootstrap_consistency() - Decision consistency estimation
- cohens_h() - Effect size measurement
"""

import math
from typing import List, Dict, Any, Tuple, Optional
import random


def normal_cdf(z: float) -> float:
    """Standard normal cumulative distribution function"""
    t = 1 / (1 + 0.2316419 * abs(z))
    d = 0.3989423 * math.exp(-z * z / 2)
    p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))
    return 1 - p if z > 0 else p


def chi_square_to_p_value(chi_square: float, df: int) -> float:
    """Convert chi-square statistic to p-value"""
    # Approximation for degrees of freedom 1-10
    if df == 1:
        z = math.sqrt(chi_square)
        return 2 * (1 - normal_cdf(z))

    if df == 2:
        return math.exp(-chi_square / 2)

    # General approximation using Wilson-Hilferty transformation
    k = df
    x = chi_square
    z = (pow(x / k, 1/3) - (1 - 2/(9*k))) / math.sqrt(2/(9*k))
    return 1 - normal_cdf(z)


def chi_square_test(observed1: List[int], observed2: List[int]) -> Optional[Dict[str, Any]]:
    """
    Chi-square test for comparing two categorical distributions

    Args:
        observed1: Observed frequencies for group 1 [group1Count, group2Count, undecidedCount]
        observed2: Observed frequencies for group 2 [group1Count, group2Count, undecidedCount]

    Returns:
        { chiSquare, pValue, degreesOfFreedom, significant }
    """
    n1 = sum(observed1)
    n2 = sum(observed2)

    if n1 == 0 or n2 == 0:
        return None

    chi_square = 0
    k = len(observed1)

    for i in range(k):
        expected1 = (observed1[i] + observed2[i]) * n1 / (n1 + n2)
        expected2 = (observed1[i] + observed2[i]) * n2 / (n1 + n2)

        if expected1 > 0:
            chi_square += pow(observed1[i] - expected1, 2) / expected1
        if expected2 > 0:
            chi_square += pow(observed2[i] - expected2, 2) / expected2

    # Validation: Check for small expected frequencies
    min_expected = min([(observed1[i] + observed2[i]) * n1 / (n1 + n2) for i in range(k)] +
                       [(observed1[i] + observed2[i]) * n2 / (n1 + n2) for i in range(k)])
    
    warning = None
    if min_expected < 5:
        warning = "Sample size too small for reliable chi-square (expected freq < 5)"

    df = k - 1
    p_value = chi_square_to_p_value(chi_square, df)

    return {
        "chiSquare": round(chi_square, 4),
        "pValue": round(p_value, 4),
        "degreesOfFreedom": df,
        "significant": p_value < 0.05,
        "warning": warning
    }


def get_z_score(confidence: float) -> float:
    """Get z-score for confidence level"""
    confidence_map = {
        0.90: 1.645,
        0.95: 1.96,
        0.99: 2.576,
        0.999: 3.291
    }
    return confidence_map.get(confidence, 1.96)


def wilson_confidence_interval(successes: int, total: int, confidence: float = 0.95) -> Dict[str, float]:
    """
    Wilson confidence interval for a proportion
    More accurate than normal approximation, especially for small samples

    Args:
        successes: Number of successes
        total: Total trials
        confidence: Confidence level (default 0.95 for 95% CI)

    Returns:
        { proportion, lower, upper, marginOfError }
    """
    if total == 0:
        return {"proportion": 0, "lower": 0, "upper": 0, "marginOfError": 0}

    assert total > 0, "wilson_confidence_interval requires total > 0"
    p = successes / total
    z = get_z_score(confidence)
    z2 = z * z

    denominator = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) / total + z2 / (4 * total * total))) / denominator

    return {
        "proportion": round(p, 4),
        "lower": round(max(0, center - margin), 4),
        "upper": round(min(1, center + margin), 4),
        "marginOfError": round(margin * 2, 4)
    }


def bootstrap_consistency(decisions: List[Any], bootstrap_samples: int = 1000, confidence: float = 0.95, seed: Optional[int] = None) -> Dict[str, float]:
    """
    Bootstrap confidence interval for consistency
    Estimates variability in decision distribution through resampling

    Args:
        decisions: Array of decision values (1, 2, or None for undecided)
        bootstrap_samples: Number of bootstrap samples (default 1000)
        confidence: Confidence level (default 0.95)
        seed: Optional seed for reproducibility

    Returns:
        { meanConsistency, lower, upper }
    """
    if len(decisions) == 0:
        return {"meanConsistency": 0, "lower": 0, "upper": 0}

    rng = random
    if seed is not None:
        rng = random.Random(seed)

    consistency_scores = []

    for _ in range(bootstrap_samples):
        # Resample with replacement (faster method)
        sample = rng.choices(decisions, k=len(decisions))

        # Calculate consistency (proportion of most common decision)
        counts = {}
        for d in sample:
            counts[d] = counts.get(d, 0) + 1

        max_count = max(counts.values())
        consistency = max_count / len(sample)
        consistency_scores.append(consistency)

    # Sort and find percentiles
    consistency_scores.sort()
    alpha = 1 - confidence
    lower_index = int(bootstrap_samples * alpha / 2)
    upper_index = int(bootstrap_samples * (1 - alpha / 2))

    mean = sum(consistency_scores) / len(consistency_scores)

    return {
        "meanConsistency": round(mean, 4),
        "lower": round(consistency_scores[lower_index], 4),
        "upper": round(consistency_scores[upper_index], 4)
    }


def cohens_h(p1: float, p2: float) -> Dict[str, Any]:
    """
    Cohen's h effect size for comparing two proportions
    Measures the magnitude of difference between two proportions

    Args:
        p1: Proportion 1
        p2: Proportion 2

    Returns:
        { h, interpretation }
    """
    # Arcsine transformation
    phi1 = 2 * math.asin(math.sqrt(p1))
    phi2 = 2 * math.asin(math.sqrt(p2))
    h = abs(phi1 - phi2)

    interpretation = "negligible"
    if h >= 0.8:
        interpretation = "large"
    elif h >= 0.5:
        interpretation = "medium"
    elif h >= 0.2:
        interpretation = "small"

    return {
        "h": round(h, 4),
        "interpretation": interpretation
    }
