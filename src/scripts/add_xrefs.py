#!/usr/bin/env python3
"""
Add cross-references to terms of the edit file from a table.

The table (tab-separated, with a header) names a term in a `COHO ID` column and
the reference in an `xref` column: the URL of the cohort's record in an outside
catalogue, or a CURIE. Each becomes an `oboInOwl:hasDbXref` annotation on the
term, placed after its label; a reference the term already carries is left as it
is, and a row whose term is not a live term of the edit file is an error.

Usage: add_xrefs.py TABLE [--dry-run]
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mint_cohorts as M  # noqa: E402

XREF = 'AnnotationAssertion(oboInOwl:hasDbXref coho:{} "{}")'


def main():
    table, dry = sys.argv[1], "--dry-run" in sys.argv
    rows = [r for r in csv.DictReader(open(table, newline="", encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE) if r.get("COHO ID") and r.get("xref")]
    text = M.EDIT.read_text(encoding="utf-8")
    T = M.parse(text)
    live = {c for c, t in T.items() if t["types"] and not t["dep"]}
    want = {}
    for r in rows:
        c = M.local(r["COHO ID"])
        if c not in live:
            raise SystemExit(f"{r['COHO ID']} is not a live term")
        want.setdefault(c, []).append(r["xref"].strip())
    out, cur, added, present = [], None, 0, 0
    for l in text.split("\n"):
        m = re.match(r"# Individual: coho:(COHO_\d+) ", l)
        if m:
            cur = m.group(1)
        out.append(l)
        if cur in want and l.startswith(f"AnnotationAssertion(rdfs:label coho:{cur} "):
            for x in dict.fromkeys(want[cur]):
                line = XREF.format(cur, M.esc(x))
                if line in text:
                    present += 1
                else:
                    out.append(line); added += 1
    print(f"xrefs: {added} added on {len(want)} terms, {present} already present")
    if not dry:
        M.EDIT.write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
