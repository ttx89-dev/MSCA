# MSCA — Requirements for a Maximum-Semantic-Capacity Agent System Prompt

> **Status:** DRAFT spec. Additive artifact. Replaces nothing.
> **Scope:** This document specifies *what an agent system prompt must satisfy* to
> maximise semantic capacity. It does not modify, supersede, or restructure any
> existing prompt or manual.
> **Evidence base:** measured behaviour of `POINTS/suite` (encoder/decoder round-trip
> probes), `points-encoding`, and 4-gram density
> analysis of the currently deployed prompts.
>
> **Status note (2026-11-05, evaluation pass):** the evidence base cites
> sources by name. `ABSUBEST_FRAMEWORK_v3.1.md` resolves in the workspace
> (`projects/ABSUBEST/`); `DEPLOYED_MASTER_DEV_SYSTEM_PROMPT.md` is cited
> from the original drafting environment and is present neither in the
> workspace nor in this repository's history — these cited names describe
> sources consulted, not files shipped with this repository, per the draft
> scope above.

---

## 0. Non-goals — read before implementing

| Non-goal | Reason |
|---|---|
| Replacing `ABSUBEST_FRAMEWORK_v3.1.md` or any deployed prompt | Out of scope by instruction. MSCA is an addendum, never an overwrite. |
| Reimplementing the POINTS ontology | The 5 relation types + epistemic fields are sound. See `65536/ontology.md`. |
| Building a new glyph alphabet | Alphabet size is not the binding constraint. See §2. |
| Depending on a specific model or vendor | All requirements are model-agnostic. |

---

## 1. The governing metric

A system prompt is not measured by length, alphabet size, or glyph count. It is
measured by:

```
                reachable_information
  capacity  =  ─────────────────────────
                 permanently_resident_tokens
```

**Definitions.**

- *Permanently resident* — tokens injected into context on **every** request,
  unconditionally, that cannot be evicted under memory pressure.
- *Reachable* — bytes/records retrievable on demand via a handle the model can
  emit, within a bounded number of tool round-trips.
- *Capacity* — the ratio above. Maximising it means **pushing information out of
  the resident set and keeping only the key that decodes it.**

A prompt with 20k resident tokens describing a framework has low capacity if
that framework is only needed for 5% of tasks. A prompt with 400 resident tokens
of codebook that can reach 400 MB of task material has high capacity.

> **Corollary (R6).** Any content whose *only* function is to assert the prompt's
> own quality has negative capacity: it is resident, and it suppresses the
> search that would find real defects.

---

## 2. Why alphabet size is not the lever

The proposed design lever "65536 symbols × max one-char semantic capacity"
conflates two independent quantities:

| Quantity | Bound | Status |
|---|---|---|
| bits per symbol | 16 bits @ 65536 symbols; 20.1 bits @ full Unicode (1,114,112 cp) | Self-imposed ceiling. Not physical. |
| semantic bits per symbol | `bits × P(decoder holds the codebook)` | **This is the binding constraint.** |

A 16-bit index into a codebook that has been evicted from context is 16 bits of
noise. The codebook's *residency* converts bits-per-symbol into meaning.
Alphabet construction is therefore an **optimisation downstream of codebook
residency**, not a prerequisite for it.

`65536/65536-Glyph.ttf` and `65536/experiments/glyph_protocol.py` are the correct
instinct aimed at the wrong layer. They remain useful — for wire-format
compactness once a codebook is resident — but they cannot by themselves raise
semantic capacity.

---

## 3. Layer model

Three layers, each independently replaceable. Independence is a testable property
(R8).

```
  L1  ONTOLOGY     5 relation types · meronymy subtypes · associative labels
                   · polarity · confidence · facets · salience · reification
                   ── SEMANTIC LAYER. KEEP. sound and load-bearing.
                          │
  L2  ENCODING     bit-packed edges · label encoding · frame layout
                   ── REPLACE. current form is a density tax (§4.1)
                          │
  L3  TRANSPORT    handle resolution · durability · process boundary
                   ── REPLACE. current form defeats the only thing L1 enables.
```

---

## 4. Evidence — measured defects this spec must prevent

All figures from direct execution of `POINTS/suite/{glyph,structure,header,encode_*}.py`.

### 4.1 Fixed-width frame is a 90× transport tax

| entities / edges | glyph bytes | b64 chars | **zlib bytes** | entropy carried |
|---|---|---|---|---|
| 50 / 100 | 8192 | 10924 | **90** | ~1.1% |
| 100 / 200 | 8192 | 10924 | **89** | ~1.1% |
| 255 / 400 | 8192 | 10924 | **113** | ~1.4% |

A 100-entity/200-edge graph carries ~90 bytes of entropy and ships 8192 bytes:
98.9% padding, plus 1038 bytes (15%) of Reed-Solomon parity computed over zeros.
A single-entity graph also costs 8192 bytes.

### 4.2 Silent payload corruption with all integrity flags green

255 entities × 12-char labels × 400 edges:

```
parity_ok = True    errors_corrected = 0    parity_verified = True
entities hdr/dec = 255 / 255       edges hdr/dec = 400 / 400
CORRUPT LABELS   = 127 of 255
   in : ENTITY_LABEL_128
   out: ENTITY_LABEL
```

**Root cause.** `LiteralValue.as_bytes()` (`structure.py:105-117`) emits a 16-bit
length; the encoder writes the pool into a fixed 6920-byte content region and
silently truncates on overflow. The 42-byte header CRC
(`header.py:108`, `_crc16` over `buf[:40]`) checksums *only the header*. RS(255,223)
protects transport bytes and cannot observe encoder-side overflow.

**Consequence.** Integrity verification is a green light wired to the wrong thing.

### 4.3 Handle transport defeats itself

`points_tool.encode_points` returns `chr(0xE000)`, resolved via a process-local
`_session_store` dict (`points_tool.py:29`, `_load_session_bytes`). Cross-process
cost: 10924 base64 chars ≈ 2731 tokens. Slot is a single global name `"main"`
with no addressing. Non-durable.

The one-token handoff — the format's headline property — works only in the single
case where transport was unnecessary.

### 4.4 Deployed-prompt density variance

Same author, opposite outcomes. Confirms density is a design choice, not a
property of the subject matter.

| Prompt | bytes | ~tokens | 4-gram redundancy | decoration |
|---|---|---|---|---|
| `DEPLOYED_MASTER_DEV_SYSTEM_PROMPT.md` | 75 157 | 18 789 | **3.0%** | 0.0% |
| `ABSUBEST_FRAMEWORK_v3.1.md` | 25 944 | 6 486 | 2.7% | 1.6% |

The deployed ABSUBEST system prompt merges ≥2 unrelated systems, repeats a single
`IDENTITY := {…}` block 8×, declares "zero-delta plateau" 3×, and embeds a
self-certification asserting `Enhancement Delta: Zero [plateau confirmed]`.
That assertion is falsified by §4.2.

---

## 5. Requirements

Priority: **P0** blocks deployment · **P1** required for capacity claim ·
**P2** quality improvement.

---

### R1 — Resident-set ceiling · P0

The permanently-resident tier SHALL NOT exceed the approved budget, measured with
the **worst available real tokenizer** — never a chars/4 estimate. Budget is
config (`MSCA_R1_MAX_TOKENS` > `tokens.APPROVED_BUDGET`, currently **640**).
Measured 2026-09-30: **592** (p50k_base; cl100k 543, o200k 539). The prior
512 was chosen before any measurement existed; chars/4 under-reported by 18%.

**Acceptance.** `python -m msca.gates`; `tokens.measure()` must return
`method="measured"`, and `governing <= ceiling()`. All task-dependent content SHALL be reachable by handle.

> Rationale: capacity is inversely proportional to resident tokens (§1). This is
> the single largest available reduction and it costs no capability once R5 holds.

**Acceptance.** `python -m msca.gates` reports `R1 resident ceiling PASS` with a
real encoder named in `measured`. The gate is a regression gate against the
approved budget; raising it deliberately is legitimate, drifting past it is not.

---

### R2 — Codebook residency invariant · P0

The decode key SHALL be resident under all eviction policies and SHALL be assigned
the highest retention priority in the context. No load, task, or pressure event
may evict the codebook while any handle remains resolvable.

> The codebook is the only content whose removal destroys the value of everything
> else. It is therefore the highest-priority resident item by construction.

**Acceptance.** Eviction-priority config places the codebook tier at priority 0
(evict-last). Assert: under simulated memory pressure with N handles outstanding,
P(codebook resident) = 1.0.

---

### R3 — Reachability must be measured, never asserted · P0

`capacity` (§1) SHALL be computed by an executable check and recorded at deploy
time. No claim of capacity may appear in a prompt or doc without a corresponding
measurement artifact and its command.

> Directly encodes the §4.4 failure: a prompt that asserts its own δ→0 while the
> linked implementation silently corrupts 127/255 records.

**Acceptance.** A deploy script emits `{reachable_bytes, resident_tokens,
capacity, measured_at, commit}` to a machine-readable log. Deployment fails if
`capacity` is below the configured floor.

---

### R4 — Encoder loud-fail · P0

The encoder SHALL raise on any condition where the emitted payload would not
round-trip exactly. **Silent truncation is forbidden.**

> §4.2 is the single most damaging defect found: 50% label loss reported as
> `parity_ok=True, errors_corrected=0`.

**Acceptance.** Fuzz: for `entities ∈ [1,1000] × edges ∈ [1,4000] ×
label_len ∈ {1,8,32,128}`, assert `(round_trip == exact) OR (exception raised)`.
Zero cases of silent divergence. This is a one-line guard
(`if written < required: raise`) and it is P0.

---

### R5 — Handle economy and durability · P1

A handle SHALL be ≤ **12 characters**, SHALL be content-addressed, and SHALL
resolve identically across process boundaries, sessions, and restarts.

> §4.3: the current 1-char handle is same-process only; cross-process costs
> ~2731 tokens. Both failure modes must be closed by the same property.

**Acceptance.** Encode in process A → terminate A → resolve in a fresh process
B → exact round-trip, handle length ≤ 12.

---

### R6 — No self-certification in the resident tier · P0

The resident tier SHALL NOT contain: optimality claims, plateau/completion
declarations, "cannot be improved" assertions, verification certificates, or
reproductions of its own header. These are negative-capacity (R1 corollary).

> A prompt that declares its own optimality has removed the only mechanism that
> could have found the defects. §4.2 was found *despite* such a declaration.

**Acceptance.** Lint rejects these patterns (case-insensitive) in resident-tier
content: `delta → 0`, `zero-delta`, `plateau confirmed`, `cannot be improved`,
`optimal`, `verified complete`, `PREMIUM CONFIRMED`, `no enhancement vectors
remain`. A *pointer* to external evidence is permitted; the claim itself is not.

---

### R7 — Redundancy and decoration gate · P1

Resident-tier content SHALL satisfy 4-gram redundancy ≤ **5%** and box-drawing
decoration ratio ≤ **0.5%**.

**Acceptance.** The density tool (4-gram counter + box-drawing class count, both
over the raw file) reports both figures; deploy fails above either threshold.
Reference: the dense prompt measures 3.0% / 0.0%.

---

### R8 — Layer separability · P1

L1 ontology, L2 encoding, and L3 transport SHALL be replaceable independently:
swapping or disabling any one SHALL NOT require changes to the others.

> §3. The ontology is sound and expensive to re-derive. The container is
> disposable. Coupling them means every container fix re-opens the ontology.

**Acceptance.** Swap L3 transport (in-memory ↔ filesystem) and assert zero
changes to L1/L2 sources. Replace L2 frame layout and assert L1 untouched.

---

### R9 — Additive, non-destructive composition · P0

An MSCA artifact SHALL be addable to an existing agent manual **without
modifying, deleting, reordering, or shadowing any existing content**. The
artifact SHALL declare its insertion point and SHALL be idempotent on re-apply.

> This is the governing constraint of the present deliverable. It is also a
> general safety property: a semantic-capacity layer must never be able to
> destroy the manual it augments.

**Acceptance.** Apply the addendum to a copy of the target manual. Assert:
(a) every pre-existing byte present and unmodified; (b) addendum present exactly
once; (c) re-apply is a no-op; (d) no identifier, rule, or verb defined by the
addendum collides with one already defined in the host manual.

---

### R10 — Variable-length container · P1

The encoded container SHALL be sized by payload, not fixed at 8192 bytes. Padding
SHALL NOT be present in the transmitted form.

> §4.1: 98.9% of the transmitted glyph is padding and zero-valued parity.

**Acceptance.** `len(encode(g)) ≈ len(payload_bytes)` for graphs spanning
3 orders of magnitude of size. No fixed floor. Measured via the §4.1 harness.

---

### R11 — Round-trip provability · P1

Every behavioural claim in the resident tier or its documentation SHALL be
expressible as an executable test. A claim with no test is a decoration and is
governed by R6.

**Acceptance.** CI enumerates resident-tier claims → tests; unbacked claims fail
the build.

---

### R12 — Ontology gap closure · P2

The L1 ontology SHALL close the two gaps already identified in
`65536/ontology.md`:

1. **EQUIVALENCE has no mechanism.** Content-addressing collapses byte-identical
   content; it cannot collapse two different strings with one referent. Requires
   a synonym/UF-collapse path.
2. **INSTANCE_OF is conflated with IS_A** in `derive_tiers()`. Formal ontology
   keeps them structurally distinct (`rdf:type` vs `rdfs:subClassOf`); collapsing
   them yields structures that imply wrong things about individuals.

**Acceptance.** Unit tests distinguishing the two cases, including the negative
case: *France* is instance-of *country*; *island nation* is subclass-of *country*.

---

## 6. Traceability

| Requirement | Prevents | Evidence |
|---|---|---|
| R1 | capacity dilution | §1, §4.4 |
| R2 | codebook eviction → total capacity loss | §2 |
| R3 | unfalsifiable self-claims | §4.4 |
| R4 | silent 50% payload loss | §4.2 |
| R5 | 2731-token handoff; non-durable handle | §4.3 |
| R6 | certification suppressing defect search | §4.2, §4.4 |
| R7 | redundancy/decoration drift | §4.4 |
| R8 | container fixes re-opening the ontology | §3 |
| R9 | destructive prompt edits | present instruction |
| R10 | 90× transport tax | §4.1 |
| R11 | decorative claims | §4.4 |
| R12 | semantic loss in L1 | `65536/ontology.md` |

---

## 7. Open decisions — require an owner's call, not an engineer guess

These are **choices**, not derivations. Each has defensible answers on both sides;
the method does not settle them. They must be answered by whoever owns the agent.

| # | Decision | Options | Consequence of getting it wrong |
|---|---|---|---|
| D1 | Resident budget | **ANSWERED 2026-09-30**: measured 592, budget set to 640, ceiling made config | Was the risk; now a regression gate with recorded provenance |
| D2 | Handle namespace | flat `⟨hhhh⟩` vs typed `⟨G:hhhh⟩` | Flat is shorter; typed is self-documenting and fails better under corruption |
| D3 | Codebook language | English mnemonics vs opaque symbols | Mnemonics are more robust to recall failure; symbols are denser. Genuinely contested |
| D4 | Hybrid depth | codebook-only vs codebook + prose restatement of P0 rules | Prose raises recall reliability but costs exactly the budget R1 protects |
| D5 | Who owns R3's floor | which `capacity` value blocks deployment | Too high → blocks deployment indefinitely; too low → admits the §4.2 class of defect |

> **Recorded per method, not resolved by it.** D3 in particular: dense symbol
> vocabularies fail *silently and plausibly* on recall failure, which is
> strictly worse than a legible failure. If MSCA is deployed, D3 should be
> decided by observing recall on a real task distribution, not by argument.

---

## 8. Definition of done

MSCA is deployable when:

1. R1, R2, R4, R6, R9 pass (§5).
2. A measurement artifact exists satisfying R3, with a recorded command.
3. R5, R7, R8, R10, R11 pass.
4. R12 is either closed or explicitly deferred with an owner.
5. D1–D5 are answered by the owner and recorded here.

---

*Requirements only. Implementation is a separate deliverable. This document
replaces nothing.*
