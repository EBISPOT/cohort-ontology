#!/usr/bin/env python3
"""
Write the catalogue subset templates from the catalogue records.

Each outside catalogue COHO has worked through has a record in `src/curation`
naming the COHO term every entry resolved to, and the terms it lists form a
subset of the ontology, like the EBI resource subsets: `GEC_subset` for the
Global Exposome Cohort Catalogue (`exposome_catalogue.tsv`) and `IHCC_subset`
for the IHCC Cohort Atlas (`ihcc_atlas.tsv`). This script writes the subsets'
ROBOT templates, `src/templates/GEC.csv` and `IHCC.csv`, in the shape of
`PGS.csv`: one line per live term an entry resolved to. The consortium behind
the atlas (the International Health Cohorts Consortium, recorded in
`ihcc_atlas.tsv` under the id IHCC) is not an atlas entry and is left out.

Usage: catalogue_subsets.py
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mint_cohorts as M  # noqa: E402

SUBSET = "http://www.ebi.ac.uk/coho#{}_subset"
CATALOGUES = [
    ("exposome_catalogue.tsv", "GEC", set()),
    ("ihcc_atlas.tsv", "IHCC", {"IHCC"}),
]


def main():
    T = M.parse(M.EDIT.read_text(encoding="utf-8"))
    for record, name, skip in CATALOGUES:
        terms = {}
        for r in csv.DictReader(open(M.ROOT / "src/curation" / record, newline="", encoding="utf-8"), delimiter="\t"):
            if not r["COHO ID"] or r["catalogue id"] in skip:
                continue
            c = M.local(r["COHO ID"])
            t = T.get(c)
            if not t or not t["types"] or t["dep"]:
                raise SystemExit(f"{record}: {r['COHO ID']} is not a live term")
            terms[r["COHO ID"]] = t["label"]
        out = M.ROOT / "src/templates" / f"{name}.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["ID", "TYPE", "subset", "label"])
            w.writerow(["ID", "TYPE", "AI oboInOwl:inSubset", ""])
            for c in sorted(terms):
                w.writerow([c, "owl:NamedIndividual", SUBSET.format(name), terms[c]])
        print(f"{out.name}: {len(terms)} terms")


if __name__ == "__main__":
    main()
