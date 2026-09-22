#!/usr/bin/env python3
"""
Write the data collection locations of the cohorts as a ROBOT template,
src/templates/locations.tsv, which becomes the locations.owl component: one
has_data_collection_location assertion per cohort and country, with the evidence
for it (a quote from a source that says where participants were recruited, and
the source's URL) as annotations on the assertion.

Sources:
  src/curation/location_evidence.tsv  one row per cohort: the country or countries
                                      COHO asserted, a verdict on them, the right
                                      ones, and the evidence (a review of every
                                      assertion made on 2026-09-22, with whether
                                      the quote was verified in its source)
  src/curation/location_curated.tsv   overrides: ID, countries (dbpedia resource
                                      names, pipe-separated), quote, URL, note.
                                      A row here wins over the review; an empty
                                      countries field removes the cohort's locations.

The review's "correct" list is applied for wrong and incomplete verdicts and the
asserted list is kept for correct and unverified ones. Evidence is attached only
where the quote was verified; otherwise the assertion stands without it.
Deprecated individuals are skipped.

Usage: src/scripts/locations.py
"""

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "src/curation/location_evidence.tsv"
CURATED = ROOT / "src/curation/location_curated.tsv"
TEMPLATE = ROOT / "src/templates/locations.tsv"
GAZ = ROOT / "src/templates/gaz_xrefs.tsv"
EDIT = ROOT / "src/ontology/coho-edit.owl"


def read(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main():
    with open(GAZ, encoding="utf-8") as f:
        known = {r[0].split(":", 1)[1] for r in list(csv.reader(f, delimiter="\t"))[2:]}
    deprecated = {
        cid.replace("_", ":", 1)
        for cid in re.findall(r"AnnotationAssertion\(owl:deprecated coho:(COHO_\d+) \"true\"", EDIT.read_text(encoding="utf-8"))
    }
    rows = {}
    for r in read(REVIEW):
        if r["ID"] in deprecated:
            continue
        if r["verdict"] in ("wrong", "incomplete"):
            countries = r["correct"]
        else:
            countries = r["asserted"]
        quote, url = (r["quote"], r["URL"]) if r["quote verified"] == "yes" else ("", "")
        rows[r["ID"]] = (countries, quote, url)
    for r in read(CURATED):
        if r["ID"] not in deprecated:
            rows[r["ID"]] = (r["countries"], r["quote"], r["URL"])

    unknown = {c for countries, _, _ in rows.values() for c in countries.split("|") if c and c not in known}
    if unknown:
        raise SystemExit(f"countries missing from {GAZ.name}: {sorted(unknown)}")

    with open(TEMPLATE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["ID", "TYPE", "label", "data collection location", "evidence", "source"])
        w.writerow(["ID", "TYPE", "", "I coho:has_data_collection_location SPLIT=|", ">A rdfs:comment", ">A oio:hasDbXref"])
        labels = {r["ID"]: r["label"] for r in read(REVIEW)}
        n = 0
        for cid in sorted(rows):
            countries, quote, url = rows[cid]
            if not countries:
                continue
            value = "|".join(f"dbpedia:{c}" for c in countries.split("|"))
            w.writerow([cid, "owl:NamedIndividual", labels.get(cid, ""), value, quote, url])
            n += 1
    print(f"{n} cohorts located, {sum(1 for c, q, u in rows.values() if c and u)} with evidence")


if __name__ == "__main__":
    main()
