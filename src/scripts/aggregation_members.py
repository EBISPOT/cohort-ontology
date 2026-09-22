#!/usr/bin/env python3
"""
Write the members of the cohort aggregations as a ROBOT template,
src/templates/aggregation_members.tsv, which becomes the aggregation_members.owl
component: a hasCohort assertion from each aggregation to each member cohort
that exists in COHO, with the evidence for it (a quote from the source naming
the member, and the source's URL) as annotations on the assertion.

Sources, in src/curation:
  aggregation_members_evidence.tsv  one row per aggregation and member, from a
                                    review of every aggregation's membership on
                                    2026-09-22: the member as the source names
                                    it, its COHO ID where it exists (else "new"),
                                    the source, the quote, whether the quote was
                                    found in the source, and per aggregation an
                                    "include" decision (yes when the members are
                                    cohorts; no when the source lists countries,
                                    sites or institutions instead)
  aggregation_members_curated.tsv   overrides: aggregation_id, member_id, quote,
                                    URL, note. A member_id of "-" with a
                                    member_id column empty removes nothing; a row
                                    whose note starts with "remove" drops that
                                    membership.

Members that do not yet exist in COHO are not asserted; they are listed for the
pass that mints new cohorts, after which re-running this script links them.
Deprecated individuals are skipped, as aggregation or member.

Usage: src/scripts/aggregation_members.py
"""

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "src/curation/aggregation_members_evidence.tsv"
CURATED = ROOT / "src/curation/aggregation_members_curated.tsv"
TEMPLATE = ROOT / "src/templates/aggregation_members.tsv"
EDIT = ROOT / "src/ontology/coho-edit.owl"


def read(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main():
    deprecated = {
        cid.replace("_", ":", 1)
        for cid in re.findall(r"AnnotationAssertion\(owl:deprecated coho:(COHO_\d+) \"true\"", EDIT.read_text(encoding="utf-8"))
    }
    links = {}  # (aggregation, member) -> (quote, url)
    labels = {}
    pending = {}
    for r in read(EVIDENCE):
        labels[r["aggregation_id"]] = r["aggregation_label"]
        if r["include"] != "yes" or not r["member_name"] or r["aggregation_id"] in deprecated or r["member_id"] in deprecated:
            continue
        if r["member_id"].startswith("COHO:"):
            quote, url = (r["quote"], r["source_url"]) if r["quote verified"] == "yes" else ("", "")
            links[(r["aggregation_id"], r["member_id"])] = (quote, url)
        else:
            pending.setdefault(r["aggregation_id"], []).append(r["member_name"])
    for r in read(CURATED):
        key = (r["aggregation_id"], r["member_id"])
        if r["aggregation_id"] in deprecated or r["member_id"] in deprecated:
            continue
        if r["note"].lower().startswith("remove"):
            links.pop(key, None)
        else:
            links[key] = (r["quote"], r["URL"])

    with open(TEMPLATE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["ID", "TYPE", "label", "member cohort", "evidence", "source"])
        w.writerow(["ID", "TYPE", "", "I coho:hasCohort", ">A rdfs:comment", ">A oio:hasDbXref"])
        for (agg, member), (quote, url) in sorted(links.items()):
            w.writerow([agg, "owl:NamedIndividual", labels.get(agg, ""), member, quote, url])
    by_agg = {}
    for agg, _ in links:
        by_agg[agg] = by_agg.get(agg, 0) + 1
    print(f"{len(links)} memberships asserted for {len(by_agg)} aggregations; "
          f"{sum(len(v) for v in pending.values())} members of {len(pending)} aggregations await minting")


if __name__ == "__main__":
    main()
