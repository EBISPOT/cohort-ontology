#!/usr/bin/env python3
"""
Write the number of participants of each cohort as a ROBOT template,
src/templates/participants.tsv, which becomes the participants.owl component:
a numberOfParticipants, numberOfCases or numberOfControls annotation on each
cohort whose number a source states, with the evidence for it as annotations on
the assertion: the verbatim sentence stating the number (rdfs:comment), the
source it came from (oboInOwl:hasDbXref, a PMID or a URL) and what the number
counts and the year it refers to (IAO:0000116).

Source:
  src/curation/cohort_participants.csv   one row per curated cohort: the number
                                         the cohort itself reports (participants;
                                         cases and controls where the source gives
                                         them separately), what it counts, the
                                         year, the quote, its source, whether the
                                         quote was found verbatim in the source,
                                         and a note

A row with no number gives nothing. The quote is attached only where the check
found it verbatim in its source ("quote verified" is yes); otherwise the number
stands with its source and note alone, as with locations. Every number is
copied as the table gives it; nothing is computed. A row whose term is not a
live term of the edit file is an error, so the table is kept in step with the
ontology.

Usage: src/scripts/participants.py
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mint_cohorts as M  # noqa: E402

TABLE = M.ROOT / "src/curation/cohort_participants.csv"
TEMPLATE = M.ROOT / "src/templates/participants.tsv"
NUMBERS = [("participants", "numberOfParticipants"), ("cases", "numberOfCases"), ("controls", "numberOfControls")]


def note(row):
    """What the number counts and the year it refers to, in a few words."""
    counts, year = row["counts"].strip(), row["year"].strip()
    if year and year not in counts:
        if not counts:
            return f"as of {year}"
        return f"{counts}, {year}" if counts.endswith(")") else f"{counts} ({year})"
    return counts


def main():
    T = M.parse(M.EDIT.read_text(encoding="utf-8"))
    rows = []
    with open(TABLE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            numbers = {k: r[k].strip() for k, _ in NUMBERS if r[k].strip()}
            if not numbers:
                continue
            for k, v in numbers.items():
                if not re.fullmatch(r"[0-9]+", v):
                    raise SystemExit(f"{r['ID']}: {k} {v!r} is not an integer")
            c = M.local(r["ID"])
            t = T.get(c)
            if not t or not t["types"] or t["dep"]:
                raise SystemExit(f"{r['ID']} is not a live term")
            if not r["source"].strip():
                raise SystemExit(f"{r['ID']}: a number without a source")
            quote = r["quote"].strip() if r["quote verified"] == "yes" else ""
            out = [r["ID"], "owl:NamedIndividual", t["label"]]
            for k, _ in NUMBERS:
                v = numbers.get(k, "")
                out += [v, quote if v else "", r["source"].strip() if v else "", note(r) if v else ""]
            rows.append(out)
    rows.sort(key=lambda x: x[0])
    with open(TEMPLATE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        header, spec = ["ID", "TYPE", "label"], ["ID", "TYPE", ""]
        for k, prop in NUMBERS:
            header += [k, f"{k} evidence", f"{k} source", f"{k} note"]
            spec += [f"AT coho:{prop}^^xsd:integer", ">A rdfs:comment", ">A oio:hasDbXref", ">A IAO:0000116"]
        w.writerow(header)
        w.writerow(spec)
        w.writerows(rows)
    n = {k: sum(1 for x in rows if x[3 + 4 * i]) for i, (k, _) in enumerate(NUMBERS)}
    print(f"{TEMPLATE.relative_to(M.ROOT)}: {len(rows)} cohorts, {n}")


if __name__ == "__main__":
    main()
