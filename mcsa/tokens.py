"""Real-tokenizer measurement for the R1 resident ceiling.

Why this module exists: chars/4 is an ESTIMATE and it was wrong. Measured
2026-09-30 on spine.RESIDENT:

    chars/4 estimate      415 tok
    cl100k_base           449 tok   (+8.2%)
    o200k_base            448 tok   (+8.0%)
    p50k_base             488 tok   (+17.6%)   <- worst case

The gate must bound the WORST tokenizer, not the average and not an estimate.
Which tokenizer enforces a ceiling depends on the model serving the prompt, and
that is not knowable here -- so take the maximum over what is available and
record which one won. If no tokenizer is loadable, say so and fall back rather
than quietly pretending the estimate was a measurement.
"""

from __future__ import annotations

import os

# Ordering is irrelevant: we take the max. List is data, not control flow
# (PROGRAMMABLE gate) -- extend it without touching logic.
ENCODINGS: tuple[str, ...] = ("cl100k_base", "o200k_base", "p50k_base")

# The budget is an OWNER-SET value, named here rather than buried in logic so it
# is visible in any diff that changes it (PROGRAMMABLE + the R3 spirit: a claim
# with no stated basis is a claim with no basis).
#
# PROVENANCE: set under explicit delegation on 2026-09-30, after real-tokenizer
# measurement replaced the chars/4 estimate. Measured then: cl100k 543,
# o200k 539, p50k 592. The prior 512 was chosen before any measurement existed
# and was, as it turns out, never load-bearing -- chars/4 under-reported by 18%.
#
# PURPOSE (laya noul 0.7988 that a ceiling is a regression gate, not an absolute):
# R1's teeth are against UNINTENTIONAL GROWTH. Deliberately raising this number
# is legitimate and expected; letting the tier creep past it silently is not.
# If you raise it, raise it here, visibly.
APPROVED_BUDGET = 640

CEILING_ENV = "MCSA_R1_MAX_TOKENS"


def ceiling(default: int = APPROVED_BUDGET) -> int:
    """Precedence: env override > approved budget. An unparseable or absurd
    override RAISES rather than falling back silently -- a typo in the
    environment must not quietly disable the gate."""
    raw = os.environ.get(CEILING_ENV)
    if not raw:
        return default
    try:
        v = int(raw)
    except ValueError:
        raise ValueError(
            f"{CEILING_ENV}={raw!r} is not an integer; refusing to guess a budget. "
            f"Unset it to use the approved budget of {default}."
        ) from None
    if v < 64:
        raise ValueError(f"{CEILING_ENV}={v} is below the minimum viable spine (64)")
    return v


def _enc(name: str):
    """Cached. tiktoken.get_encoding is expensive (parses a ~1.7 MB BPE table)
    and every gate re-measures; without the cache a preflight paid it dozens of
    times. Measured: caching took the suite from >120 s to under 10 s."""
    import tiktoken  # imported lazily: optional dependency, see measure()
    global _CACHE
    if name not in _CACHE:
        _CACHE[name] = tiktoken.get_encoding(name)
    return _CACHE[name]


_CACHE: dict = {}


def available() -> list[str]:
    """Which encodings actually load. A name that needs a download and has none
    is reported absent rather than counted as zero-cost."""
    ok = []
    for n in ENCODINGS:
        try:
            _enc(n)
            ok.append(n)
        except Exception:
            continue
    return ok


def measure(text: str) -> dict:
    """Token count per encoding. Returns the WORST case as the governing number.

    `method` records whether this was a measurement or a fallback, so a gate
    result can never be mistaken for one (R3: measured, never asserted).
    """
    counts: dict[str, int] = {}
    for n in ENCODINGS:
        try:
            counts[n] = len(_enc(n).encode(text))
        except Exception:
            continue
    if not counts:
        return {
            "method": "fallback-chars4",
            "governing": len(text) // 4,
            "worst_encoding": None,
            "counts": {},
            "chars": len(text),
            "note": "no tokenizer loadable; chars/4 is an ESTIMATE, not a measurement",
        }
    worst = max(counts, key=lambda k: counts[k])
    return {
        "method": "measured",
        "governing": counts[worst],
        "worst_encoding": worst,
        "counts": counts,
        "chars": len(text),
        "note": "governing = max over available encodings",
    }
