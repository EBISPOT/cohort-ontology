#!/usr/bin/env python3
"""
Write the evidence components of COHO from the curation tables in src/curation.

Every fact a table records on a cohort becomes a copy of the fact's axiom
annotated with its evidence: the verbatim quote (rdfs:comment) and its source
(oboInOwl:hasDbXref, in the forms sources.py sets out: a paper by its PMID or
DOI, a supplementary file by its paper and the file's URL, a database record by
its public page, a website by its address), one copy per quote so that each
quote keeps its own source. Most components are written as ROBOT templates in
src/templates, which owlmake builds; names, types, diseases and exposures are
written directly in OWL functional syntax, because they copy assertions the
edit file holds (with their synonym types and language tags) or carry class
expressions.

  component    table(s) read                               written
  definitions  definitions_curated.tsv, definition_quotes.tsv   templates/definitions.tsv
  examples     example_studies_curated.tsv, example_studies_titles.tsv   templates/example_studies.tsv
  locations    location_curated.tsv                         templates/locations.tsv
  members      aggregation_members_curated.tsv              templates/aggregation_members.tsv
  participants cohort_participants.tsv                      templates/participants.tsv
  diseases     cohort_diseases.tsv, distinct_diseases_mapped.csv   components/diseases.owl, imports/mondo_terms.txt, hp_terms.txt
  exposures    cohort_exposures.tsv, distinct_exposures_mapped.csv   components/exposures.owl, imports/ecto_terms.txt
  names        name_evidence.tsv, name_sources.tsv          components/names.owl
  types        type_evidence.tsv                            components/types.owl
  subsets      exposome_catalogue.tsv, ihcc_atlas.tsv       templates/GEC.csv, IHCC.csv

The tables have one row per fact and quote: the cohort's ID, what the fact is
(a name and its kind, a type, a country, a number, a disease or exposure as
the source names it, a member, an example study), the quote, the paper it was
read in (PMID) and the address it was read at (read at), a note, and who found
the quote. A row with an empty fact (no country, no number, no disease) records
that the sources give none. A fact on a term the
edit file no longer carries, or on a deprecated term, is left out and counted.
Definitions are one per cohort (definitions_curated.tsv: the text, its source
and the agents that drafted and checked it) with their quotes in
definition_quotes.tsv, attached only while the definition reads as it did when
they were found (its md5). Catalogue-sourced names (name_sources.tsv, written
by name_sources.py) carry the record's URL and no quote.

Usage: src/scripts/components.py [COMPONENT ...]     (default: all, in the order above)
"""

import argparse
import csv
import hashlib
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mint_cohorts as M  # noqa: E402
import sources as S  # noqa: E402

CUR = M.CUR
TEMPLATES = M.ROOT / "src/templates"
COMPONENTS = M.ROOT / "src/ontology/components"
IMPORTS = M.ROOT / "src/ontology/imports"
INDIVIDUAL = "owl:NamedIndividual"

ANN = r'Annotation\((?:[^()"]|"(?:[^"\\]|\\.)*")*\)'
NAME = re.compile(rf'^AnnotationAssertion\(((?:{ANN}\s*)*)(rdfs:label|oboInOwl:has(?:Exact|Related|Broad|Narrow)Synonym) '
                  r'coho:(COHO_\d+) "((?:[^"\\]|\\.)*)"(@\w+)?\)$')


# ---------------------------------------------------------------- shared

def read(path, delimiter="\t"):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


class Edit:
    """What the component writers need to know of the edit file."""

    def __init__(self):
        self.text = M.EDIT.read_text(encoding="utf-8")
        self.terms = M.parse(self.text)
        self.live = {c for c, t in self.terms.items() if t["types"] and not t["dep"]}
        self.deprecated = {M.curie(c) for c, t in self.terms.items() if t["dep"]}
        self.individuals = set(re.findall(r"Declaration\(NamedIndividual\(coho:(COHO_\d+)\)", self.text))
        self.labels = {M.curie(c): t["label"] for c, t in self.terms.items()
                       if c in self.individuals and t["label"] is not None and M.curie(c) not in self.deprecated}
        self.uncurated = set(re.findall(r"AnnotationAssertion\(obo:IAO_0000114 coho:(COHO_\d+) obo:IAO_0000124\)", self.text))

    def is_live(self, cid):
        t = self.terms.get(M.local(cid))
        return bool(t and t["types"] and not t["dep"])


def write_template(path, header, spec, rows, delimiter="\t"):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=delimiter, lineterminator="\n")
        w.writerow(header)
        w.writerow(spec)
        w.writerows(rows)


def owl_header(iri, extra_prefixes=()):
    prefixes = [("owl", "http://www.w3.org/2002/07/owl#"), ("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
                ("xml", "http://www.w3.org/XML/1998/namespace"), ("xsd", "http://www.w3.org/2001/XMLSchema#"),
                ("rdfs", "http://www.w3.org/2000/01/rdf-schema#"), ("obo", "http://purl.obolibrary.org/obo/")]
    prefixes += list(extra_prefixes)
    prefixes += [("coho", "http://www.ebi.ac.uk/coho/"), ("oboInOwl", "http://www.geneontology.org/formats/oboInOwl#")]
    return "".join(f"Prefix({p}:=<{u}>)\n" for p, u in prefixes) + f"\n\nOntology(<{iri}>\n\n"


def write_owl(path, header, declarations, axioms):
    lines = [header] + declarations + [""] + axioms + [")\n"]
    path.write_text("\n".join(lines), encoding="utf-8")


def evidence(quote, paper, read_at, note=""):
    """The axiom annotations for one quote: the quote, its sources (S.cite), and the editor note on how the source
    writes a name (a variant: capitals, punctuation, a leading "The"; a sourced name plus a descriptor) or that it
    describes the cohort without naming it."""
    notes = [f'Annotation(rdfs:comment "{M.esc(quote)}")'] if quote else []
    notes += xrefs(S.cite(paper, read_at))
    if note.startswith(("the source writes it", "the catalogue writes it", "the source describes it")):
        notes.append(f'Annotation(obo:IAO_0000116 "{M.esc(note.split(":")[0])}")')
    return " ".join(notes)


def xrefs(xs):
    return [f'Annotation(oboInOwl:hasDbXref "{M.esc(x)}")' for x in xs]


def cited(paper, read_at, **kw):
    """The sources of one quote as a template cell (split on |)."""
    return "|".join(S.cite(paper, read_at, **kw))


# ---------------------------------------------------------------- components

def definitions(E):
    """IAO:0000115 with its source (IAO:0000119), drafter and checker (dcterms:contributor), one copy per quote."""
    rows = {}
    for r in read(CUR / "definitions_curated.tsv"):
        if r["ID"] in E.deprecated:
            continue
        if r["definition"].strip():
            rows[r["ID"]] = (r["definition"].strip(), r["source"], (r.get("drafted by") or "").strip() or "Claude Fable 5.1 (Anthropic), 2026-09",
                             (r.get("checked by") or "").strip())
        else:
            rows.pop(r["ID"], None)
    quotes, stale = {}, set()
    for r in read(CUR / "definition_quotes.tsv"):
        if r["ID"] not in rows:
            continue
        if r["definition md5"] != hashlib.md5(rows[r["ID"]][0].encode()).hexdigest()[:12]:
            stale.add(r["ID"])
            continue
        quotes.setdefault(r["ID"], []).append((r["quote"], r["PMID"], r["read at"]))
    out = []
    for cid in sorted(rows):
        definition, source, drafted, checked = rows[cid]
        source = "|".join(S.cite_sources(source))
        for quote, pmid, read_at in quotes.get(cid) or [("", "", "")]:
            out.append([cid, INDIVIDUAL, E.labels.get(cid, ""), definition, source, drafted, checked, quote, cited(pmid, read_at)])
    write_template(TEMPLATES / "definitions.tsv",
                   ["ID", "TYPE", "label", "definition", "definition source", "drafted by", "checked by", "quote", "quote source"],
                   ["ID", "TYPE", "", "A IAO:0000115", ">A IAO:0000119 SPLIT=|", ">A dcterms:contributor", ">A dcterms:contributor",
                    ">A rdfs:comment", ">A oio:hasDbXref SPLIT=|"], out)
    missing = sorted(set(E.labels) - set(rows))
    print(f"definitions: {len(rows)} of {len(E.labels)} cohorts defined, {sum(len(v) for v in quotes.values())} quotes on {len(quotes)}"
          + (f"; quotes left off {len(stale)} definitions changed since they were found: {', '.join(sorted(stale))}" if stale else "")
          + (f"; without a definition: {', '.join(f'{c} {E.labels[c]}' for c in missing)}" if missing else ""))


EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
RESOURCES = {"EGA": r"EGAS\d+", "GWAS": r"GCST\d+", "MetaboLight": r"MTBLS\d+", "PRIDE": r"PXD\d+", "PGS": r"PGS\d+"}


def paper_titles(pmids):
    """PMID -> title, from example_studies_titles.tsv, topped up from Europe PMC for PMIDs not yet in it."""
    path = CUR / "example_studies_titles.tsv"
    titles = {r["PMID"]: r["title"] for r in read(path)}
    todo = sorted(set(pmids) - set(titles), key=int)
    for i in range(0, len(todo), 50):
        query = "src:med AND (" + " OR ".join(f"ext_id:{p}" for p in todo[i:i + 50]) + ")"
        url = EUROPEPMC + "?" + urllib.parse.urlencode({"query": query, "format": "json", "resultType": "lite", "pageSize": 100})
        with urllib.request.urlopen(url, timeout=60) as resp:
            for r in json.load(resp)["resultList"]["result"]:
                if r.get("pmid") in todo and r.get("title"):
                    titles[r["pmid"]] = html.unescape(re.sub(r"<[^>]+>", "", r["title"])).strip()
    if todo:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter="\t", lineterminator="\n")
            w.writerow(["PMID", "title"])
            w.writerows(sorted(titles.items(), key=lambda kv: int(kv[0])))
    return titles


def examples(E):
    """IAO:0000112, the example studies: the study (or its paper), with the paper's PMID and title and the quote
    naming the cohort on the axiom. A cohort in a subset needs an example from that subset's resource."""
    curated = defaultdict(list)
    for r in read(CUR / "example_studies_curated.tsv"):
        curated[r["ID"]].append((r["example study"].strip(), (r["PMID"] or "").strip().removeprefix("PMID:"),
                                 (r.get("quote") or "").strip(), (r.get("read at") or "").strip(), (r.get("title") or "").strip()))
    chosen = {}
    for cid in sorted(E.labels, key=M.local):
        if cid in curated:
            chosen[cid] = [e for e in curated[cid] if e[0] or e[1]]
    titles = paper_titles(pmid for es in chosen.values() for _, pmid, *_ in es if pmid)
    untitled = sorted({pmid for es in chosen.values() for _, pmid, *_ in es if pmid and pmid not in titles})
    if untitled:
        print("examples: no title found for PMID " + ", ".join(untitled), file=sys.stderr)
    out = []
    for cid, es in chosen.items():
        for acc, pmid, quote, read_at, given in es:
            paper = f"PMID:{pmid}" if pmid else ""
            # the quote's own source beside the example's paper: the record, supplement or website it was read at
            # (an address of the example's paper itself adds nothing)
            source = "|".join(x for x in S.cite(paper, read_at, copies=False) if x != paper)
            out.append([cid, INDIVIDUAL, E.labels[cid], acc or paper, paper, titles.get(pmid) or given, quote, source, "curated"])
    write_template(TEMPLATES / "example_studies.tsv",
                   ["ID", "TYPE", "label", "example study", "PMID", "title", "evidence", "evidence source", "source"],
                   ["ID", "TYPE", "", "A IAO:0000112", ">A oboInOwl:hasDbXref", ">A dcterms:title", ">A rdfs:comment", ">A oboInOwl:hasDbXref SPLIT=|", ""], out)
    subsets = defaultdict(list)
    for s in RESOURCES:
        for r in list(csv.reader(open(TEMPLATES / f"{s}.csv", encoding="utf-8")))[2:]:
            subsets[r[0]].append(s)
    done = {cid for cid, es in chosen.items() if es}
    missing = [c for c in E.labels if c not in done and M.local(c) not in E.uncurated]
    resource = lambda acc: next((s for s, pat in RESOURCES.items() if re.fullmatch(pat, acc or "")), "")
    gaps = [(s, c) for c in E.labels if M.local(c) not in E.uncurated for s in subsets[c] if s not in {resource(e[0]) for e in chosen.get(c, [])}]
    print(f"examples: {len(done)} of {len(E.labels)} cohorts have an example, {len(out)} examples"
          + (f"; without (not placeholders): {', '.join(f'{c} {E.labels[c]}' for c in missing)}" if missing else "")
          + (f"; subset members without an example from the resource: {', '.join(f'{s} {c}' for s, c in gaps)}" if gaps else ""))


def locations(E):
    """has_data_collection_location, one assertion per cohort and country, with the quote saying where participants
    were recruited; the country names are the DBpedia names of gaz_xrefs.tsv."""
    with open(M.GAZ, encoding="utf-8") as f:
        known = {r[0].split(":", 1)[1] for r in list(csv.reader(f, delimiter="\t"))[2:]}
    rows = defaultdict(list)
    for r in read(CUR / "location_curated.tsv"):
        if r["ID"] not in E.deprecated:
            rows[r["ID"]].append(r)
    unknown = {r["country"] for rs in rows.values() for r in rs if r["country"] and r["country"] not in known}
    if unknown:
        raise SystemExit(f"countries missing from {M.GAZ.name}: {sorted(unknown)}")
    out, located = [], set()
    for cid in sorted(rows):
        for r in rows[cid]:
            if r["country"]:
                out.append([cid, INDIVIDUAL, E.labels.get(cid, ""), f"dbpedia:{r['country']}", r["quote"], cited(r["PMID"], r["read at"])])
                located.add(cid)
    write_template(TEMPLATES / "locations.tsv", ["ID", "TYPE", "label", "data collection location", "evidence", "source"],
                   ["ID", "TYPE", "", "I coho:has_data_collection_location", ">A rdfs:comment", ">A oio:hasDbXref SPLIT=|"], out)
    unlocated = sorted(c for c in E.labels if c not in located)
    print(f"locations: {len(located)} cohorts located, {len(out)} locations; {len(unlocated)} unlocated")


def members(E):
    """hasCohort from each aggregation to each member, with the quote naming the member; a row whose note starts
    with "remove" drops the membership."""
    links = {}
    for r in read(CUR / "aggregation_members_curated.tsv"):
        key = (r["aggregation_id"], r["member_id"])
        if r["aggregation_id"] in E.deprecated or r["member_id"] in E.deprecated:
            continue
        if r["note"].lower().startswith("remove"):
            links.pop(key, None)
        else:
            links[key] = (r["quote"], cited(r["PMID"], r["read at"]))
    out = [[agg, INDIVIDUAL, E.labels.get(agg, ""), member, quote, source] for (agg, member), (quote, source) in sorted(links.items())]
    write_template(TEMPLATES / "aggregation_members.tsv", ["ID", "TYPE", "label", "member cohort", "evidence", "source"],
                   ["ID", "TYPE", "", "I coho:hasCohort", ">A rdfs:comment", ">A oio:hasDbXref SPLIT=|"], out)
    print(f"members: {len(links)} memberships of {len({a for a, _ in links})} aggregations")


NUMBERS = [("participants", "numberOfParticipants"), ("cases", "numberOfCases"), ("controls", "numberOfControls")]


def participants(E):
    """numberOfParticipants, numberOfCases and numberOfControls, each with the sentence stating the number, its source
    and what the number counts (IAO:0000116). Every number is copied as the table gives it; nothing is computed."""
    by_cohort = defaultdict(dict)
    for r in read(CUR / "cohort_participants.tsv"):
        if not r["number"]:
            continue
        if r["number"] not in dict(NUMBERS):
            raise SystemExit(f"{r['ID']}: unknown number {r['number']!r}")
        if not re.fullmatch(r"[0-9]+", r["value"].strip()):
            raise SystemExit(f"{r['ID']}: {r['number']} {r['value']!r} is not an integer")
        if not E.is_live(r["ID"]):
            raise SystemExit(f"{r['ID']} is not a live term")
        if not (r["PMID"].strip() or r["read at"].strip()):
            raise SystemExit(f"{r['ID']}: a number without a source")
        if r["number"] in by_cohort[r["ID"]]:
            raise SystemExit(f"{r['ID']}: two {r['number']} numbers")
        by_cohort[r["ID"]][r["number"]] = r
    out = []
    for cid in sorted(by_cohort):
        row = [cid, INDIVIDUAL, E.labels.get(cid, "")]
        for k, _ in NUMBERS:
            r = by_cohort[cid].get(k)
            row += [r["value"].strip(), r["quote"], cited(r["PMID"].strip(), r["read at"].strip()), r["counts"]] if r else ["", "", "", ""]
        out.append(row)
    header, spec = ["ID", "TYPE", "label"], ["ID", "TYPE", ""]
    for k, prop in NUMBERS:
        header += [k, f"{k} evidence", f"{k} source", f"{k} note"]
        spec += [f"AT coho:{prop}^^xsd:integer", ">A rdfs:comment", ">A oio:hasDbXref SPLIT=|", ">A IAO:0000116"]
    write_template(TEMPLATES / "participants.tsv", header, spec, out)
    print(f"participants: {len(out)} cohorts with a number; " + ", ".join(f"{k} {sum(1 for c in by_cohort.values() if k in c)}" for k, _ in NUMBERS))


def mapping(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {r["name"].lower(): r["id"] for r in csv.DictReader(f)}  # the table keys names case-insensitively


DISEASE_ROLES = {"patients": "has_patients_with", "at risk": "has_participants_at_risk_of", "population study of disease": "is_population_study_of"}
EXPOSURE_ROLES = {"defined by exposure": "has_participants_with_exposure", "designed to study exposures": "is_designed_to_study_exposure"}
OBO = "http://purl.obolibrary.org/obo/"


def diseases(E):
    """Types of the form `has_patients_with some D` (or has_participants_at_risk_of, is_population_study_of) over the
    MONDO or HP term each disease name is mapped to, the quote and the name on the assertion; and the import seeds."""
    terms = mapping(CUR / "distinct_diseases_mapped.csv")
    assertions, unmapped, cohorts, used = [], defaultdict(list), set(), set()
    for r in read(CUR / "cohort_diseases.tsv"):
        if r["disease cohort"] != "yes" or not r["disease"].strip():
            continue
        prop = DISEASE_ROLES.get(r["disease role"])
        if not prop:
            raise SystemExit(f"{r['ID']}: unknown role {r['disease role']!r}")
        if not E.is_live(r["ID"]):
            raise SystemExit(f"{r['ID']} is not a live term")
        name = r["disease"].strip()
        if name.lower() not in terms:
            raise SystemExit(f"{r['ID']}: disease name {name!r} is not in distinct_diseases_mapped.csv")
        tid = terms[name.lower()]
        if not tid:
            unmapped[name].append(r["ID"])
            continue
        prefix, local = tid.split(":", 1)
        if prefix not in ("MONDO", "HP"):
            raise SystemExit(f"{tid}: not a MONDO or HP term")
        c, t = M.local(r["ID"]), f"obo:{prefix}_{local}"
        notes = ([f'Annotation(rdfs:comment "{M.esc(r["quote"].strip())}")'] if r["quote"].strip() else []) + xrefs(S.cite(r["PMID"].strip(), r["read at"].strip()))
        notes.append(f'Annotation(obo:IAO_0000116 "{M.esc(name)}")')
        assertions.append((c, tid, f"ClassAssertion({' '.join(notes)} ObjectSomeValuesFrom(coho:{prop} {t}) coho:{c})"))
        cohorts.add(c)
        used.add(tid)
    assertions.sort()
    term = lambda tid: "obo:" + tid.replace(":", "_", 1)
    declarations = [f"Declaration(ObjectProperty(coho:{p}))" for p in sorted(DISEASE_ROLES.values())]
    declarations += [f"Declaration(Class({term(t)}))" for t in sorted(used)]
    declarations += [f"Declaration(NamedIndividual(coho:{c}))" for c in sorted(cohorts)]
    write_owl(COMPONENTS / "diseases.owl", owl_header("http://www.ebi.ac.uk/coho/components/diseases.owl", [("efo", "http://www.ebi.ac.uk/efo/")]),
              declarations, [a for _, _, a in assertions])
    for prefix in ("MONDO", "HP"):
        ids = sorted(t for t in used if t.startswith(prefix + ":"))
        path = IMPORTS / f"{prefix.lower()}_terms.txt"
        if ids:
            path.write_text("".join(f"<{OBO}{t.replace(':', '_', 1)}>\n" for t in ids), encoding="utf-8")
        elif path.exists():
            print(f"diseases: no {prefix} term is used any more; remove the import")
    print(f"diseases: {len(assertions)} assertions on {len(cohorts)} cohorts, {len(used)} terms"
          + (f"; {len(unmapped)} names without a term: " + ", ".join(f"{n} ({', '.join(ids)})" for n, ids in sorted(unmapped.items())) if unmapped else ""))


def exposures(E):
    """Types of the form `has_participants_with_exposure some X` (or is_designed_to_study_exposure) over the ECTO term
    each exposure name is mapped to; names of one cohort mapped to one term give one assertion carrying each name."""
    terms = mapping(CUR / "distinct_exposures_mapped.csv")
    groups = {}  # (cohort, term) -> (prop, quote, PMID, read at, [names])
    unmapped, bare, order = defaultdict(list), [], []
    for r in read(CUR / "cohort_exposures.tsv"):
        if r["exposure cohort"] != "yes":
            continue
        prop = EXPOSURE_ROLES.get(r["exposure role"])
        if not prop:
            raise SystemExit(f"{r['ID']}: unknown role {r['exposure role']!r}")
        if not E.is_live(r["ID"]):
            raise SystemExit(f"{r['ID']} is not a live term")
        name = r["exposure"].strip()
        if not name:
            if r["ID"] not in order:
                order.append(r["ID"])
            continue
        if name.lower() not in terms:
            raise SystemExit(f"{r['ID']}: exposure name {name!r} is not in distinct_exposures_mapped.csv")
        tid = terms[name.lower()]
        if r["ID"] not in order:
            order.append(r["ID"])
        if not tid:
            unmapped[name].append(r["ID"])
            continue
        prefix = tid.split(":", 1)[0]
        if prefix not in ("ECTO", "ExO") or (prefix == "ExO" and tid != "ExO:0000002"):
            raise SystemExit(f"{tid}: not an ECTO term")
        key = (M.local(r["ID"]), tid)
        if key not in groups:
            groups[key] = (prop, r["quote"].strip(), r["PMID"].strip(), r["read at"].strip(), [])
        groups[key][4].append(name)
    mapped_cohorts = {c for c, _ in groups}
    bare = [cid for cid in order if M.local(cid) not in mapped_cohorts]
    assertions, used = [], set()
    for (c, tid), (prop, quote, paper, read_at, names) in groups.items():
        t = "obo:" + tid.replace(":", "_", 1)
        notes = ([f'Annotation(rdfs:comment "{M.esc(quote)}")'] if quote else []) + xrefs(S.cite(paper, read_at))
        notes += [f'Annotation(obo:IAO_0000116 "{M.esc(n)}")' for n in names]
        assertions.append((c, tid, f"ClassAssertion({' '.join(notes)} ObjectSomeValuesFrom(coho:{prop} {t}) coho:{c})"))
        used.add(tid)
    assertions.sort()
    term = lambda tid: "obo:" + tid.replace(":", "_", 1)
    declarations = [f"Declaration(ObjectProperty(coho:{p}))" for p in sorted(EXPOSURE_ROLES.values())]
    declarations += [f"Declaration(Class({term(t)}))" for t in sorted(used)]
    declarations += [f"Declaration(NamedIndividual(coho:{c}))" for c in sorted(mapped_cohorts)]
    write_owl(COMPONENTS / "exposures.owl", owl_header("http://www.ebi.ac.uk/coho/components/exposures.owl"), declarations, [a for _, _, a in assertions])
    (IMPORTS / "ecto_terms.txt").write_text("".join(f"<{OBO}{t.replace(':', '_', 1)}>\n" for t in sorted(used)), encoding="utf-8")
    print(f"exposures: {len(assertions)} assertions on {len(mapped_cohorts)} cohorts, {len(used)} terms"
          + (f"; {len(unmapped)} names without a term: " + ", ".join(f"{n} ({', '.join(ids)})" for n, ids in sorted(unmapped.items())) if unmapped else "")
          + (f"; {len(bare)} exposure cohorts with no mapped exposure get no assertion: {', '.join(bare)}" if bare else ""))


def names(E):
    """Copies of the label and synonym assertions of the edit file, each with one quote and its sources, or with a
    catalogue record's URL alone; a note says how the source writes a variant."""
    carried = {}  # (term, name) -> [(existing annotations, property, lang)]
    for line in E.text.splitlines():
        m = NAME.match(line)
        if m:
            anns, prop, c, value, lang = m.groups()
            carried.setdefault((c, M.unesc(value)), []).append((anns.strip(), prop, lang or ""))
    out, gone, terms, records = [], 0, set(), 0
    for table, record in ((CUR / "name_evidence.tsv", False), (CUR / "name_sources.tsv", True)):
        for r in read(table):
            c = M.local(r["ID"])
            found = carried.get((c, r["name"]))
            if not found:
                gone += 1
                continue
            ev = evidence("", "", r["URL"], r["note"]) if record else evidence(r["quote"], r["PMID"], r["read at"], r.get("note") or "")
            for anns, prop, lang in found:
                lead = (anns + " ") if anns else ""
                out.append(f'AnnotationAssertion({lead}{ev} {prop} coho:{c} "{M.esc(r["name"])}"{lang})')
                terms.add(c)
                records += record
    out = sorted(set(out))
    write_owl(COMPONENTS / "names.owl", owl_header("http://www.ebi.ac.uk/coho/components/names.owl"),
              [f"Declaration(NamedIndividual(coho:{c}))" for c in sorted(terms)], out)
    print(f"names: {len(out) - records} name assertions with a quote and {records} with a catalogue record, on {len(terms)} terms"
          + (f"; {gone} quotes for names the term no longer carries left out" if gone else ""))


TYPES = {"cohort": "COHO_0000000", "cohort aggregation": "COHO_0000001"}


def types(E):
    """Copies of the class assertions to cohort or cohort aggregation, each with one quote and its sources."""
    have = set(re.findall(r"^ClassAssertion\(coho:(COHO_000000[01]) coho:(COHO_\d+)\)$", E.text, re.M))
    out, gone, terms = [], 0, set()
    for r in read(CUR / "type_evidence.tsv"):
        c, t = M.local(r["ID"]), TYPES.get(r["type"])
        if (t, c) not in have:
            gone += 1
            continue
        out.append(f'ClassAssertion({evidence(r["quote"], r["PMID"], r["read at"])} coho:{t} coho:{c})')
        terms.add(c)
    out = sorted(set(out))
    write_owl(COMPONENTS / "types.owl", owl_header("http://www.ebi.ac.uk/coho/components/types.owl"),
              [f"Declaration(NamedIndividual(coho:{c}))" for c in sorted(terms)], out)
    print(f"types: {len(out)} type assertions with a quote on {len(terms)} terms" + (f"; {gone} quotes for a type the term no longer has left out" if gone else ""))


CATALOGUES = [("exposome_catalogue.tsv", "GEC", set()), ("ihcc_atlas.tsv", "IHCC", {"IHCC"})]


def subsets(E):
    """The catalogue subsets: one line per live term an entry of the catalogue resolved to."""
    for record, name, skip in CATALOGUES:
        terms = {}
        for r in read(CUR / record):
            if not r["COHO ID"] or r["catalogue id"] in skip:
                continue
            if not E.is_live(r["COHO ID"]):
                raise SystemExit(f"{record}: {r['COHO ID']} is not a live term")
            terms[r["COHO ID"]] = E.terms[M.local(r["COHO ID"])]["label"]
        write_template(TEMPLATES / f"{name}.csv", ["ID", "TYPE", "subset", "label"], ["ID", "TYPE", "AI oboInOwl:inSubset", ""],
                       [[c, INDIVIDUAL, f"http://www.ebi.ac.uk/coho#{name}_subset", terms[c]] for c in sorted(terms)], delimiter=",")
        print(f"subsets: {name} {len(terms)} terms")


ALL = {"definitions": definitions, "examples": examples, "locations": locations, "members": members, "participants": participants,
       "diseases": diseases, "exposures": exposures, "names": names, "types": types, "subsets": subsets}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("components", nargs="*", choices=list(ALL), metavar="COMPONENT", help=", ".join(ALL))
    a = ap.parse_args()
    E = Edit()
    for name in a.components or list(ALL):
        ALL[name](E)


if __name__ == "__main__":
    main()
