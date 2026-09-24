#!/usr/bin/env python3
"""
Curate placeholder terms from decided review rows.

A placeholder is an uncurated term (IAO:0000114 IAO:0000124) of the temporary
unclassified class that carries only a catalog's name and ids. When such a name
has been checked against its sources, its decision comes as a row in the format
of src/curation/catalog_cohorts_review.tsv, preceded by two columns: the review
key and the placeholder's COHO ID. For each row this script

  - verdict "mint cohort" or "mint aggregation": curates the term in place, keeping
    its ID: the row's label (the old label kept as a synonym), its acronyms and
    other names, the type, an isSubCohortOf link with its quote, and rows for its
    definition, example, locations and memberships in the curated files; the
    curation status goes, the PGS subset membership stays;
  - verdict "not a cohort": obsoletes the term (label "obsolete …", owl:deprecated,
    a comment giving the reason) and drops it from the PGS subset;
  - verdict "existing" (the COHO ID column names the term the sample is) or
    "same as" (another row of the file, or a term): obsoletes the placeholder with
    "term replaced by" that term, moves its names to that term as synonyms, and
    puts that term in the PGS subset;
  - verdict "unresolved": leaves the term as it is;

gives every term an editor note wherever a name becomes shared (and removes notes
that named an obsoleted term), and rewrites each placeholder's row of the review
with the decision, the term's ID (the surviving term's, for a merge) and the terms
its names clash with. Changes to terms other than the placeholders are limited to
the names a merge adds and the editor notes.

Usage: curate_placeholders.py --rows FILE --provenance TEXT [--date YYYY-MM-DD] [--dry-run]
"""

import argparse
import collections
import csv
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mint_cohorts as M  # noqa: E402

COMMENT = 'AnnotationAssertion(rdfs:comment coho:{} "{}"@en)'
REPLACED = "AnnotationAssertion(obo:IAO_0100001 coho:{} coho:{})"
DEPRECATED = 'AnnotationAssertion(owl:deprecated coho:{} "true"^^xsd:boolean)'
LABEL = 'AnnotationAssertion(rdfs:label coho:{} "{}"@en)'
ANCHOR = "SubObjectPropertyOf(ObjectPropertyChain("
PREFIX_RE = re.compile(r"^Tier E \(E\d+\), minted as a placeholder and checked against its sources on \d{4}-\d{2}-\d{2} without a draft\.\s*")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--provenance", required=True)
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.rows, newline="", encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE))
    text = M.EDIT.read_text(encoding="utf-8")
    T = M.parse(text)
    live = {c for c, t in T.items() if t["types"] and not t["dep"]}
    uncurated = set(re.findall(r"obo:IAO_0000114 coho:(COHO_\d+) obo:IAO_0000124", text))
    gaz = {l.split("\t")[0].split(":", 1)[1] for l in open(M.GAZ, encoding="utf-8") if l.startswith("dbpedia:")}
    review = open(M.REVIEW, newline="", encoding="utf-8").read().split("\n")
    head = review[0].split("\t")
    col = {h: i for i, h in enumerate(head)}
    line_of = {}
    for i, l in enumerate(review[1:], 1):
        f = l.split("\t")
        if len(f) == len(head) and f[col["verdict"]] == "placeholder":
            m = re.match(r"Tier E \((E\d+)\)", f[col["note"]])
            if m:
                line_of[m.group(1)] = i
    problems = []

    # --- what each row asks for
    byph = {}
    for x in rows:
        x["_c"] = M.local(x["placeholder"])
        byph[x["_c"]] = x
    for x in rows:
        if x["same as"] and x["verdict"] != "unresolved":
            x["verdict"] = "same as"   # the review gives such a row its target's verdict; here it is a merge
    for x in rows:
        k, c, v = x["key"], x["_c"], x["verdict"]
        if c not in uncurated or c not in live:
            problems.append(f"{k}: {x['placeholder']} is not a live uncurated term")
        if k not in line_of:
            problems.append(f"{k}: no placeholder row in the review")
        x["_target"] = None
        if v in M.MINT:
            want = "cohort aggregation" if v == "mint aggregation" else "cohort"
            if x["type"] != want:
                problems.append(f"{k}: type {x['type']!r} does not agree with verdict {v!r}")
            if not x["label"]:
                problems.append(f"{k}: no label")
            for o in live:
                if o != c and M.norm(T[o]["label"]) == M.norm(x["label"]):
                    problems.append(f"{k}: label {x['label']!r} is already {M.curie(o)}")
            if not (x["definition"] and x["definition source"] and x["drafted by"]):
                problems.append(f"{k}: definition, its source and its drafter are all needed")
            if not (x["example study"] or x["example PMID"]):
                problems.append(f"{k}: no example study or paper")
            elif bool(x["example quote"]) != bool(x["example quote URL"]):
                problems.append(f"{k}: the example's quote and URL go together")
            groups = [g.strip() for g in x["countries"].split(" || ")] if x["countries"] else []
            if x["countries"] and len({len(groups), len(x["location quote"].split(" || ")), len(x["location URL"].split(" || "))}) != 1:
                problems.append(f"{k}: countries, location quote and location URL have different numbers of groups")
            for cc in (cc for g in groups for cc in M.split(g)):
                if cc not in gaz:
                    problems.append(f"{k}: country {cc} is not in {M.GAZ.name}")
            if x["parent"]:
                if x["parent relation"] not in ("isSubCohortOf", "memberOf"):
                    problems.append(f"{k}: parent relation {x['parent relation']!r}")
                if not (x["parent quote"] and x["parent URL"]):
                    problems.append(f"{k}: the parent needs a quote and its URL")
        elif v == "existing":
            t = M.local(x["COHO ID"]) if x["COHO ID"] else None
            if not t or t not in live or t == c:
                problems.append(f"{k}: verdict existing needs a live COHO ID other than the placeholder")
            x["_target"] = t
        elif v == "same as":
            x["_target"] = None  # resolved below, once every row is known
        elif v == "not a cohort":
            if not x["note"]:
                problems.append(f"{k}: not a cohort needs a note giving the reason")
        elif v == "unresolved":
            pass
        else:
            problems.append(f"{k}: verdict {v!r}")

    def resolve(ref, exclude):
        """a row reference: a COHO ID, or the PGS id or label of another row of this file"""
        if ref.startswith("COHO:"):
            t = M.local(ref)
            if t not in live:
                problems.append(f"{ref} is not a live COHO term")
            return t
        c = [y for y in rows if y is not exclude and y["verdict"] in M.MINT and (y["PGS id"] == ref or y["label"] == ref)]
        if len(c) != 1:
            problems.append(f"row reference {ref!r} resolves to {len(c)} rows of the file")
            return None
        return c[0]["_c"]

    for x in rows:
        if x["verdict"] == "same as":
            x["_target"] = resolve(x["same as"], x) if x["same as"] else None
            if not x["_target"]:
                problems.append(f"{x['key']}: same as needs a target")
        if x["verdict"] in M.MINT and x["parent"]:
            x["_parent"] = resolve(x["parent"], x)
            if x["_parent"] and x["parent relation"] == "memberOf" and x["_parent"] not in byph and M.AGGREGATION not in T[x["_parent"]]["types"]:
                problems.append(f"{x['key']}: memberOf {M.curie(x['_parent'])}, which is not a cohort aggregation")

    curated = [x for x in rows if x["verdict"] in M.MINT]
    merged = [x for x in rows if x["verdict"] in ("existing", "same as") and x["_target"]]
    gone = [x for x in rows if x["verdict"] == "not a cohort"]
    obsoleted = {x["_c"] for x in merged + gone}
    for x in merged:
        if x["_target"] in obsoleted:
            problems.append(f"{x['key']}: its target {M.curie(x['_target'])} is obsoleted by this run")
    for x in curated:
        if x.get("_parent") in obsoleted:
            problems.append(f"{x['key']}: its parent {M.curie(x['_parent'])} is obsoleted by this run")
    if problems:
        raise SystemExit("not applied:\n  " + "\n  ".join(dict.fromkeys(problems)))

    # --- names after the run
    def add(lst, label, s, acr, have=()):
        if s and s != label and s not in have and all(s != e for e, _ in lst):
            lst.append((s, acr))

    names = {}  # curated term -> [(name, is_acronym)]
    for x in curated:
        c = x["_c"]
        lst = [(s, acr) for s, acr in T[c]["syn"] if s != x["label"]]
        old = T[c]["label"]
        for s in M.split(x["acronym synonyms"]) + [x["PGS id"]] + M.split(x["GWAS tags"], ";"):
            add(lst, x["label"], s, True)
        add(lst, x["label"], old, False)
        for s in M.split(x["other synonyms"]):
            add(lst, x["label"], s, False)
        names[c] = lst
    added = collections.defaultdict(list)  # merge target -> [(name, is_acronym)]
    for x in merged:
        c, t = x["_c"], x["_target"]
        have = {e for e, _ in T[t]["syn"]}
        cands = [(s, True) for s in M.split(x["acronym synonyms"]) + [x["PGS id"]] + M.split(x["GWAS tags"], ";")]
        cands += [(s, acr) for s, acr in T[c]["syn"]] + [(T[c]["label"], False)] + [(s, False) for s in M.split(x["other synonyms"])]
        for s, acr in cands:
            add(added[t], T[t]["label"], s, acr, have)
    added = {k: v for k, v in added.items() if v}

    # --- shared names: editor notes on every term concerned; notes naming an obsoleted term go
    live2 = live - obsoleted
    label = {c: T[c]["label"] for c in live2}
    label.update({x["_c"]: x["label"] for x in curated})
    syns = {c: {s: acr for s, acr in T[c]["syn"]} for c in live2}
    for c, v in added.items():
        syns[c].update(dict(v))
    for c, v in names.items():
        syns[c] = dict(v)
    groups = collections.defaultdict(dict)
    for c, ss in syns.items():
        for s in ss:
            groups[M.norm(s)].setdefault(c, s)
    stale = collections.defaultdict(list)  # term -> notes that name an obsoleted term
    for c in live2:
        for n in T[c]["notes"]:
            if any(M.curie(o) in n for o in obsoleted):
                stale[c].append(n)

    def changed(k, c):
        return c in names or any(M.norm(s) == k for s, _ in added.get(c, [])) or any(k in M.norm(n) for n in stale.get(c, []))

    shared = {k: v for k, v in groups.items() if len(v) > 1 and any(changed(k, c) for c in v)}
    notes, rewrite = collections.defaultdict(list), collections.defaultdict(list)
    for k, v in sorted(shared.items()):
        ids = sorted(v)
        for c in ids:
            s = v[c]
            others = [f"{label[o]} ({M.curie(o)})" for o in ids if o != c]
            kind = "name" if len(s.split()) >= 3 else "acronym"
            n = f"The {kind} {s} also denotes {M.joinnames(others)}; this term is {label[c]}."
            old = [m for m in T[c]["notes"] if M.norm(m).startswith((f"the acronym {k} also denotes", f"the name {k} also denotes"))]
            if len(old) > 1:
                raise SystemExit(f"{M.curie(c)} has {len(old)} notes on {k!r}")
            if old and old[0] != n:
                rewrite[c].append((old[0], n))
                stale[c] = [m for m in stale[c] if m != old[0]]
            elif not old:
                notes[c].append(n)
    clashes = {c: sorted({M.curie(o) for k, v in shared.items() if c in v for o in v if o != c}) for c in syns}

    # --- the edit file
    lines = text.split("\n")
    starts = {}
    for i, l in enumerate(lines):
        m = re.match(r"# Individual: coho:(COHO_\d+) ", l)
        if m:
            starts[m.group(1)] = i
    anchor = [i for i, l in enumerate(lines) if l.startswith(ANCHOR)]
    if len(anchor) != 1:
        raise SystemExit(f"expected one {ANCHOR!r} line in the edit file")
    bounds = sorted(starts.values()) + anchor

    def block(c):
        s = starts[c]
        e = bounds[bounds.index(s) + 1]
        return s, e

    def synline(c, s, acr):
        return (M.ACR if acr else M.REL).format(c, M.esc(s))

    def reason_of(x):
        return PREFIX_RE.sub("", x["note"]).strip() or x["note"].strip()

    subs = {x["_c"]: x for x in curated if x.get("_parent") and x["parent relation"] == "isSubCohortOf"}
    new_blocks = {}
    for x in curated:
        c = x["_c"]
        s, e = block(c)
        keep = [l for l in lines[s + 1:e] if l and not re.match(r"AnnotationAssertion\((Annotation\(oboInOwl:hasSynonymType obo:OMO_0003000\) )?oboInOwl:has\w+Synonym coho:", l)
                and not l.startswith(("AnnotationAssertion(obo:IAO_0000114 ", "AnnotationAssertion(rdfs:label ", "ClassAssertion(", "AnnotationAssertion(obo:IAO_0000116 "))]
        b = [f"# Individual: coho:{c} ({x['label']})", ""]
        b += [synline(c, n, acr) for n, acr in names[c] if acr] + [synline(c, n, acr) for n, acr in names[c] if not acr]
        old_notes = [n for n in T[c]["notes"] if n not in stale.get(c, []) and n not in [o for o, _ in rewrite.get(c, [])]]
        b += [M.NOTE.format(c, M.esc(n)) for n in old_notes + [n for _, n in rewrite.get(c, [])] + notes.get(c, [])]
        b += keep
        b.append(LABEL.format(c, M.esc(x["label"])))
        b.append(f"ClassAssertion(coho:{M.AGGREGATION if x['verdict'] == 'mint aggregation' else M.COHORT} coho:{c})")
        if c in subs:
            b.append(M.SUB.format(M.esc(x["parent quote"]), M.esc(x["parent URL"]), c, x["_parent"]))
        new_blocks[c] = b + [""]
    for x in merged + gone:
        c = x["_c"]
        b = [f"# Individual: coho:{c} (obsolete {T[c]['label']})", ""]
        if x["_target"]:
            b.append(REPLACED.format(c, x["_target"]))
            why = (f"Obsoleted {a.date}. {reason_of(x)} Replaced by {M.curie(x['_target'])} ({label[x['_target']]}), "
                   f"which now carries this term's names. Found by {a.provenance}.")
        else:
            why = f"Obsoleted {a.date}. {reason_of(x)} Found by {a.provenance}."
        b.append(COMMENT.format(c, M.esc(re.sub(r"\s+", " ", why))))
        b.append(LABEL.format(c, M.esc("obsolete " + T[c]["label"])))
        b.append(DEPRECATED.format(c))
        new_blocks[c] = b + [""]
    out, cur, ins = [], None, collections.Counter()
    want = {c: len(added.get(c, [])) + len(notes.get(c, [])) for c in set(added) | set(notes) if c not in new_blocks}
    skip_to = None
    for i, l in enumerate(lines):
        if skip_to is not None:
            if i < skip_to:
                continue
            skip_to = None
        m = re.match(r"# Individual: coho:(COHO_\d+) ", l)
        if m:
            cur = m.group(1)
            if cur in new_blocks:
                out += new_blocks[cur]
                skip_to = block(cur)[1]
                continue
        if cur and cur not in new_blocks and l.startswith(f"AnnotationAssertion(rdfs:label coho:{cur} "):
            for n, acr in added.get(cur, []):
                out.append(synline(cur, n, acr)); ins[cur] += 1
            for n in notes.get(cur, []):
                out.append(M.NOTE.format(cur, M.esc(n))); ins[cur] += 1
        if cur and cur not in new_blocks and l.startswith(f"AnnotationAssertion(obo:IAO_0000116 coho:{cur} "):
            for o, n in rewrite.get(cur, []):
                if l == M.NOTE.format(cur, M.esc(o)):
                    l = M.NOTE.format(cur, M.esc(n))
            if any(l == M.NOTE.format(cur, M.esc(o)) for o in stale.get(cur, [])):
                continue
        out.append(l)
    for c, w in want.items():
        if ins[c] != w:
            raise SystemExit(f"{M.curie(c)}: {ins[c]} of {w} lines placed; is its block in the edit file?")
    text2 = "\n".join(out)

    # --- curated files and subsets
    ex, tit, de, lo, am, ty = [], [], [], [], [], []
    titles = {r["PMID"] for r in csv.DictReader(open(M.CUR / "example_studies_titles.tsv", encoding="utf-8"), delimiter="\t")}
    for x in curated:
        i = M.curie(x["_c"])
        note = f"curated {a.date} from {a.provenance}"
        ex.append([i, x["example study"], x["example PMID"], note + ("" if x["example quote"] else "; no quote: the paper could not be read (see the review's note)"), x["example quote"], x["example quote URL"], ""])
        p = x["example PMID"].removeprefix("PMID:")
        if p and p not in titles and x["example title"]:
            titles.add(p); tit.append([p, x["example title"]])
        de.append([i, x["definition"], x["definition source"], f"written from the cited source when the placeholder was {note}", x["drafted by"]])
        if x["countries"]:
            for cs, q, u in zip(x["countries"].split(" || "), x["location quote"].split(" || "), x["location URL"].split(" || ")):
                lo.append([i, cs.strip(), q.strip(), u.strip(), note + ("" if q.strip() else "; the country is given by the cohort's name, no quote")])
        if x.get("_parent") and x["parent relation"] == "memberOf":
            am.append([M.curie(x["_parent"]), i, x["parent quote"], x["parent URL"], f"membership stated in the source; added when the placeholder was {note}"])
        ty.append([i, x["label"], "temporary unclassified", x["type"], "yes", f"placeholder {note}"])
    pgs = open(M.PGS_SUBSET, encoding="utf-8").read().split("\n")
    pgs_ids = {l.split(",")[0] for l in pgs}
    pgs = [l for l in pgs if l.split(",")[0] not in {M.curie(c) for c in obsoleted}]
    for x in merged:
        t = M.curie(x["_target"])
        if t not in pgs_ids:
            pgs_ids.add(t)
            pgs.append(",".join([t, "owl:NamedIndividual", "http://www.ebi.ac.uk/coho#PGS_subset", label[x["_target"]].replace(",", " ")]))
    pgs_text = "\n".join(l for l in pgs if l) + "\n"

    # --- the review
    for x in rows:
        f = review[line_of[x["key"]]].split("\t")
        if x["verdict"] == "unresolved":
            # the term stays a placeholder: its row keeps everything but gains the check's note
            f[col["note"]] = (f[col["note"]].rstrip() + " " + PREFIX_RE.sub("Checked against its sources on " + a.date + " without a draft, unresolved: ", x["note"]).strip()).strip()
            review[line_of[x["key"]]] = "\t".join(re.sub(r"[\t\r\n]+", " ", v) for v in f)
            continue
        for h in head:
            if h in x:
                f[col[h]] = x[h]
        if x["verdict"] in ("existing", "same as"):
            f[col["COHO ID"]] = M.curie(x["_target"])
            f[col["note"]] = (x["note"].rstrip() + f" The placeholder {x['placeholder']} was obsoleted {a.date}, replaced by {M.curie(x['_target'])}, which took its names.").strip()
            if x["verdict"] == "same as" and not x["same as"].startswith("COHO:"):
                f[col["verdict"]] = "existing" if x["_target"] not in byph else byph[x["_target"]]["verdict"]
        else:
            f[col["COHO ID"]] = x["placeholder"]
        t = x["_target"] if x["verdict"] in ("existing", "same as") else x["_c"]
        f[col["clashes with"]] = "|".join(clashes.get(t, [])) if t not in obsoleted else ""
        review[line_of[x["key"]]] = "\t".join(re.sub(r"[\t\r\n]+", " ", v) for v in f)

    print(f"curated {len(curated)}, obsoleted {len(gone)} as not cohorts, merged {len(merged)} into existing terms, unresolved {sum(1 for x in rows if x['verdict'] == 'unresolved')}")
    print(f"names added to merge targets {sum(len(v) for v in added.values())} on {len(added)} terms; editor notes {sum(len(v) for v in notes.values())} new, "
          f"{sum(len(v) for v in rewrite.values())} rewritten, {sum(len(v) for v in stale.values())} removed; isSubCohortOf {len(subs)}; memberships {len(am)}")
    print(f"definitions {len(de)}, examples {len(ex)}, titles {len(tit)}, location lines {len(lo)}; PGS subset lines now {len(pgs) - 1}")
    if a.dry_run:
        return
    M.EDIT.write_text(text2, encoding="utf-8")
    for path, rs in ((M.CUR / "example_studies_curated.tsv", ex), (M.CUR / "example_studies_titles.tsv", tit), (M.CUR / "definitions_curated.tsv", de),
                     (M.CUR / "location_curated.tsv", lo), (M.CUR / "aggregation_members_curated.tsv", am), (M.CUR / "type_changes.tsv", ty)):
        if rs:
            t = path.read_text(encoding="utf-8")
            path.write_text(t + ("" if t.endswith("\n") else "\n") + M.rows_to_text(rs), encoding="utf-8")
    M.PGS_SUBSET.write_text(pgs_text, encoding="utf-8")
    open(M.REVIEW, "w", newline="", encoding="utf-8").write("\n".join(review))


if __name__ == "__main__":
    main()
