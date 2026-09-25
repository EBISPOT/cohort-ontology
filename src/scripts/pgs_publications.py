#!/usr/bin/env python3
"""
Write the publications the PGS Catalog records for each COHO term it has a cohort id for.

pgs_examples.py gives a term one example; this writes the whole record, so that
the papers a term's curation needs can be fetched in one go and read: for every
live term with a cohort id in the Catalog (placed by the catalog review, or matched
by name for the cohorts COHO had before it, see pgs_examples.catalog_ids), every
publication the Catalog links to any of its ids, one line per term, cohort id and
paper. A paper is a PGS Catalog
publication (a score's, where the cohort is among the score's training samples
or the samples its variant associations came from; or the publication that
evaluated a score on a sample set naming the cohort) or the source GWAS itself
whose samples name the cohort, which is the paper most likely to describe it.
The `roles` column says which, for every score involved (the first twenty, and
how many more).

Columns: COHO ID, label, curation status (uncurated for a placeholder), PGS
subset (yes for a term of the subset), PGS cohort id, placed by (how the id was
tied to the term: the review, or the name),  PGS cohort name (as the Catalog gives it), PMID, DOI, title (from
Europe PMC, cached in example_studies_titles.tsv), PGP id (the Catalog's
publication id, empty for a source GWAS), roles.

The Catalog is read from the cache pgs_examples.py keeps (--cache, --refresh as
there). Output: src/curation/pgs_catalog_publications.tsv, which the bulk fetch
of the curation pipeline reads.

Usage: pgs_publications.py [--cache DIR] [--refresh]
"""
import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import example_studies as E  # noqa: E402
import mint_cohorts as M  # noqa: E402
import pgs_examples as P  # noqa: E402

OUT = M.CUR / "pgs_catalog_publications.tsv"
HEADER = ["COHO ID", "label", "curation status", "PGS subset", "PGS cohort id", "placed by", "PGS cohort name", "PMID", "DOI", "title", "PGP id", "roles"]


def doi(d):
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", d or "")


def roles_text(roles, keep=20):
    return "; ".join(roles[:keep]) + (f"; and {len(roles) - keep} more" if len(roles) > keep else "")


def uses(rec):
    """(PMID, DOI, PGP id, role) for each paper a Catalog record ties the cohort to."""
    pub, pgs = rec["pub"], rec["pgs"]
    if rec["kind"] == "samples_training":
        yield pub.get("PMID"), doi(pub.get("doi")), pub.get("id"), f"training samples of {pgs}"
    elif rec["kind"] == "evaluation":
        yield pub.get("PMID"), doi(pub.get("doi")), pub.get("id"), f"evaluation of {pgs} on {rec['pss']} ({rec['ppm']})"
    else:
        gwas = rec.get("gcst") or "a GWAS"
        yield pub.get("PMID"), doi(pub.get("doi")), pub.get("id"), f"development of {pgs} from the samples of {gwas}"
        if rec.get("source_pmid") or rec.get("source_doi"):
            yield rec.get("source_pmid"), doi(rec.get("source_doi")), "", f"source GWAS {gwas} of {pgs}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache/coho/pgs_catalog")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    T, live, uncurated, subset = P.terms()
    cands = P.candidates(P.catalog(a.cache, a.refresh))
    ids = P.catalog_ids(cands, T, live)
    subset = set(subset)

    papers = {}  # (term, cohort id, PMID or DOI) -> record
    for c in sorted(live):
        for cid in ids.get(c, ()):
            for _, rec in cands.get(cid, ()):
                for pmid, doi, pgp, role in uses(rec):
                    if not (pmid or doi):
                        continue
                    key = (c, cid, str(pmid) if pmid else doi)
                    r = papers.setdefault(key, dict(name=rec["name_full"], pmid=str(pmid) if pmid else "", doi=doi or "", pgp=set(), roles=[]))
                    r["doi"] = r["doi"] or (doi or "")
                    if pgp:
                        r["pgp"].add(pgp)
                    if role not in r["roles"]:
                        r["roles"].append(role)

    titles = E.paper_titles({r["pmid"] for r in papers.values() if r["pmid"]})
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(HEADER)
        for (c, cid, key), r in sorted(papers.items(), key=lambda kv: (kv[0][0], kv[0][1], int(kv[1]["pmid"] or 0), kv[0][2])):
            w.writerow([M.curie(c), T[c]["label"], "uncurated" if c in uncurated else "curated", "yes" if c in subset else "", cid, P.PLACED_BY.get((c, cid), ""), r["name"],
                        f"PMID:{r['pmid']}" if r["pmid"] else "", r["doi"], titles.get(r["pmid"], ""), "|".join(sorted(r["pgp"])), roles_text(r["roles"])])

    done = {c for c, _, _ in papers}
    pmids = {r["pmid"] for r in papers.values() if r["pmid"]}
    print(f"{len(papers)} lines for {len(done)} terms ({len(done & uncurated)} placeholders, {len(done - uncurated)} curated; {len(done & subset)} in the PGS subset): "
          f"{len(pmids)} distinct PMIDs, {sum(1 for r in papers.values() if not r['pmid'])} papers with a DOI only; "
          f"written to {OUT.relative_to(M.ROOT)}")


if __name__ == "__main__":
    main()
