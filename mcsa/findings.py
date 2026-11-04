"""MCSA findings — measured defects, with the evidence that produced them.

Every figure here was produced by executing the code named, in-session, on
2026-09-30. None is inherited from a manifest or a doc. The point of this module
is that a downstream reader can re-run and disagree.

REPRODUCE: the probes live in POINTS/suite; see PROVENANCE below.

Provenance of the POINTS figures: /var/home/ryan/Documents/projects/POINTS
  suite/{glyph,structure,header,encode_entities,encode_edges,points_tool}.py
"""

from __future__ import annotations

# ── F1: fixed-width frame is a ~90x transport tax ───────────────────────────
FIXED_FRAME = {
    "claim": "A graph carries ~1% of the bytes it transmits.",
    "unit": "8192-byte fixed glyph; 6920 content + 1038 parity (15%)",
    "measurements": [
        # (entities, edges, glyph_bytes, b64_chars, zlib_bytes, json_chars)
        (50, 100, 8192, 10924, 90, 1426),
        (100, 200, 8192, 10924, 89, 2826),
        (255, 400, 8192, 10924, 113, 6072),
    ],
    "derived": [
        "content occupancy ~1.1-1.4%",
        "raw base64 handoff ~2731 tokens per glyph",
        "zlib+base64 handoff ~30 tokens per glyph",
        "a 1-entity graph still costs 8192 bytes",
    ],
    "consequence": "The 1-char handle is the format's headline property, and it "
                   "works only in the case where transport was unnecessary.",
}

# ── F2: silent payload corruption, every integrity flag green ───────────────
SILENT_CORRUPTION = {
    "claim": "50% label loss reported as parity_ok=True, errors_corrected=0.",
    "probe": "255 entities x 12-char labels x 400 edges, pack -> unpack",
    "observed": {
        "parity_ok": True,
        "errors_corrected": 0,
        "parity_verified": True,
        "entities_hdr": 255, "entities_decoded": 255,
        "edges_hdr": 400, "edges_decoded": 400,
        "corrupt_labels": "127 of 255",
        "label_in": "ENTITY_LABEL_128",
        "label_out": "ENTITY_LABEL",
    },
    "root_cause": [
        "structure.py:105-117 LiteralValue.as_bytes emits a 16-bit length",
        "encoder writes the pool into a fixed 6920-byte content region and "
        "truncates on overflow with no error path",
        "header.py:108 _crc16 covers buf[:40] -- the HEADER ONLY",
        "RS(255,223) protects transport bytes; it cannot observe encoder overflow",
    ],
    "class": "verification wired to the wrong subject",
    "fix": "one guard: if written < required: raise  (gate R4 / r_loud_fail)",
}

# ── F3: handle transport defeats itself ─────────────────────────────────────
HANDLE_FRAGILITY = {
    "claim": "chr(0xE000) is same-process only; cross-process costs ~2731 tokens.",
    "mechanism": [
        "points_tool.py:29 _session_store is a process-local dict",
        "points_tool.py:234 _load_session_bytes falls back to a single file",
        "slot is one global name 'main' -- no addressing, no durability",
    ],
    "consequence": "closes gate R5 (handle economy and durability)",
}

# ── F4: self-certification suppressed the search that found F2 ──────────────
SELF_CERTIFICATION = {
    "claim": "A prompt asserting its own zero-delta plateau was live while F2 "
             "was present in the linked implementation.",
    "mechanism": "resident content spends attention and attention budget on "
                 "asserting quality instead of checking it",
    "closes": "gate R6",
}

# ── F5: deliberation.run schema non-determinism at the MCP boundary ─────────
MCP_NONDETERMINISM = {
    "claim": "An identical, schema-valid graph was rejected then accepted on retry.",
    "observed": [
        'error: graph must have \'entities\' array  (x2, valid input)',
        'same payload -> {"verdict":"improve","laps":2,"parity":true}',
    ],
    "consequence": "Verify every deliberation verdict. A first error is not "
                   "evidence of a bad input shape.",
    "logged_as": "G5",
}

# ── F6: density is a design choice, not a property of the subject ───────────
DENSITY_VARIANCE = {
    "claim": "Same author, same repo, opposite density outcomes.",
    "measurements": [
        ("DEPLOYED_MASTER_DEV_SYSTEM_PROMPT.md", 75157, 18789, 0.030, 0.000),
        ("ABSUBEST_FRAMEWORK_v3.1.md", 25944, 6486, 0.027, 0.016),
    ],
    "columns": "file, bytes, ~tokens, 4-gram redundancy, decoration ratio",
    "consequence": "closes gate R7 with a reference, not a guess",
}

# ── F7: laya `score` returns a degenerate result on list-shaped criteria ─────
LAYA_SCORE_DEFECT = {
    "claim": "laya score answered with legend 'item' and probability 1.0 on a "
             "list-shaped criteria rubric -- a malformed result, not a measurement.",
    "occurrences": 2,
    "detail": [
        "call 1: 'pointer_omission_silent_failure' -> score 0.0, legend {'0': 'item'}",
        "call 2: 'removal_cost' -> score 0.0, legend {'0': 'item'}",
        "a second question in the same batched call was silently DROPPED",
    ],
    "contrast": "choice and noul in the SAME batch returned well-formed results "
                "with distinguishable probabilities",
    "reading": "A rubric passed as a list is not being applied as a rubric. The "
               "response is confidently uniform, which is worse than an error: "
               "it looks like a measurement and is not.",
    "protocol": "Treat any laya `score` whose legend is the literal string 'item' "
                "as INVALID and discard it. Do not report it as a number. "
                "Prefer noul/choice, or re-issue the score with a dict rubric.",
    "logged_as": "G6",
}

# ── F8: laya silently DROPS questions from a batched call ───────────────────
LAYA_DROPPED_QUESTIONS = {
    "claim": "A batched laya call returned fewer answers than questions asked, "
             "with no error and no indication of which were dropped.",
    "occurrences": 3,
    "detail": [
        "call 1 (5 asked): dereference_mode, spine_size, ref_file_format, "
        "selection_key, pointer_omission_silent_failure -> 4 returned "
        "(pointer_omission_silent_failure returned malformed; see F7)",
        "call 2 (2 asked): mechanism, what_would_be_the_trap -> 1 returned "
        "(what_would_be_the_trap absent from the response entirely)",
        "call 3 (3 asked): floor_choice, mechanism, what_would_be_the_trap "
        "-> only mechanism returned; floor_choice and the trap were both absent",
    ],
    "contrast": "questions that DID return were well-formed, with real "
                "differing probabilities -- the defect is omission, not noise",
    "reading": "A dropped question is the most dangerous failure shape here: the "
               "call SUCCEEDED. An unwary reader sees a valid response with a "
               "confidence figure and concludes the decision was made, when the "
               "question was never answered.",
    "protocol": "Count the keys in `answers` against the keys you sent. If they "
                "differ, the decision is NOT settled for the missing keys. Treat "
                "a missing answer as unresolved, never as agreement. This is why "
                "the D1 budget was answered from a measurement instead of from "
                "the engine's silence on floor_choice.",
    "logged_as": "G7",
}

ALL_FINDINGS = {
    "F1": FIXED_FRAME,
    "F2": SILENT_CORRUPTION,
    "F3": HANDLE_FRAGILITY,
    "F4": SELF_CERTIFICATION,
    "F5": MCP_NONDETERMINISM,
    "F6": DENSITY_VARIANCE,
    "F7": LAYA_SCORE_DEFECT,
    "F8": LAYA_DROPPED_QUESTIONS,
}


def render(name: str | None = None) -> str:
    if name is None:
        return "\n\n".join(
            f"### {k}\n{v['claim']}\n"
            + "\n".join(f"- {kk}: {vv}" for kk, vv in v.items() if kk != "claim")
            for k, v in ALL_FINDINGS.items()
        )
    f = ALL_FINDINGS[name]
    return f"### {name}\n{f['claim']}\n" + "\n".join(
        f"- {k}: {v}" for k, v in f.items() if k != "claim")
