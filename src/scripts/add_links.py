#!/usr/bin/env python3
"""
Add sub-cohort and membership links between existing terms from a table.

The table (tab-separated, with a header) has the columns `child`, `parent`,
`relation` (isSubCohortOf or memberOf), `quote`, `url` and optionally `note`.
An isSubCohortOf row becomes an `isSubCohortOf` assertion from the child to
the parent in the edit file, placed after the child's label, annotated with
the quote and its URL; a memberOf row becomes a line of
`src/curation/aggregation_members_curated.tsv` (aggregation, member, quote,
URL, note), from which `aggregation_members.py` rebuilds the template. Links
already present are skipped; both terms must be live curated terms, the parent
of a membership an aggregation and the parent of a sub-cohort link a cohort.

Usage: add_links.py TABLE [--dry-run]
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mint_cohorts as M  # noqa: E402

CURATED = M.ROOT / "src/curation/aggregation_members_curated.tsv"


def main():
    table, dry = sys.argv[1], "--dry-run" in sys.argv
    rows = list(csv.DictReader(open(table, newline="", encoding="utf-8"), delimiter="\t"))
    text = M.EDIT.read_text(encoding="utf-8")
    T = M.parse(text)
    live = {c for c, t in T.items() if t["types"] and not t["dep"] and "TEMP_temporary_unclassified" not in t["types"]}
    agg = {c for c, t in T.items() if "COHO_0000001" in t["types"]}
    curated = list(csv.reader(open(CURATED, newline="", encoding="utf-8"), delimiter="\t"))
    have_mem = {(r[0], r[1]) for r in curated[1:] if len(r) > 1}
    have_tpl = set()
    for r in csv.reader(open(M.ROOT / "src/templates/aggregation_members.tsv", newline="", encoding="utf-8"), delimiter="\t"):
        if r and r[0].startswith("COHO:") and len(r) > 3:
            have_tpl.add((r[0], r[3]))
    subs, mems = {}, []
    for r in rows:
        c, p, rel = M.local(r["child"]), M.local(r["parent"]), r["relation"]
        if c not in live or p not in live:
            raise SystemExit(f"{r['child']} or {r['parent']} is not a live curated term")
        if rel == "isSubCohortOf":
            if p in agg:
                raise SystemExit(f"{r['parent']} is an aggregation; {r['child']} cannot be its sub-cohort")
            line = M.SUB.format(M.esc(r["quote"]), M.esc(r["url"]), c, p)
            if f"coho:isSubCohortOf coho:{c} coho:{p})" in text:
                continue
            subs.setdefault(c, []).append(line)
        elif rel == "memberOf":
            if p not in agg:
                raise SystemExit(f"{r['parent']} is not an aggregation; {r['child']} cannot be its member")
            key = (r["parent"], r["child"])
            if key in have_mem or key in have_tpl:
                continue
            have_mem.add(key)
            mems.append([r["parent"], r["child"], r["quote"], r["url"], r.get("note", "")])
        else:
            raise SystemExit(f"unknown relation {rel!r}")
    out, cur, added = [], None, 0
    for l in text.split("\n"):
        m = re.match(r"# Individual: coho:(COHO_\d+) ", l)
        if m:
            cur = m.group(1)
        out.append(l)
        if cur in subs and l.startswith(f"AnnotationAssertion(rdfs:label coho:{cur} "):
            for line in subs.pop(cur):
                out.append(line); added += 1
    if subs:
        raise SystemExit(f"no label line found for {', '.join(subs)}")
    print(f"isSubCohortOf: {added} added; memberships: {len(mems)} new rows for {CURATED.name}")
    if not dry:
        M.EDIT.write_text("\n".join(out), encoding="utf-8")
        with open(CURATED, "a", newline="", encoding="utf-8") as f:
            csv.writer(f, delimiter="\t", lineterminator="\n").writerows(mems)


if __name__ == "__main__":
    main()
