#!/usr/bin/env python3
"""
Pick the example studies of each cohort and write them as a ROBOT template
(src/templates/example_studies.tsv), which puts each on the cohort as
IAO:0000112 "example of usage", with the study's PMID (the first, if it has
several) as an xref on the axiom and a title as dcterms:title on the axiom: the
paper's, from Europe PMC, or the EGA study's own where it has no paper.

A cohort in a subset (EGA, GWAS, MetaboLight, PRIDE) needs an example from that
subset's resource: an EGA study (EGAS...), a GWAS Catalog study (GCST...), a
MetaboLights study (MTBLS...) or a PRIDE project (PXD...). The
subset-example-violation check in src/sparql enforces this, so a cohort in two
subsets has two examples. Otherwise a cohort has one example.

Sources, in src/curation:
  ega_studies.tsv               the EGA studies a human reviewed for cohort mentions
                                (accession, title, description, PMIDs, availability,
                                verified cohort matches, verification status)
  ega_study_cohorts.tsv         one row per verified EGA study -> cohort match
  gwas_catalog_cohorts.tsv.gz   GWAS Catalog PUBMEDID / STUDY_ACCESSION / COHORT,
                                one cohort per line

A study is matched to a cohort when its cohort string equals the cohort's label
or one of its synonyms, ignoring case and punctuation. Acronyms are not unique to
one cohort, and the EGA matches began as text hits, so an EGA match made on a
synonym alone counts as supported only if the study's title, description or
abstract also contains the cohort's label. The GWAS Catalog's cohort acronyms are
curated against the same list COHO was built from, so they are taken as they are.

The example is a supported EGA study if there is one, otherwise a GWAS Catalog
study. Within each, a released and undeprecated study is preferred, then the one
naming the fewest cohorts (it says most about this one), then one with a PMID,
then the lowest accession.

Cohorts left without an example are printed, with the unsupported EGA match as a
candidate where there is one, and so are the subset members that lack an example
from their subset's resource, with the studies the tables here suggest. Examples
a curator has settled go in src/curation/example_studies_curated.tsv (ID, example
study, PMID, note, quote, URL, title), which takes precedence over everything here: a
cohort with curated lines gets exactly those examples and no automatic one, so a
cohort that needs a second example has both written there. A line with a PMID
but no accession gives the paper as the example; a line with neither means the
cohort is to have none, which is how a wrong choice made here is rejected. The
quote and URL, where given, are the evidence that the study used the cohort;
the title, where given, is used when the study has no paper (a MetaboLights study
or PRIDE project without a PMID, say).

Paper titles are kept in src/curation/example_studies_titles.tsv, so only PMIDs
not yet in it are looked up.

The evidence that the study used the cohort, a quote and the URL it came from,
is in src/curation/example_studies_evidence.tsv (one row per cohort, from the
reviews of 2026-09-22) and goes on the annotation as rdfs:comment and
oboInOwl:hasDbXref where the quote was verified in its source.

Usage: src/scripts/example_studies.py
"""

import csv
import gzip
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EDIT = ROOT / "src/ontology/coho-edit.owl"
TEMPLATE = ROOT / "src/templates/example_studies.tsv"
EGA_STUDIES = ROOT / "src/curation/ega_studies.tsv"
EGA_COHORTS = ROOT / "src/curation/ega_study_cohorts.tsv"
GWAS = ROOT / "src/curation/gwas_catalog_cohorts.tsv.gz"
CURATED = ROOT / "src/curation/example_studies_curated.tsv"
EVIDENCE = ROOT / "src/curation/example_studies_evidence.tsv"
TITLES = ROOT / "src/curation/example_studies_titles.tsv"
EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
SUBSETS = ["EGA", "GWAS", "MetaboLight", "PRIDE"]

VERIFIED = ("confirmed correct", "corrected by reviewer")


def norm(s):
    return re.sub(r"\W+", "", str(s)).lower()


def accession_key(acc):
    return int(re.sub(r"\D", "", acc) or 0)


RESOURCES = {"EGA": r"EGAS\d+", "GWAS": r"GCST\d+", "MetaboLight": r"MTBLS\d+", "PRIDE": r"PXD\d+"}


def resource(acc):
    """The subset whose resource an example study comes from, or '' for a paper."""
    return next((s for s, pat in RESOURCES.items() if re.fullmatch(pat, acc or "")), "")


def rows(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f, delimiter="\t")


def paper_titles(pmids):
    """PMID -> title, from the cache in TITLES, topped up from Europe PMC."""
    titles = {}
    if TITLES.exists():
        with open(TITLES, encoding="utf-8") as f:
            titles = {r["PMID"]: r["title"] for r in csv.DictReader(f, delimiter="\t")}
    todo = sorted(set(pmids) - set(titles), key=int)
    for i in range(0, len(todo), 50):
        query = "src:med AND (" + " OR ".join(f"ext_id:{p}" for p in todo[i : i + 50]) + ")"
        url = EUROPEPMC + "?" + urllib.parse.urlencode({"query": query, "format": "json", "resultType": "lite", "pageSize": 100})
        with urllib.request.urlopen(url, timeout=60) as resp:
            for r in json.load(resp)["resultList"]["result"]:
                if r.get("pmid") in todo and r.get("title"):
                    titles[r["pmid"]] = html.unescape(re.sub(r"<[^>]+>", "", r["title"])).strip()
    with open(TITLES, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["PMID", "title"])
        w.writerows(sorted(titles.items(), key=lambda kv: int(kv[0])))
    return titles


def evidence():
    """cohort -> (quote, URL, accession, PMID) for the study the review settled on, where the quote was verified."""
    if not EVIDENCE.exists():
        return {}
    with open(EVIDENCE, encoding="utf-8") as f:
        return {
            r["ID"]: (r["quote"], r["URL"], r["example study"], r["PMID"])
            for r in csv.DictReader(f, delimiter="\t")
            if r["quote verified"] == "yes" and r["quote"] and r["URL"]
        }


def cohorts():
    txt = EDIT.read_text(encoding="utf-8")
    individuals = set(re.findall(r"Declaration\(NamedIndividual\(coho:(COHO_\d+)\)", txt))
    individuals -= set(re.findall(r"AnnotationAssertion\(owl:deprecated coho:(COHO_\d+) \"true\"", txt))
    labels, names = {}, defaultdict(set)
    for prop, cid, value in re.findall(
        r'AnnotationAssertion\((?:Annotation\([^)]*\) )?(rdfs:label|oboInOwl:has\w+Synonym) coho:(COHO_\d+) "((?:[^"\\]|\\.)*)"',
        txt,
    ):
        if cid in individuals:
            names[cid].add(value)
            if prop == "rdfs:label":
                labels[cid] = value
    return labels, names


def main():
    labels, names = cohorts()
    index = defaultdict(set)
    for cid, ns in names.items():
        for n in ns:
            index[norm(n)].add(cid)

    # study -> pmids, text and availability, from the full verified table
    ega_pmids, ega_text, ega_title, ega_withdrawn = {}, {}, {}, set()
    for r in rows(EGA_STUDIES):
        acc = r["accession_id"]
        ega_pmids[acc] = re.findall(r"\d+", str(r["pubmed_ids"] or ""))
        ega_title[acc] = str(r["title"] or "").strip()
        ega_text[acc] = norm(" ".join(str(r[k] or "") for k in ("title", "description", "abstract")))
        if str(r["is_released"]).upper() != "TRUE" or str(r["is_deprecated"]).upper() == "TRUE":
            ega_withdrawn.add(acc)

    ega_matches = defaultdict(set)  # study -> cohort strings
    for r in rows(EGA_COHORTS):
        if str(r["verification_status"]).lower().startswith(VERIFIED):
            ega_matches[r["accession_id"]].add(r["cohort_match"])

    gwas_matches, gwas_pmid = defaultdict(set), {}
    for r in rows(GWAS):
        acc = r["STUDY_ACCESSION"]
        gwas_matches[acc].add(r["COHORT"])
        if r["PUBMEDID"]:
            gwas_pmid[acc] = [r["PUBMEDID"]]

    def candidates(matches, pmids, supported=lambda acc, s, cid: True):
        good, weak = defaultdict(list), defaultdict(list)
        for acc, strings in matches.items():
            for s in strings:
                for cid in index.get(norm(s), ()):
                    rank = (acc in ega_withdrawn, len(strings), not pmids.get(acc), accession_key(acc), acc)
                    (good if supported(acc, s, cid) else weak)[cid].append(rank)
        return good, weak

    def ega_supported(acc, s, cid):
        label = norm(labels[cid])
        return norm(s) == label or label in ega_text.get(acc, "")

    ega, ega_weak = candidates(ega_matches, ega_pmids, ega_supported)
    gwas, _ = candidates(gwas_matches, gwas_pmid)

    curated = defaultdict(list)  # cohort -> [(accession, pmid, quote, URL, title)], one line per example
    if CURATED.exists():
        with open(CURATED, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                curated[r["ID"].replace(":", "_")].append(
                    (r["example study"].strip(), (r["PMID"] or "").strip().removeprefix("PMID:"),
                     (r.get("quote") or "").strip(), (r.get("URL") or "").strip(), (r.get("title") or "").strip())
                )

    chosen = defaultdict(list)  # cohort -> [(accession, pmid, source, quote, URL, title)]
    for cid in sorted(labels):
        if cid in curated:
            for acc, pmid, quote, url, title in curated[cid]:
                if acc or pmid:
                    chosen[cid].append((acc, pmid, "curated", quote, url, title))
            continue
        for source, cands, pmids in (("EGA", ega, ega_pmids), ("GWAS Catalog", gwas, gwas_pmid)):
            if cands.get(cid):
                acc = min(cands[cid])[-1]
                chosen[cid].append((acc, (pmids.get(acc) or [""])[0], source, "", "", ""))
                break

    examples = [e for es in chosen.values() for e in es]
    titles = paper_titles(pmid for _, pmid, *_ in examples if pmid)
    untitled = sorted({pmid for _, pmid, *_ in examples if pmid and pmid not in titles})
    if untitled:
        print("no title found for PMID " + ", ".join(untitled), file=sys.stderr)

    done = set(chosen)
    ev = evidence()
    with open(TEMPLATE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["ID", "TYPE", "label", "example study", "PMID", "title", "evidence", "evidence source", "source"])
        w.writerow(["ID", "TYPE", "", "A IAO:0000112", ">A oboInOwl:hasDbXref", ">A dcterms:title", ">A rdfs:comment", ">A oboInOwl:hasDbXref", ""])
        for cid, es in chosen.items():
            curie = cid.replace("_", ":")
            for acc, pmid, source, quote, url, given_title in es:
                title = titles.get(pmid) or given_title or ega_title.get(acc, "")
                if not (quote and url) and curie in ev and ev[curie][2] == acc and ev[curie][3] == (f"PMID:{pmid}" if pmid else ""):
                    quote, url = ev[curie][:2]  # evidence is for this very study, not an earlier choice
                w.writerow([curie, "owl:NamedIndividual", labels[cid], acc or f"PMID:{pmid}", f"PMID:{pmid}" if pmid else "", title, quote, url, source])

    subsets = defaultdict(list)
    for s in SUBSETS:
        with open(ROOT / f"src/templates/{s}.csv", encoding="utf-8") as f:
            for r in list(csv.reader(f))[2:]:
                subsets[r[0].replace(":", "_")].append(s)

    missing = [c for c in sorted(labels) if c not in done]
    print(f"{len(done)} of {len(labels)} cohorts given an example study; {len(missing)} without:")
    for cid in missing:
        cand = min(ega_weak[cid])[-1] if ega_weak.get(cid) else ""
        note = f"  candidate {cand} ({ega_title.get(cand, '')[:60]})" if cand else ""
        print(f"  {cid.replace('_', ':')} {labels[cid]} [{'|'.join(subsets[cid])}]{note}")

    # subset members without an example from their subset's resource
    suggest = {"EGA": lambda c: [r[-1] for r in sorted(ega.get(c, []) + ega_weak.get(c, []))], "GWAS": lambda c: [r[-1] for r in sorted(gwas.get(c, []))]}
    gaps = [(s, c) for c in sorted(labels) for s in subsets[c] if s not in {resource(e[0]) for e in chosen.get(c, [])}]
    print(f"{len(gaps)} subset memberships without an example from the subset's resource:")
    for s, cid in gaps:
        cands = list(dict.fromkeys(suggest[s](cid)))[:3] if s in suggest else []
        note = f"  candidates {', '.join(cands)}" if cands else ""
        print(f"  {s} {cid.replace('_', ':')} {labels[cid]}{note}")


if __name__ == "__main__":
    main()
