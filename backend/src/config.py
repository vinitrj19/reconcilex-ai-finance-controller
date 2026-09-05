"""
Unified deterministic configuration (M1/M2/M3).

Single source of truth for the monetary/date parameters used by exact
matching (M1), deterministic reconciliation (M2), and candidate generation
(M3). M4's scoring configuration (acceptance_threshold, minimum_margin,
feature weights) is intentionally NOT here - it is owned by M4's own
locked, versioned config file (config/m4_thresholds.json) per spec section
9 ("M4 owns ... locked versioned configuration"). Mixing the two would let
a change to M2 tolerances silently move M4's threshold, which the spec
forbids.

Values below come directly from the product spec ("Financial Rules") and
architecture review - they are not tuned against individual DEV event IDs.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ReconciliationConfig:
    # --- Financial rules (spec section 6) ---
    fee_rate_min: Decimal = Decimal("0.015")   # 1.5%
    fee_rate_max: Decimal = Decimal("0.030")   # 3.0%
    gst_rate: Decimal = Decimal("0.18")        # 18% of the fee

    # --- Monetary tolerance for "exact" comparisons ---
    # Absorbs Decimal rounding noise (records are quantized to 0.01),
    # not a business fee/tax allowance.
    monetary_tolerance: Decimal = Decimal("0.01")

    # --- M1 exact-match date tolerance ---
    # A same-identity settlement is still expected to land close to the
    # payment date under normal processing; large lags are evidence
    # (RULE_M2_* late-settlement flags), not automatic rejection.
    date_tolerance_days: int = 5

    # --- M2 duplicate detection window ---
    duplicate_window_seconds: int = 900  # 15 minutes

    # --- M2/M3 fallback candidate date window ---
    candidate_date_window_days: int = 7
