#!/usr/bin/env python3
"""
Write the exposures of interest of the cohorts as the exposures.owl component,
src/ontology/components/exposures.owl, and the seeds of the exposure import.

Each exposure cohort is typed with an existential restriction on the property
its role calls for (has_participants_with_exposure or
is_designed_to_study_exposure, both sub-properties of
has_exposure_of_interest) over the ECTO term its exposure name is mapped to,
with the evidence as annotations on the assertion: the verbatim sentence
showing the recruitment basis or purpose (rdfs:comment), its source
(oboInOwl:hasDbXref, a URL) and the exposure as the source names it
(IAO:0000116). The component is written directly in OWL functional syntax
rather than through a ROBOT template, because a template cannot annotate a
type assertion.

Sources, in src/curation:
  cohort_exposures.csv            one row per curated cohort: whether it is an
                                  exposure cohort, its role, the categories of
                                  exposure, the exposures as the source names
                                  them (pipe-separated), the quote, its source,
                                  confidence, note, and who classified and
                                  checked it
  distinct_exposures_mapped.csv   one row per distinct exposure name: the ECTO
                                  term it is mapped to (ExO's exposure event,
                                  the root of ECTO, for a name no more specific
                                  than "environmental exposures"), or none

Also written: src/ontology/imports/ecto_terms.txt, the terms the import module
is cut around, one full IRI per line.

A cohort gives one assertion per term its exposure names are mapped to: names
that share a term on one cohort give one assertion carrying each name. An
unmapped name gives nothing and is listed. A row with no quote gives the
assertion with its name note alone, as with locations. A cohort that is not a
live term of the edit file is an error, so the table is kept in step with the
ontology.

Usage: src/scripts/exposures.py
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mint_cohorts as M  # noqa: E402

TABLE = M.ROOT / "src/curation/cohort_exposures.csv"
MAPPED = M.ROOT / "src/curation/distinct_exposures_mapped.csv"
COMPONENT = M.ROOT / "src/ontology/components/exposures.owl"
SEEDS = M.ROOT / "src/ontology/imports/ecto_terms.txt"
ROLES = {
    "defined by exposure": "has_participants_with_exposure",
    "designed to study exposures": "is_designed_to_study_exposure",
}
IRI = {"ECTO": "obo:ECTO_", "ExO": "obo:ExO_"}  # ExO only for ECTO's root, exposure event; EFO is not imported and a disease is not an exposure
ROOT_TERM = "ExO:0000002"
OBO = "http://purl.obolibrary.org/obo/"
HEADER = """Prefix(owl:=<http://www.w3.org/2002/07/owl#>)
Prefix(rdf:=<http://www.w3.org/1999/02/22-rdf-syntax-ns#>)
Prefix(xml:=<http://www.w3.org/XML/1998/namespace>)
Prefix(xsd:=<http://www.w3.org/2001/XMLSchema#>)
Prefix(rdfs:=<http://www.w3.org/2000/01/rdf-schema#>)
Prefix(obo:=<http://purl.obolibrary.org/obo/>)
Prefix(coho:=<http://www.ebi.ac.uk/coho/>)
Prefix(oboInOwl:=<http://www.geneontology.org/formats/oboInOwl#>)


Ontology(<http://www.ebi.ac.uk/coho/components/exposures.owl>

"""


def split(v):
    return [x.strip() for x in (v or "").split("|") if x.strip()]


def term(curie):
    prefix, local = curie.split(":", 1)
    if prefix not in IRI or (prefix == "ExO" and curie != ROOT_TERM):
        raise SystemExit(f"{curie}: not an ECTO term")
    return IRI[prefix] + local


def main():
    T = M.parse(M.EDIT.read_text(encoding="utf-8"))
    with open(MAPPED, newline="", encoding="utf-8") as f:
        terms = {r["name"].lower(): r["id"] for r in csv.DictReader(f)}  # the table keys names case-insensitively
    assertions, unmapped, cohorts, used, bare = [], {}, set(), set(), []
    with open(TABLE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["exposure cohort"] != "yes":
                continue
            prop = ROLES.get(r["exposure role"])
            if not prop:
                raise SystemExit(f"{r['ID']}: unknown role {r['exposure role']!r}")
            c = M.local(r["ID"])
            t = T.get(c)
            if not t or not t["types"] or t["dep"]:
                raise SystemExit(f"{r['ID']} is not a live term")
            named = {}  # term -> the names of the row mapped to it, in the row's order
            for name in split(r["exposures"]):
                if name.lower() not in terms:
                    raise SystemExit(f"{r['ID']}: exposure name {name!r} is not in {MAPPED.name}")
                tid = terms[name.lower()]
                if not tid:
                    unmapped.setdefault(name, []).append(r["ID"])
                    continue
                named.setdefault(tid, []).append(name)
            if not named:
                bare.append(r["ID"])
            for tid, names in named.items():
                notes = []
                if r["quote"].strip():
                    notes.append(f'Annotation(rdfs:comment "{M.esc(r["quote"].strip())}")')
                if r["source"].strip():
                    notes.append(f'Annotation(oboInOwl:hasDbXref "{M.esc(r["source"].strip())}")')
                notes += [f'Annotation(obo:IAO_0000116 "{M.esc(n)}")' for n in names]
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
    SEEDS.write_text("".join(f"<{OBO}{term(t)[4:]}>\n" for t in sorted(used)), encoding="utf-8")
    print(f"{SEEDS.relative_to(M.ROOT)}: {len(used)} terms")
    if unmapped:
        print(f"{len(unmapped)} exposure names have no term, on {sum(len(v) for v in unmapped.values())} rows:")
        for name, ids in sorted(unmapped.items()):
            print(f"  {name}: {', '.join(ids)}")
    if bare:
        print(f"{len(bare)} exposure cohorts have no mapped exposure and get no assertion: {', '.join(bare)}")


if __name__ == "__main__":
    main()
