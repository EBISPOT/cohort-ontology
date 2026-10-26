#!/usr/bin/env python3
"""
Write the cohorts' textual definitions as a ROBOT template,
src/templates/definitions.tsv, which becomes the definitions.owl component: an
IAO:0000115 definition per cohort, with its source (IAO:0000119: the paper's
PMID, or the URL of a cohort's own site) and, as dcterms:contributor, the
agents that wrote and checked it. The definitions were drafted by an AI model
from sources it retrieved and checked by another against those sources; the
contributor annotations say so on each one.

Each definition also carries the verbatim quotes that support it (rdfs:comment), each with the paper's PMID, when the
document is a paper, and the document's URL (oboInOwl:hasDbXref): one copy of the definition axiom per quote, so each
quote stays with its own source. A cohort without quotes keeps one row. Quotes are attached only while the definition
reads as it did when they were found (their "definition md5"); those of a definition changed since are printed and
left off until the definition is sourced again.

Sources, in src/curation:
  definitions_evidence.tsv  one row per cohort: the drafted definition, its source,
                            the supporting quote and whether the quote was found in
                            the source (a review of 2026-09-22)
  definition_quotes.tsv     the quotes supporting each definition: ID, supports, quote, PMID, URL,
                            found by (the model or person), definition md5
  definitions_curated.tsv   overrides: ID, definition, source, note, drafted by, checked by. A
                            row here wins; an empty definition means the cohort is
                            to have none. The optional "drafted by" column names the
                            model or person that wrote the definition; where it is
                            empty, the definition was written by the checking model
                            alone. The optional "checked by" column names the model
                            or person that checked it against its sources; where
                            it is empty, nobody has.

Every individual in coho-edit.owl that is not deprecated is expected to have a
definition; those without are printed.

Usage: src/scripts/definitions.py
"""

import csv
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "src/curation/definitions_evidence.tsv"
CURATED = ROOT / "src/curation/definitions_curated.tsv"
QUOTES = ROOT / "src/curation/definition_quotes.tsv"
TEMPLATE = ROOT / "src/templates/definitions.tsv"
EDIT = ROOT / "src/ontology/coho-edit.owl"

DRAFTED_BY = "GPT-6 (OpenAI Codex), 2026-09"
CHECKED_BY = "Claude Fable 5.1 (Anthropic), 2026-09"
WRITTEN_BY = CHECKED_BY


def read(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main():
    edit = EDIT.read_text(encoding="utf-8")
    deprecated = {
        cid.replace("_", ":", 1)
        for cid in re.findall(r"AnnotationAssertion\(owl:deprecated coho:(COHO_\d+) \"true\"", edit)
    }
    individuals = set(re.findall(r"Declaration\(NamedIndividual\(coho:(COHO_\d+)\)", edit))
    labels = {
        cid.replace("_", ":", 1): label
        for cid, label in re.findall(r'AnnotationAssertion\(rdfs:label coho:(COHO_\d+) "((?:[^"\\]|\\.)*)"', edit)
        if cid in individuals
        if cid.replace("_", ":", 1) not in deprecated
    }
    rows = {}
    for r in read(EVIDENCE):
        if r["ID"] in deprecated:
            continue
        if r["definition"].strip():
            rows[r["ID"]] = (r["definition"].strip(), r["source PMID"] or r["source URL"], DRAFTED_BY, CHECKED_BY)
    for r in read(CURATED):
        if r["ID"] in deprecated:
            continue
        if r["definition"].strip():
            rows[r["ID"]] = (r["definition"].strip(), r["source"], (r.get("drafted by") or "").strip() or WRITTEN_BY, (r.get("checked by") or "").strip())
        else:
            rows.pop(r["ID"], None)

    quotes, stale = {}, set()
    for r in read(QUOTES):
        if r["ID"] not in rows:
            continue
        if r["definition md5"] != hashlib.md5(rows[r["ID"]][0].encode()).hexdigest()[:12]:
            stale.add(r["ID"])
            continue
        quotes.setdefault(r["ID"], []).append((r["quote"], r["PMID"], r["URL"]))

    with open(TEMPLATE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["ID", "TYPE", "label", "definition", "definition source", "drafted by", "checked by", "quote", "quote PMID", "quote URL"])
        w.writerow(["ID", "TYPE", "", "A IAO:0000115", ">A IAO:0000119 SPLIT=|", ">A dcterms:contributor", ">A dcterms:contributor",
                    ">A rdfs:comment", ">A oio:hasDbXref", ">A oio:hasDbXref"])
        for cid in sorted(rows):
            definition, source, drafted, checked = rows[cid]
            for quote, pmid, url in quotes.get(cid) or [("", "", "")]:
                w.writerow([cid, "owl:NamedIndividual", labels.get(cid, ""), definition, source, drafted, checked, quote, pmid, url])
    print(f"{sum(len(v) for v in quotes.values())} supporting quotes on {len(quotes)} definitions"
          + (f"; quotes left off {len(stale)} definitions changed since they were found: {', '.join(sorted(stale))}" if stale else ""))
    missing = sorted(set(labels) - set(rows))
    print(f"{len(rows)} of {len(labels)} cohorts defined; without: {', '.join(f'{c} {labels[c]}' for c in missing) or 'none'}")


if __name__ == "__main__":
    main()
