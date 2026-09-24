#!/usr/bin/env python3
"""
Mint the cohorts that src/curation/catalog_cohorts_review.tsv has decided on and
not yet minted, and record their evidence in the curated files.

The review has one row per name the GWAS Catalog or PGS Catalog uses: a verdict
(mint cohort, mint aggregation, existing, not a cohort, unresolved), the label,
acronym synonyms and other synonyms, the type, "same as" (the PGS id, label or COHO
ID of the row or term that carries a duplicate), an example with its quote (a study
accession with its paper's PMID, or a paper's PMID alone),
a definition with its source and drafter, countries with a quote, and a parent
(isSubCohortOf a cohort, or memberOf an aggregation) with a quote. From the rows
at or after --from-row the script

  - gives each row to mint (mint verdict, no COHO ID, no same-as) the next free
    COHO ID, and writes its declaration, label, type and synonyms to
    src/ontology/coho-edit.owl: the acronyms, the PGS id and the GWAS tags as
    acronyms (OMO:0003000), the other names as related synonyms;
  - adds the names of "existing" rows, and of same-as rows, to the term they denote;
  - gives both terms an editor note wherever a name becomes shared, in the form
    CLAUDE.md sets out, and rewrites an existing note when the terms it names change;
  - asserts isSubCohortOf, with its quote and URL;
  - appends the definitions, examples (with their titles), locations and
    memberships to src/curation, and the cohorts whose example is a GWAS Catalog
    study to the GWAS subset. Countries backed by different quotes are given as
    groups separated by " || " in the countries, location quote and location URL
    columns alike (e.g. "India || Canada"), and each group becomes its own
    location line. An example without a quote (its paper could not be read) is
    minted with the reason taken from the row's note, and listed;
  - writes the new COHO IDs, and the terms each row's names clash with, back
    into the review.

A "placeholder" row mints an uncurated term: the catalog's name as its label, its
ids and other names as synonyms (with editor notes where a name is shared), the
temporary unclassified holding class as its type, IAO:0000114 (has curation
status) IAO:0000124 (uncurated), and membership of the PGS subset. It gets no
definition, example, location or links; curating it later means filling those in
and removing the status. A same-as row whose twin is a placeholder adds its names
to the placeholder.

Earlier rows are only read, to resolve references. Changes to terms minted
earlier other than new names (a new definition, type or label) are not made here:
record them in catalog_cohorts_review_existing_terms.tsv and make them by hand.

Usage: src/scripts/mint_cohorts.py --from-row N --provenance TEXT [--date YYYY-MM-DD] [--dry-run]
  --from-row    the first data row (1-based) of the review that this run mints from
  --provenance  how the rows were decided, used in the curated files' notes, e.g.
                "the fourth tier of the GWAS and PGS Catalog review, checked by an
                independent review before minting"
"""

import argparse
import collections
import csv
import datetime
import io
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CUR = ROOT / "src/curation"
REVIEW = CUR / "catalog_cohorts_review.tsv"
EDIT = ROOT / "src/ontology/coho-edit.owl"
GAZ = ROOT / "src/templates/gaz_xrefs.tsv"
GWAS_SUBSET = ROOT / "src/templates/GWAS.csv"
PGS_SUBSET = ROOT / "src/templates/PGS.csv"
COHORT, AGGREGATION, UNCLASSIFIED = "COHO_0000000", "COHO_0000001", "TEMP_temporary_unclassified"
MINT = ("mint cohort", "mint aggregation")
PLACEHOLDER = "placeholder"
NEWV = MINT + (PLACEHOLDER,)  # verdicts that make a new term
UNCURATED = "AnnotationAssertion(obo:IAO_0000114 coho:{} obo:IAO_0000124)"

LIT = r'"((?:[^"\\]|\\.)*)"'
ACR = 'AnnotationAssertion(Annotation(oboInOwl:hasSynonymType obo:OMO_0003000) oboInOwl:hasRelatedSynonym coho:{} "{}")'
REL = 'AnnotationAssertion(oboInOwl:hasRelatedSynonym coho:{} "{}")'
NOTE = 'AnnotationAssertion(obo:IAO_0000116 coho:{} "{}"@en)'
SUB = ('ObjectPropertyAssertion(Annotation(rdfs:comment "{}") Annotation(oboInOwl:hasDbXref "{}") '
       "coho:isSubCohortOf coho:{} coho:{})")


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def unesc(s):
    return re.sub(r"\\(.)", r"\1", s)


def curie(c):
    return "COHO:" + c.split("_")[1]


def local(c):
    return c.replace("COHO:", "COHO_")


def norm(s):
    """names are compared as the overlapping-synonyms check compares them"""
    return " ".join(s.lower().split())


def split(s, sep="|"):
    return [t.strip() for t in s.split(sep) if t.strip()]


def parse(text):
    terms = {}

    def term(c):
        return terms.setdefault(c, dict(label=None, syn=[], notes=[], dep=False, types=[]))

    for m in re.finditer(r"AnnotationAssertion\((Annotation\(oboInOwl:hasSynonymType obo:OMO_0003000\) )?"
                         r"oboInOwl:has\w+Synonym coho:(COHO_\d+) " + LIT, text):
        term(m.group(2))["syn"].append((unesc(m.group(3)), bool(m.group(1))))
    for m in re.finditer(r"AnnotationAssertion\(rdfs:label coho:(COHO_\d+) " + LIT, text):
        term(m.group(1))["label"] = unesc(m.group(2))
    for m in re.finditer(r"AnnotationAssertion\(obo:IAO_0000116 coho:(COHO_\d+) " + LIT, text):
        term(m.group(1))["notes"].append(unesc(m.group(2)))
    for m in re.finditer(r'AnnotationAssertion\(owl:deprecated coho:(COHO_\d+) "true"', text):
        term(m.group(1))["dep"] = True
    for m in re.finditer(r"^ClassAssertion\(coho:(COHO_\d+|TEMP_temporary_unclassified) coho:(COHO_\d+)\)", text, re.M):
        term(m.group(2))["types"].append(m.group(1))
    return terms


def rows_to_text(rows, delim="\t"):
    buf = io.StringIO()
    csv.writer(buf, delimiter=delim, lineterminator="\n").writerows(rows)
    return buf.getvalue()


def joinnames(xs):
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-row", type=int, required=True)
    ap.add_argument("--provenance", required=True)
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    rows = list(csv.DictReader(open(REVIEW, newline="", encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE))
    for i, x in enumerate(rows, 1):
        x["_n"] = i
    todo = [x for x in rows if x["_n"] >= a.from_row]
    text = EDIT.read_text(encoding="utf-8")
    T = parse(text)
    live = {c for c, t in T.items() if t["types"] and not t["dep"]}
    gaz = {l.split("\t")[0].split(":", 1)[1] for l in open(GAZ, encoding="utf-8") if l.startswith("dbpedia:")}
    problems = []

    # --- IDs: rows to mint, in review order
    top = max(int(c.split("_")[1]) for c in T)
    new = []
    for x in todo:
        if x["verdict"] in NEWV and not x["COHO ID"] and not x["same as"]:
            top += 1
            x["_id"] = "COHO:%07d" % top
            new.append(x)

    def idof(x):
        if x.get("_id"):
            return x["_id"]
        if x["COHO ID"]:
            return x["COHO ID"]
        if x["same as"]:
            return resolve(x["same as"], x)
        return None

    def resolve(ref, exclude=None):
        if ref.startswith("COHO:"):
            if local(ref) not in live:
                problems.append(f"{ref} is not a live COHO term")
            return ref
        pool = [y for y in rows if y is not exclude and y["verdict"] in NEWV + ("existing",) and not y["same as"]]
        c = ([y for y in pool if y["PGS id"] == ref] or [y for y in pool if y["label"] == ref]
             or [y for y in pool if ref in split(y["acronym synonyms"])])
        ids = {idof(y) for y in c}
        if len(ids) != 1 or None in ids:
            problems.append(f"row reference {ref!r} resolves to {sorted(map(str, ids)) or 'nothing'}")
            return None
        return ids.pop()

    # --- checks on the rows to mint
    labels_new = collections.Counter(x["label"] for x in new)
    live_labels = {norm(T[c]["label"]): c for c in live}
    for x in new:
        n = x["_n"]
        want = {"mint aggregation": "cohort aggregation", PLACEHOLDER: "unclassified"}.get(x["verdict"], "cohort")
        if x["type"] != want:
            problems.append(f"row {n}: type {x['type']!r} does not agree with verdict {x['verdict']!r}")
        if not x["label"]:
            problems.append(f"row {n}: no label")
        elif labels_new[x["label"]] > 1:
            problems.append(f"row {n}: label {x['label']!r} is used by another row to mint")
        elif norm(x["label"]) in live_labels:
            problems.append(f"row {n}: label {x['label']!r} is already {curie(live_labels[norm(x['label'])])}")
        if x["verdict"] == PLACEHOLDER:
            continue
        if not (x["definition"] and x["definition source"] and x["drafted by"]):
            problems.append(f"row {n}: definition, its source and its drafter are all needed")
        if not (x["example study"] or x["example PMID"]):
            problems.append(f"row {n}: no example study or paper")
        elif bool(x["example quote"]) != bool(x["example quote URL"]):
            problems.append(f"row {n}: the example's quote and URL go together")
        groups = [g.strip() for g in x["countries"].split(" || ")] if x["countries"] else []
        if x["countries"] and len({len(groups), len(x["location quote"].split(" || ")), len(x["location URL"].split(" || "))}) != 1:
            problems.append(f"row {n}: countries, location quote and location URL have different numbers of groups")
        for c in (c for g in groups for c in split(g)):
            if c not in gaz:
                problems.append(f"row {n}: country {c} is not in {GAZ.name}")
    for x in todo:
        if x["parent"] and x["verdict"] in MINT + ("existing",):
            if x["parent relation"] not in ("isSubCohortOf", "memberOf"):
                problems.append(f"row {x['_n']}: parent relation {x['parent relation']!r}")
            if not (x["parent quote"] and x["parent URL"]):
                problems.append(f"row {x['_n']}: the parent needs a quote and its URL")
    for x in todo:
        if x["same as"]:
            x["_target"] = resolve(x["same as"], x)

    # --- names: of new terms, and added to existing ones
    newids = {local(x["_id"]) for x in new}
    byid = {local(x["_id"]): x for x in new}
    names = {}  # term -> [(name, is_acronym)] after the run, for new terms and additions
    added = collections.defaultdict(list)

    def add(lst, label, s, acr, have=()):
        if s and s != label and s not in have and all(s != e for e, _ in lst):
            lst.append((s, acr))

    for x in new:
        lst = []
        for s in split(x["acronym synonyms"]) + [x["PGS id"]] + split(x["GWAS tags"], ";"):
            add(lst, x["label"], s, True)
        for s in split(x["other synonyms"]):
            add(lst, x["label"], s, False)
        names[local(x["_id"])] = lst
    for x in todo:
        if x["verdict"] not in NEWV + ("existing",):
            continue
        if x["same as"]:
            tid = x.get("_target")
        elif x["verdict"] == "existing":
            tid = x["COHO ID"]
        else:
            continue
        if not tid:
            continue
        tid = local(tid)
        cands = [(s, True) for s in split(x["acronym synonyms"]) + [x["PGS id"]] + split(x["GWAS tags"], ";")]
        if x["same as"]:
            cands.append((x["label"], False))
        cands += [(s, False) for s in split(x["other synonyms"])]
        for s, acr in cands:
            if tid in newids:
                add(names[tid], byid[tid]["label"], s, acr)
            elif tid in T:
                add(added[tid], T[tid]["label"], s, acr, {e for e, _ in T[tid]["syn"]})
            else:
                problems.append(f"row {x['_n']}: {curie(tid)} is not in the edit file")
    added = {k: v for k, v in added.items() if v}

    if problems:
        raise SystemExit("not minted:\n  " + "\n  ".join(dict.fromkeys(problems)))

    # --- shared names after the run
    label = {c: T[c]["label"] for c in live}
    label.update({local(x["_id"]): x["label"] for x in new})
    syns = {c: {s: acr for s, acr, in T[c]["syn"]} for c in live}
    for c, v in added.items():
        syns[c].update(dict(v))
    for c, v in names.items():
        syns[c] = dict(v)
    groups = collections.defaultdict(dict)
    for c, ss in syns.items():
        for s in ss:
            groups[norm(s)].setdefault(c, s)

    def changed(k, c):
        return c in newids or any(norm(s) == k for s, _ in added.get(c, []))

    shared = {k: v for k, v in groups.items() if len(v) > 1 and any(changed(k, c) for c in v)}
    notes, rewrite = collections.defaultdict(list), collections.defaultdict(list)
    for k, v in sorted(shared.items()):
        ids = sorted(v)
        for c in ids:
            s = v[c]
            others = [f"{label[o]} ({curie(o)})" for o in ids if o != c]
            kind = "name" if len(s.split()) >= 3 else "acronym"
            n = f"The {kind} {s} also denotes {joinnames(others)}; this term is {label[c]}."
            old = [m for m in (T[c]["notes"] if c in T else [])
                   if norm(m).startswith((f"the acronym {k} also denotes", f"the name {k} also denotes"))]
            if len(old) > 1:
                raise SystemExit(f"{curie(c)} has {len(old)} notes on {k!r}")
            if old and old[0] != n:
                rewrite[c].append((old[0], n))
            elif not old:
                notes[c].append(n)
    clashes = {c: sorted({curie(o) for k, v in shared.items() if c in v for o in v if o != c}) for c in syns}

    # --- sub-cohort links
    subs = collections.defaultdict(list)
    for x in todo:
        if x["verdict"] in MINT + ("existing",) and x["parent"] and x["parent relation"] == "isSubCohortOf" and not x["same as"]:
            ch, pa = local(idof(x)), local(resolve(x["parent"], x))
            if f"coho:isSubCohortOf coho:{ch} coho:{pa})" not in text:
                subs[ch].append((x["parent quote"], x["parent URL"], pa))

    def synline(c, s, acr):
        return (ACR if acr else REL).format(c, esc(s))

    # --- edit file: additions to existing terms, rewritten notes, declarations, new blocks
    out, cur, ins, nrew = [], None, collections.Counter(), 0
    last_decl = max(i for i, l in enumerate(text.split("\n")) if re.match(r"Declaration\(NamedIndividual\(coho:COHO_\d+\)\)$", l))
    for i, l in enumerate(text.split("\n")):
        m = re.match(r"# Individual: coho:(COHO_\d+) ", l)
        if m:
            cur = m.group(1)
        if cur and cur not in newids and l.startswith(f"AnnotationAssertion(rdfs:label coho:{cur} "):
            for s, acr in added.get(cur, []):
                out.append(synline(cur, s, acr)); ins[cur] += 1
            for n in notes.get(cur, []):
                out.append(NOTE.format(cur, esc(n))); ins[cur] += 1
            for q, u, p in subs.get(cur, []):
                out.append(SUB.format(esc(q), esc(u), cur, p)); ins[cur] += 1
        for o, n in rewrite.get(cur, []):
            if l == NOTE.format(cur, esc(o)):
                l = NOTE.format(cur, esc(n)); nrew += 1
        out.append(l)
        if i == last_decl:
            out += [f"Declaration(NamedIndividual(coho:{local(x['_id'])}))" for x in new]
    for c in set(added) | {c for c in notes if c not in newids} | {c for c in subs if c not in newids}:
        want = len(added.get(c, [])) + len(notes.get(c, [])) + len(subs.get(c, []))
        if ins[c] != want:
            raise SystemExit(f"{curie(c)}: {ins[c]} of {want} lines placed; is its block in the edit file?")
    if nrew != sum(len(v) for v in rewrite.values()):
        raise SystemExit("not every note to rewrite was found")
    blocks = []
    for x in new:
        c = local(x["_id"])
        b = [f"# Individual: coho:{c} ({x['label']})", ""]
        b += [synline(c, s, acr) for s, acr in names[c] if acr] + [synline(c, s, acr) for s, acr in names[c] if not acr]
        b += [NOTE.format(c, esc(n)) for n in notes.get(c, [])]
        if x["verdict"] == PLACEHOLDER:
            b.append(UNCURATED.format(c))
        b.append(f'AnnotationAssertion(rdfs:label coho:{c} "{esc(x["label"])}"@en)')
        typ = {"cohort aggregation": AGGREGATION, "unclassified": UNCLASSIFIED}.get(x["type"], COHORT)
        b.append(f"ClassAssertion(coho:{typ} coho:{c})")
        b += [SUB.format(esc(q), esc(u), c, p) for q, u, p in subs.get(c, [])]
        blocks.append("\n".join(b) + "\n")
    text2 = "\n".join(out)
    anchor = "SubObjectPropertyOf(ObjectPropertyChain("
    if text2.count(anchor) != 1:
        raise SystemExit(f"expected one {anchor!r} line in the edit file")
    k = text2.index(anchor)
    text2 = text2[:k] + "\n".join(blocks) + ("\n" if blocks else "") + text2[k:]

    # --- curated files
    prov = a.provenance
    ex, tit, de, lo, gw, am, pg = [], [], [], [], [], [], []
    titles = {r["PMID"] for r in csv.DictReader(open(CUR / "example_studies_titles.tsv", encoding="utf-8"), delimiter="\t")}
    subset = {l.split(",")[0] for l in open(GWAS_SUBSET, encoding="utf-8")}
    unquoted = []
    for x in new:
        i = x["_id"]
        if x["verdict"] == PLACEHOLDER:
            pg.append([i, "owl:NamedIndividual", "http://www.ebi.ac.uk/coho#PGS_subset", x["label"]])
            continue
        note = f"minted {a.date} from {prov}"
        if not x["example quote"]:
            note += "; no quote: the paper could not be read (see the review's note)"
            unquoted.append(f"{i} {x['label']}")
        ex.append([i, x["example study"], x["example PMID"], note, x["example quote"], x["example quote URL"], ""])
        p = x["example PMID"].removeprefix("PMID:")
        if p and p not in titles and x["example title"]:
            titles.add(p); tit.append([p, x["example title"]])
        de.append([i, x["definition"], x["definition source"], f"written from the cited source when the cohort was minted {a.date} from {prov}", x["drafted by"]])
        if x["countries"]:
            for cs, q, u in zip(x["countries"].split(" || "), x["location quote"].split(" || "), x["location URL"].split(" || ")):
                note = f"minted {a.date} from {prov}"
                if not q.strip():
                    note += "; the country is given by the cohort's name, no quote"
                lo.append([i, cs.strip(), q.strip(), u.strip(), note])
        if x["example study"].startswith("GCST") and i not in subset:
            gw.append([i, "owl:NamedIndividual", "http://www.ebi.ac.uk/coho#GWAS_subset", x["label"]])
    have = {(r["ID"], r["member cohort"]) for r in csv.DictReader(open(ROOT / "src/templates/aggregation_members.tsv", encoding="utf-8"), delimiter="\t")}
    have |= {(r["aggregation_id"], r["member_id"]) for r in csv.DictReader(open(CUR / "aggregation_members_curated.tsv", encoding="utf-8"), delimiter="\t")}
    for x in todo:
        if x["verdict"] in MINT + ("existing",) and x["parent"] and x["parent relation"] == "memberOf" and not x["same as"]:
            key = (resolve(x["parent"], x), idof(x))
            if key not in have:
                have.add(key)
                am.append([*key, x["parent quote"], x["parent URL"], f"membership stated in the source; added {a.date} when the cohorts were minted from {prov}"])

    # --- review: COHO IDs of minted and same-as rows, and clashes
    L = open(REVIEW, newline="", encoding="utf-8").read().split("\n")
    head = L[0].split("\t")
    ci, cc = head.index("COHO ID"), head.index("clashes with")
    nid = 0
    for x in todo:
        f = L[x["_n"]].split("\t")
        v = x.get("_id") or (x.get("_target") if not x["COHO ID"] else None)
        if v:
            f[ci] = v; nid += 1
        t = idof(x) if x["verdict"] in NEWV + ("existing",) else None
        if t and local(t) in clashes:
            f[cc] = "|".join(clashes[local(t)])
        L[x["_n"]] = "\t".join(f)

    print(f"new terms {len(new)} ({new[0]['_id']}–{new[-1]['_id']}), of which placeholders {len(pg)}" if new else "new terms 0")
    print(f"names added to existing terms {sum(len(v) for v in added.values())} on {len(added)} terms; "
          f"editor notes {sum(len(v) for v in notes.values())} new, {nrew} rewritten; "
          f"isSubCohortOf {sum(len(v) for v in subs.values())}; memberships {len(am)}")
    print(f"definitions {len(de)}, examples {len(ex)}, titles {len(tit)}, location lines {len(lo)}, GWAS subset {len(gw)}; review IDs filled {nid}")
    if unquoted:
        print("examples without a quote: " + "; ".join(unquoted))
    if a.dry_run:
        return
    EDIT.write_text(text2, encoding="utf-8")
    for path, rs, delim in ((CUR / "example_studies_curated.tsv", ex, "\t"), (CUR / "example_studies_titles.tsv", tit, "\t"),
                            (CUR / "definitions_curated.tsv", de, "\t"), (CUR / "location_curated.tsv", lo, "\t"),
                            (CUR / "aggregation_members_curated.tsv", am, "\t"), (GWAS_SUBSET, gw, ","), (PGS_SUBSET, pg, ",")):
        if rs:
            t = path.read_text(encoding="utf-8")
            path.write_text(t + ("" if t.endswith("\n") else "\n") + rows_to_text(rs, delim), encoding="utf-8")
    open(REVIEW, "w", newline="", encoding="utf-8").write("\n".join(L))


if __name__ == "__main__":
    main()
