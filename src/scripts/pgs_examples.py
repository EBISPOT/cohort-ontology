#!/usr/bin/env python3
"""
Give the terms of the PGS subset an example from the PGS Catalog.

The PGS Catalog records a cohort wherever a score used it: among the samples a
score was developed from (its training samples, or the samples of the GWAS its
variant associations came from), or among the samples of a sample set a score
was evaluated on. This script reads the Catalog's REST API (every score,
performance metric and sample set, cached as JSON lines in --cache) and gives
each term one example: a score (`PGS...`) that used the cohort, with the PMID and
title of the publication in which it did so (the score's own for development, the
evaluating publication for an evaluation). The Catalog's record is the evidence,
so the line has no quote; the note says where in the record the cohort is.

Which score: a use of the cohort's own data first (training samples, then
evaluation), then the samples of a source GWAS; among those, a publication with a
PMID, then the sample naming the fewest cohorts (it says most about this one),
then the lowest score id. The term's cohort id in the Catalog is the `PGS id` of
its row in catalog_cohorts_review.tsv (or its `input name`, where that is a
Catalog id).

By default the placeholders of the subset (uncurated terms, IAO:0000124) that have
no example yet are done; --all does every live term of the subset without a PGS
example. The lines go to src/curation/example_studies_curated.tsv (a term that
already has a PGS line there is left alone); run example_studies.py afterwards.
Terms the Catalog lists in its cohort table but uses in no score get no example
and are printed. A placeholder among them stays in the subset (the check exempts
it); with --all, a curated term among them is taken out of the subset, since the
subset-example check requires a PGS Catalog example of every curated term in it,
and the removal is recorded in src/curation/subset_examples_backfill.tsv. So
after placeholders are curated, run this with --all.

Usage: pgs_examples.py [--all] [--dry-run] [--cache DIR] [--refresh]
"""
import argparse
import csv
import datetime
import json
import re
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mint_cohorts as M  # noqa: E402

REST = "https://www.pgscatalog.org/rest/"
CURATED = M.CUR / "example_studies_curated.tsv"
BACKFILL = M.CUR / "subset_examples_backfill.tsv"
ENDPOINTS = ("score/all", "performance/all", "sample_set/all")
ROLES = {"samples_training": 0, "evaluation": 1, "samples_variants": 2}


def fetch(url):
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            print(f"  {url}: {e}, retrying", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    sys.exit(f"could not fetch {url}")


def catalog(cache, refresh):
    """endpoint -> its records, from the cache or the Catalog."""
    cache.mkdir(parents=True, exist_ok=True)
    out = {}
    for ep in ENDPOINTS:
        f = cache / (ep.replace("/", "_") + ".jsonl")
        if f.exists() and not refresh:
            out[ep] = [json.loads(line) for line in f.open(encoding="utf-8")]
            continue
        print(f"fetching {ep} from the PGS Catalog", file=sys.stderr)
        records, url = [], f"{REST}{ep}?limit=250"
        while url:
            d = fetch(url)
            records += d["results"]
            url = d.get("next")
            time.sleep(0.5)
        with f.open("w", encoding="utf-8") as w:
            for x in records:
                w.write(json.dumps(x) + "\n")
        out[ep] = records
    return out


def candidates(cat):
    """Catalog cohort id -> [(rank, record)], one per sample the cohort is in."""
    cands = defaultdict(list)

    def add(cid, kind, pgs, pub, sample, **extra):
        names = [c["name_short"] for c in sample.get("cohorts") or []]
        full = next(c["name_full"] for c in sample["cohorts"] if c["name_short"] == cid)
        rank = (ROLES[kind], not pub.get("PMID"), len(names), int(pgs[3:]))
        cands[cid].append((rank, dict(kind=kind, pgs=pgs, pub=pub, ncohorts=len(names), name_full=full, **extra)))

    for s in cat["score/all"]:
        for kind in ("samples_training", "samples_variants"):
            for sample in s.get(kind) or []:
                for c in sample.get("cohorts") or []:
                    add(c["name_short"], kind, s["id"], s.get("publication") or {}, sample,
                        gcst=sample.get("source_GWAS_catalog"), source_pmid=sample.get("source_PMID"))
    samplesets = {x["id"]: x for x in cat["sample_set/all"]}
    for p in cat["performance/all"]:
        pss = (p.get("sampleset") or {}).get("id")
        for sample in (samplesets.get(pss) or {}).get("samples") or []:
            for c in sample.get("cohorts") or []:
                add(c["name_short"], "evaluation", p["associated_pgs_id"], p.get("publication") or {}, sample, pss=pss, ppm=p["id"])
    return cands


def note(cid, rec, today):
    pub = rec["pub"]
    where = f"{pub['id']}, PMID:{pub['PMID']}"
    n = rec["ncohorts"]
    among = f"among the {n} cohorts" if n > 1 else "as the cohort"
    if rec["kind"] == "samples_training":
        how = f"{among} of the training samples of {rec['pgs']}, a score of {where}"
    elif rec["kind"] == "samples_variants":
        src = f"GWAS Catalog study {rec['gcst']}" if rec.get("gcst") else "a GWAS"
        src += f", PMID:{rec['source_pmid']}" if rec.get("source_pmid") else ""
        how = f"{among} of the samples of {src}, whose variant associations {rec['pgs']}, a score of {where}, was developed from"
    else:
        how = f"{among} of sample set {rec['pss']}, on which {rec['pgs']} was evaluated ({rec['ppm']}) in {where}"
    return f"PGS Catalog, {today}: the Catalog lists {cid} ({rec['name_full']}) {how}; the Catalog's record is the evidence, so there is no quote"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="every live term of the PGS subset, not only the placeholders")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache/coho/pgs_catalog")
    ap.add_argument("--refresh", action="store_true", help="download the Catalog again")
    a = ap.parse_args()

    text = M.EDIT.read_text(encoding="utf-8")
    T = M.parse(text)
    live = {c for c, t in T.items() if t["types"] and not t["dep"]}
    uncurated = set(re.findall(r"AnnotationAssertion\(obo:IAO_0000114 coho:(COHO_\d+) obo:IAO_0000124\)", text)) & live
    with M.PGS_SUBSET.open(newline="", encoding="utf-8") as f:
        subset = [M.local(r[0]) for r in list(csv.reader(f))[2:] if r[0].startswith("COHO:")]
    subset = [c for c in subset if c in live]

    cat = catalog(a.cache, a.refresh)
    cands = candidates(cat)
    ids = defaultdict(list)  # term -> its Catalog cohort ids
    with M.REVIEW.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if not r["COHO ID"]:
                continue
            for k in ("PGS id", "input name"):
                v = (r[k] or "").strip()
                if v and (v in cands or k == "PGS id") and v not in ids[M.local(r["COHO ID"])]:
                    ids[M.local(r["COHO ID"])].append(v)

    have = defaultdict(set)  # term -> its curated example studies
    with CURATED.open(newline="", encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        for r in csv.DictReader(f, delimiter="\t", fieldnames=header, quoting=csv.QUOTE_NONE):
            have[M.local(r["ID"])].add((r["example study"] or "").strip() or f"PMID:{(r['PMID'] or '').strip().removeprefix('PMID:')}")

    todo = [c for c in subset if (a.all or c in uncurated) and not any(re.fullmatch(r"PGS\d+", e) for e in have[c])]
    if not a.all:
        todo = [c for c in todo if not have[c]]
    today = datetime.date.today().isoformat()
    lines, unused, unmapped = [], [], []
    for c in todo:
        if not ids[c]:
            unmapped.append(c)
            continue
        best = min(((rank, rec, cid) for cid in ids[c] for rank, rec in cands.get(cid, ())), key=lambda x: x[0], default=None)
        if best is None:
            unused.append(c)
            continue
        rank, rec, cid = best
        lines.append([M.curie(c), rec["pgs"], f"PMID:{rec['pub']['PMID']}", note(cid, rec, today), "", "", rec["pub"].get("title") or ""])

    kinds = defaultdict(int)
    for line in lines:
        kinds[re.search(r"training samples|variant associations|evaluated", line[3]).group(0)] += 1
    drop = [c for c in unused if c not in uncurated]  # curated terms the Catalog uses in no score leave the subset
    print(f"{len(subset)} live terms in the PGS subset, {len(todo)} to do: {len(lines)} given a PGS Catalog example "
          f"({', '.join(f'{v} {k}' for k, v in sorted(kinds.items()))}), {len(unused)} used by no score "
          f"({len(unused) - len(drop)} placeholders, which stay in the subset; {len(drop)} curated terms, taken out of it), "
          f"{len(unmapped)} with no Catalog id")
    if unused:
        print("used by no score in the Catalog: " + ", ".join(f"{M.curie(c)} {T[c]['label']} [{'|'.join(ids[c])}]" for c in unused))
    if drop:
        print("taken out of the PGS subset: " + ", ".join(f"{M.curie(c)} {T[c]['label']}" for c in drop))
    if unmapped:
        print("no Catalog id in the review: " + ", ".join(f"{M.curie(c)} {T[c]['label']}" for c in unmapped))
    if a.dry_run:
        for line in lines[:5]:
            print("\t".join(line))
        return
    if lines:
        t = CURATED.read_text(encoding="utf-8")
        CURATED.write_text(t + ("" if t.endswith("\n") else "\n") + M.rows_to_text(lines), encoding="utf-8")
        print(f"{len(lines)} lines appended to {CURATED.relative_to(M.ROOT)}; now run example_studies.py")
    if drop:
        gone = {M.curie(c) for c in drop}
        with M.PGS_SUBSET.open(newline="", encoding="utf-8") as f:
            rows = [r for r in csv.reader(f) if r and r[0] not in gone]
        with M.PGS_SUBSET.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f, lineterminator="\n").writerows(rows)
        record = [[M.curie(c), "PGS", "NOT FOUND", "removed from subset", "", "", "", "", "",
                   f"No score in the PGS Catalog uses {M.joinnames(ids[c])}: the Catalog's cohort table lists the id, but no score's "
                   f"development samples and no evaluated sample set name it (REST API, every score, performance metric and sample set, {today})"]
                  for c in drop]
        t = BACKFILL.read_text(encoding="utf-8")
        BACKFILL.write_text(t + ("" if t.endswith("\n") else "\n") + M.rows_to_text(record), encoding="utf-8")
        print(f"{len(drop)} terms taken out of {M.PGS_SUBSET.relative_to(M.ROOT)}, recorded in {BACKFILL.relative_to(M.ROOT)}")


if __name__ == "__main__":
    main()
