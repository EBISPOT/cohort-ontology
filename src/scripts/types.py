#!/usr/bin/env python3
"""
Write the evidence for the cohorts' types as the component
src/ontology/components/types.owl: for every quote in
src/curation/type_evidence.tsv, a copy of the term's class assertion in
coho-edit.owl to cohort (COHO:0000000) or cohort aggregation (COHO:0000001),
annotated with the quote (rdfs:comment) and its sources (oboInOwl:hasDbXref:
the paper's PMID, when the document is a paper, and the document's URL). A
quote recorded for a type the term no longer has is left out and counted.

Usage: src/scripts/types.py
"""

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mint_cohorts as M  # noqa: E402
from names import HEADER, evidence  # noqa: E402

TABLE = M.ROOT / "src/curation/type_evidence.tsv"
COMPONENT = M.ROOT / "src/ontology/components/types.owl"
TYPES = {"cohort": "COHO_0000000", "cohort aggregation": "COHO_0000001"}


def main():
    have = set(re.findall(r"^ClassAssertion\(coho:(COHO_000000[01]) coho:(COHO_\d+)\)$", M.EDIT.read_text(encoding="utf-8"), re.M))
    out, gone, terms = [], 0, set()
    with open(TABLE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            c, t = M.local(r["ID"]), TYPES.get(r["type"])
            if (t, c) not in have:
                gone += 1
                continue
            out.append(f'ClassAssertion({evidence(r["quote"], r["PMID"], r["URL"])} coho:{t} coho:{c})')
            terms.add(c)
    out = sorted(set(out))
    header = HEADER.replace("components/names.owl", "components/types.owl")
    lines = [header] + [f"Declaration(NamedIndividual(coho:{c}))" for c in sorted(terms)] + [""] + out + [")\n"]
    COMPONENT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{COMPONENT.relative_to(M.ROOT)}: {len(out)} type assertions with a quote on {len(terms)} terms"
          + (f"; {gone} quotes for a type the term no longer has left out" if gone else ""))


if __name__ == "__main__":
    main()
