#!/usr/bin/env python3
"""
Write the diseases of interest of the cohorts as the diseases.owl component,
src/ontology/components/diseases.owl, and the seeds of the disease imports.

Each disease cohort is typed with an existential restriction on the property
its role calls for (has_patients_with, has_participants_at_risk_of or
is_population_study_of, all sub-properties of has_disease_of_interest) over
the ontology term its disease name is mapped to, with the evidence as
annotations on the assertion: the verbatim sentence showing the recruitment
basis or purpose (rdfs:comment), its source (oboInOwl:hasDbXref, a URL) and
the disease as the source names it (IAO:0000116). The component is written
directly in OWL functional syntax rather than through a ROBOT template,
because a template cannot annotate a type assertion.

Sources, in src/curation:
  cohort_diseases.csv            one row per curated cohort: whether it is a
                                 disease cohort, its role, the diseases as the
                                 source names them (pipe-separated), the quote,
                                 its source, confidence, note, and who classified
                                 and checked it
  distinct_diseases_mapped.csv   one row per distinct disease name: the MONDO
                                 (or HP) term it is mapped to, or none

Also written: src/ontology/imports/mondo_terms.txt and hp_terms.txt, the terms
the import modules are cut around, one full IRI per line.

A cohort gives one assertion per disease name that is mapped; an unmapped
name gives nothing and is listed. A row with no quote gives the assertion with
its name note alone, as with locations. A cohort that is not a live term of
the edit file is an error, so the table is kept in step with the ontology.

Usage: src/scripts/diseases.py
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mint_cohorts as M  # noqa: E402

TABLE = M.ROOT / "src/curation/cohort_diseases.csv"
MAPPED = M.ROOT / "src/curation/distinct_diseases_mapped.csv"
COMPONENT = M.ROOT / "src/ontology/components/diseases.owl"
IMPORTS = M.ROOT / "src/ontology/imports"
ROLES = {
    "patients": "has_patients_with",
    "at risk": "has_participants_at_risk_of",
    "population study of disease": "is_population_study_of",
}
IRI = {"MONDO": "obo:MONDO_", "HP": "obo:HP_"}  # EFO is not imported: its disease-location axioms clash with RO under BFO
FULL = {"obo:": "http://purl.obolibrary.org/obo/", "efo:": "http://www.ebi.ac.uk/efo/"}  # seeds are written as full IRIs: EFO is not an OBO prefix
HEADER = """Prefix(owl:=<http://www.w3.org/2002/07/owl#>)
Prefix(rdf:=<http://www.w3.org/1999/02/22-rdf-syntax-ns#>)
Prefix(xml:=<http://www.w3.org/XML/1998/namespace>)
Prefix(xsd:=<http://www.w3.org/2001/XMLSchema#>)
Prefix(rdfs:=<http://www.w3.org/2000/01/rdf-schema#>)
Prefix(obo:=<http://purl.obolibrary.org/obo/>)
Prefix(efo:=<http://www.ebi.ac.uk/efo/>)
Prefix(coho:=<http://www.ebi.ac.uk/coho/>)
Prefix(oboInOwl:=<http://www.geneontology.org/formats/oboInOwl#>)


Ontology(<http://www.ebi.ac.uk/coho/components/diseases.owl>

"""


def split(v):
    return [x.strip() for x in (v or "").split("|") if x.strip()]


def term(curie):
    prefix, local = curie.split(":", 1)
    if prefix not in IRI:
        raise SystemExit(f"{curie}: not a MONDO or HP term")
    return IRI[prefix] + local


def main():
    T = M.parse(M.EDIT.read_text(encoding="utf-8"))
    with open(MAPPED, newline="", encoding="utf-8") as f:
        terms = {r["name"].lower(): r["id"] for r in csv.DictReader(f)}  # the table keys names case-insensitively
    assertions, unmapped, cohorts, used = [], {}, set(), set()
    with open(TABLE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["disease cohort"] != "yes":
                continue
            prop = ROLES.get(r["disease role"])
            if not prop:
                raise SystemExit(f"{r['ID']}: unknown role {r['disease role']!r}")
            c = M.local(r["ID"])
            t = T.get(c)
            if not t or not t["types"] or t["dep"]:
                raise SystemExit(f"{r['ID']} is not a live term")
            for name in split(r["diseases"]):
                if name.lower() not in terms:
                    raise SystemExit(f"{r['ID']}: disease name {name!r} is not in {MAPPED.name}")
                tid = terms[name.lower()]
                if not tid:
                    unmapped.setdefault(name, []).append(r["ID"])
                    continue
                notes = []
                if r["quote"].strip():
                    notes.append(f'Annotation(rdfs:comment "{M.esc(r["quote"].strip())}")')
                if r["source"].strip():
                    notes.append(f'Annotation(oboInOwl:hasDbXref "{M.esc(r["source"].strip())}")')
                notes.append(f'Annotation(obo:IAO_0000116 "{M.esc(name)}")')
                assertions.append((c, tid, f"ClassAssertion({' '.join(notes)} ObjectSomeValuesFrom(coho:{prop} {term(tid)}) coho:{c})"))
                cohorts.add(c)
                used.add(tid)
    assertions.sort()
    lines = [HEADER]
    lines += [f"Declaration(ObjectProperty(coho:{p}))" for p in sorted(ROLES.values())]
    lines += [f"Declaration(Class({term(t)}))" for t in sorted(used)]
    lines += [f"Declaration(NamedIndividual(coho:{c}))" for c in sorted(cohorts)]
    lines.append("")
    lines += [a for _, _, a in assertions]
    lines.append(")\n")
    COMPONENT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{COMPONENT.relative_to(M.ROOT)}: {len(assertions)} assertions on {len(cohorts)} cohorts, {len(used)} terms")
    for prefix in IRI:
        ids = sorted(t for t in used if t.startswith(prefix + ":"))
        path = IMPORTS / f"{prefix.lower()}_terms.txt"
        if ids:
            path.write_text("".join(f"<{FULL[term(t)[:4]]}{term(t)[4:]}>\n" for t in ids), encoding="utf-8")
            print(f"{path.relative_to(M.ROOT)}: {len(ids)} terms")
        elif path.exists():
            print(f"{path.relative_to(M.ROOT)}: no {prefix} term is used any more; remove the import")
    if unmapped:
        print(f"{len(unmapped)} disease names have no term, on {sum(len(v) for v in unmapped.values())} rows:")
        for name, ids in sorted(unmapped.items()):
            print(f"  {name}: {', '.join(ids)}")


if __name__ == "__main__":
    main()
