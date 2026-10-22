#!/usr/bin/env python3
"""
Find the catalogue record that uses each of a cohort's names for which no
document gave a quote (not in src/curation/name_evidence.tsv), and write them
to src/curation/name_sources.tsv (ID, name, URL, note): many names are a
catalogue's own code or name for the cohort and appear in no paper. The record
is the evidence, so names.py puts its URL on the name as oboInOwl:hasDbXref,
without a quote. In order:
  - the term's entry in the Global Exposome Cohort Catalogue or the IHCC Cohort
    Atlas that gives the name (exposome_catalogue.tsv, ihcc_atlas.tsv);
  - the PGS Catalog cohort whose id, name or other names give it
    (pgs_catalog_cohorts.csv), as its REST record;
  - a GWAS Catalog study that tags its sample with it
    (gwas_catalog_cohorts.tsv.gz), the term's own example study when it is one.
A variant of a name one of these uses (capitals, punctuation, a leading "The") is sourced by the same record, with a
note saying how the catalogue writes it. A name none of these use is left out and counted.

Usage: src/scripts/name_sources.py
"""

import csv
import gzip
import re
import sys
import urllib.parse
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mint_cohorts as M  # noqa: E402
from names import NAME  # noqa: E402

CUR = M.ROOT / "src/curation"
OUT = CUR / "name_sources.tsv"


def rows(path, delimiter="\t"):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def main():
    names = defaultdict(set)
    for line in M.EDIT.read_text(encoding="utf-8").splitlines():
        m = NAME.match(line)
        if m:
            names[M.curie(m.group(3))].add(M.unesc(m.group(4)))
    quoted = {(r["ID"], r["name"]) for r in rows(CUR / "name_evidence.tsv")}
    entries = defaultdict(list)  # term -> [(names the entry gives, URL, catalogue)]
    for f, label in (("exposome_catalogue.tsv", "Global Exposome Cohort Catalogue"), ("ihcc_atlas.tsv", "IHCC Cohort Atlas")):
        for r in rows(CUR / f):
            url = r["xref"] or next(iter(re.findall(r"\((https?://[^)\s]+)\)", r["note"])), "")
            if r["COHO ID"].startswith("COHO:") and url:
                entries[r["COHO ID"]].append(({r["catalogue id"], r["name"]}, url, label))
    pgs = {}
    for r in rows(CUR / "pgs_catalog_cohorts.csv", ","):
        for n in [r["Cohort ID"], r["Cohort Name"]] + (r["Previous/other/additional names"] or "").split("|"):
            if n.strip():
                pgs.setdefault(n.strip(), r["Cohort ID"])
    gwas = defaultdict(set)
    with gzip.open(CUR / "gwas_catalog_cohorts.tsv.gz", "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            gwas[r["COHORT"].strip()].add(r["STUDY_ACCESSION"])
    examples = defaultdict(set)
    for r in rows(M.ROOT / "src/templates/example_studies.tsv")[1:]:
        examples[r["ID"]].add(r["example study"])
    def vnorm(x):
        return re.sub(r"^the ", "", re.sub(r"[\W_]+", " ", x.lower()).strip())
    pgs_v = {vnorm(k): k for k in pgs}
    gwas_v = {vnorm(k): k for k in gwas}
    out, left = [], 0
    for c in sorted(names):
        for n in sorted(names[c]):
            if (c, n) in quoted:
                continue
            hit = next(((url, f"the {label} entry for the term gives this name") for given, url, label in entries[c] if n in given), None)
            if not hit and n in pgs:
                hit = (f"https://www.pgscatalog.org/rest/cohort/{urllib.parse.quote(pgs[n])}",
                       f"the PGS Catalog cohort {pgs[n]} gives this name")
            if not hit and n in gwas:
                gcst = sorted(gwas[n] & examples[c]) or sorted(gwas[n])
                hit = (f"https://www.ebi.ac.uk/gwas/studies/{gcst[0]}", f"GWAS Catalog study {gcst[0]} tags its sample with this name")
            if not hit:
                v = vnorm(n)
                for given, url, label in entries[c]:
                    g = next((x for x in given if vnorm(x) == v), None)
                    if g:
                        hit = (url, f'the catalogue writes it "{g}": the {label} entry for the term'); break
                if not hit and v in pgs_v:
                    k = pgs_v[v]
                    hit = (f"https://www.pgscatalog.org/rest/cohort/{urllib.parse.quote(pgs[k])}", f'the catalogue writes it "{k}": the PGS Catalog cohort {pgs[k]}')
                if not hit and v in gwas_v:
                    k = gwas_v[v]
                    gcst = sorted(gwas[k] & examples[c]) or sorted(gwas[k])
                    hit = (f"https://www.ebi.ac.uk/gwas/studies/{gcst[0]}", f'the catalogue writes it "{k}": GWAS Catalog study {gcst[0]} tags its sample with it')
            if hit:
                out.append([c, n, hit[0], hit[1]])
            else:
                left += 1
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["ID", "name", "URL", "note"])
        w.writerows(out)
    print(f"{OUT.relative_to(M.ROOT)}: {len(out)} names sourced to a catalogue record; {left} names with neither a quote nor a catalogue record")


if __name__ == "__main__":
    main()
