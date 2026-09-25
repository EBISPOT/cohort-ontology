#!/usr/bin/env python3
"""
Add cross-references and websites to terms of the edit file from a table.

The table (tab-separated, with a header) names a term in a `COHO ID` column.
Its `xref` column gives the URL of the cohort's record in an outside catalogue,
or a CURIE, which becomes an `oboInOwl:hasDbXref` annotation on the term; its
`website` column gives the cohort's website as the catalogue states it, which
becomes an `rdfs:seeAlso` annotation. Either column may be absent or empty.
The annotations are placed after the term's label; one the term already carries
is left as it is, and a row whose term is not a live term of the edit file is an
error.

Usage: add_xrefs.py TABLE [--dry-run]
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mint_cohorts as M  # noqa: E402

XREF = 'AnnotationAssertion(oboInOwl:hasDbXref coho:{} "{}")'
SEEALSO = "AnnotationAssertion(rdfs:seeAlso coho:{} <{}>)"


def main():
    table, dry = sys.argv[1], "--dry-run" in sys.argv
    rows = [r for r in csv.DictReader(open(table, newline="", encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE) if r.get("COHO ID")]
    text = M.EDIT.read_text(encoding="utf-8")
    T = M.parse(text)
    live = {c for c, t in T.items() if t["types"] and not t["dep"]}
    want = {}
    for r in rows:
        x, w = (r.get("xref") or "").strip(), (r.get("website") or "").strip()
        if not (x or w):
            continue
        c = M.local(r["COHO ID"])
        if c not in live:
            raise SystemExit(f"{r['COHO ID']} is not a live term")
        lines = want.setdefault(c, [])
        if x:
            lines.append(XREF.format(c, M.esc(x)))
        if w:
            if re.search(r'[\s<>"{}|\\^`]', w):
                raise SystemExit(f"{r['COHO ID']}: website {w!r} is not a valid IRI")
            lines.append(SEEALSO.format(c, w))
    out, cur, added, present = [], None, 0, 0
    for l in text.split("\n"):
        m = re.match(r"# Individual: coho:(COHO_\d+) ", l)
        if m:
            cur = m.group(1)
        out.append(l)
        if cur in want and l.startswith(f"AnnotationAssertion(rdfs:label coho:{cur} "):
            for line in dict.fromkeys(want[cur]):
                if line in text:
                    present += 1
                else:
                    out.append(line); added += 1
    print(f"{added} annotations added on {len(want)} terms, {present} already present")
    if not dry:
        M.EDIT.write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
