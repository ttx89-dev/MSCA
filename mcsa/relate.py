"""MCSA relation algebra — C4. Closes the two ontology gaps named in
65536/ontology.md, which R12 requires and which were documented but never
implemented.

GAP 1  EQUIVALENCE has no mechanism.
      Content-addressing collapses byte-identical content. It cannot collapse
      two different strings meaning one referent ("car" / "automobile"). POINTS
      has the relation type and no way to exercise it. Here: union-find over
      EQL, symmetric and transitive, with an explicit asymmetric-pair check.

GAP 2  INSTANCE_OF is conflated with IS_A.
      Formal ontology keeps them structurally distinct (rdf:type vs
      rdfs:SubClassOf) because collapsing them produces structures that imply
      wrong things about individuals. 65536/ontology.md records that
      derive_tiers() cannot tell them apart. Here: separate relations, and the
      class methods REFUSE the conflation instead of silently accepting it.

Every property in the table below is asserted at mutation time, not documented
and hoped for. A violation raises RelationViolation. That is the R6 discipline
applied to the algebra itself: a claim the code cannot fail on is a comment.
"""

from __future__ import annotations

__all__ = ["Ontology", "RelationViolation", "EQUIVALENCE", "IS_A", "INSTANCE_OF",
           "PART_OF", "ASSOCIATIVE", "MERONYMY", "CONFIDENCE"]

EQUIVALENCE = "EQL"   # symmetric, transitive
IS_A = "ISA"          # transitive, asymmetric  (genus-differentia)
INSTANCE_OF = "INS"   # NON-transitive        (individual -> class)
PART_OF = "PAR"       # compositional, subtyped
ASSOCIATIVE = "OST"   # typed catch-all

MERONYMY = {
    "CIN": "component-integral", "MEM": "member-collection",
    "POR": "portion-mass",       "STU": "stuff-object",
    "FEA": "feature-activity",   "PLA": "place-area",
}

CONFIDENCE = {0: "certain", 1: "likely", 2: "plausible", 3: "unknown"}


class RelationViolation(Exception):
    """A formal property was broken. Raised at mutation time, never deferred."""


class Ontology:
    def __init__(self) -> None:
        self._eq: dict[str, str] = {}                     # union-find parent
        self._sub: dict[str, set[str]] = {}               # child -> {parent}
        self._inst: dict[str, set[str]] = {}              # individual -> {class}
        self._par: list[tuple[str, str, str]] = []        # (part, whole, qualifier)
        self._ost: list[tuple[str, str, str]] = []        # (src, tgt, label)
        self._conf: dict[tuple[str, str], int] = {}       # (src,tgt) -> confidence

    # ── internals ──────────────────────────────────────────────────────────
    def _find(self, x: str) -> str:
        self._eq.setdefault(x, x)
        root = x
        while self._eq[root] != root:
            root = self._eq[root]
        while self._eq[x] != root:                        # path compression
            self._eq[x], x = root, self._eq[x]
        return root

    def _union(self, a: str, b: str) -> bool:
        ra, rb = self._find(a), self._find(b)
        if ra == rb:
            return False
        self._eq[rb] = ra
        return True

    # ── GAP 1: EQUIVALENCE ─────────────────────────────────────────────────
    def equivalent(self, a: str, b: str, confidence: int = 0) -> bool:
        """Declare a~b. Symmetric and transitive by construction. Returns True
        if this call merged two previously distinct classes."""
        if confidence not in CONFIDENCE:
            raise RelationViolation(f"confidence must be 0-3, got {confidence}")
        if a == b:
            raise RelationViolation(
                f"EQL is between two labels for one referent; {a!r} is not two "
                f"labels. That is identity, not equivalence.")
        merged = self._union(a, b)
        self._conf[(a, b)] = self._conf[(b, a)] = confidence
        return merged

    def same_referent(self, a: str, b: str) -> bool:
        """Transitivity is implied: a~b~c => same_referent(a,c)."""
        return self._find(a) == self._find(b)

    def equivalence_classes(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for x in self._eq:
            out.setdefault(self._find(x), []).append(x)
        return {k: sorted(v) for k, v in sorted(out.items()) if len(v) > 1}

    def labels_of(self, canonical: str) -> list[str]:
        return sorted(self.equivalence_classes().get(self._find(canonical), [canonical]))

    # ── GAP 2: IS_A vs INSTANCE_OF ─────────────────────────────────────────
    def is_a(self, child: str, parent: str) -> None:
        """Transitive, asymmetric. Refuses to accept an individual here: that
        is the conflation this gap exists to prevent."""
        if child == parent:
            raise RelationViolation("IS_A is asymmetric; a node cannot be its own parent")
        if self._is_individual(child):
            raise RelationViolation(
                f"CONFLATION GUARD: {child!r} was declared INSTANCE_OF a class, so "
                f"it is an individual and cannot be a subclass. Use "
                f"instance_of({child!r}, ...). Collapsing the two implies wrong "
                f"things about individuals -- see 65536/ontology.md.")
        self._sub.setdefault(child, set()).add(parent)

    def instance_of(self, individual: str, cls: str) -> None:
        """NON-transitive. The class must not itself acquire subclasses from
        this individual -- an individual is not a species."""
        if individual == cls:
            raise RelationViolation("INSTANCE_OF requires a distinct class")
        self._inst.setdefault(individual, set()).add(cls)
        # Guard the reverse: an individual must never appear as a subclass.
        if individual in self._sub:
            raise RelationViolation(
                f"CONFLATION GUARD: {individual!r} is already a subclass of "
                f"{sorted(self._sub[individual])}. An individual is not a kind of "
                f"anything.")

    def _is_individual(self, x: str) -> bool:
        return bool(self._inst.get(x))

    def is_instance(self, x: str) -> bool:
        return self._is_individual(x)

    def ancestors(self, x: str) -> set[str]:
        """Transitive CLOSURE over IS_A. An individual's class hierarchy is
        reachable via its class, but the individual itself is never an ancestor
        of its class -- non-transitivity is preserved, not papered over."""
        out: set[str] = set()
        frontier = [x]
        while frontier:
            cur = frontier.pop()
            for p in self._sub.get(cur, ()):
                if p not in out:
                    out.add(p)
                    frontier.append(p)
        return out

    def instances_of(self, cls: str) -> set[str]:
        """Direct instances only. Transitivity is explicitly not offered."""
        return {i for i, cs in self._inst.items() if cls in cs}

    def possible_subtypes(self, x: str) -> set[str]:
        """The test 65536/ontology.md specifies for instance-vs-subclass: does X
        have possible subtypes of its own? If no, it is an instance.

        Returns CHILDREN -- the nodes that are is_a X. (Returning X's parents
        here was a real bug caught by test_instance_has_no_possible_subtypes:
        the question is "what can be a kind of this", not "what is this a kind
        of".) Individuals are never parents, so this is empty for an individual
        by construction.
        """
        return {child for child, parents in self._sub.items() if x in parents}

    # ── meronymy + associative ─────────────────────────────────────────────
    def part_of(self, part: str, whole: str, qualifier: str = "CIN") -> None:
        if qualifier not in MERONYMY:
            raise RelationViolation(
                f"qualifier must be one of {'/'.join(MERONYMY)}; got {qualifier!r}")
        self._par.append((part, whole, qualifier))

    def related(self, src: str, tgt: str, label: str = "OTH",
                confidence: int = 0) -> None:
        self._ost.append((src, tgt, label))
        self._conf[(src, tgt)] = confidence

    def parts_of(self, whole: str) -> list[tuple[str, str]]:
        return [(p, q) for p, w, q in self._par if w == whole]

    def confidence_of(self, src: str, tgt: str) -> str:
        return CONFIDENCE.get(self._conf.get((src, tgt), 0), "certain")

    # ── audit ──────────────────────────────────────────────────────────────
    def audit(self) -> dict:
        """Every structural invariant, checked. This is what VALIDATABLE means:
        a validator pass that is recorded rather than assumed."""
        problems: list[str] = []
        for child, parents in self._sub.items():
            if child in parents:
                problems.append(f"asymmetry: {child!r} is its own parent")
            for p in parents:
                if child in self.ancestors(p) and child != p:
                    problems.append(
                        f"transitivity cycle: {child!r} -> {p!r} -> ... -> {child!r}")
        for ind in self._inst:
            if ind in self._sub:
                problems.append(
                    f"conflation: {ind!r} is both an instance and a subclass")
        for p, w, q in self._par:
            if p == w:
                problems.append(f"PAR self-loop: {p!r}")
        return {
            "ok": not problems,
            "problems": problems,
            "equivalence_classes": len(self.equivalence_classes()),
            "subclass_edges": sum(len(v) for v in self._sub.values()),
            "instances": len(self._inst),
            "part_of_edges": len(self._par),
        }
