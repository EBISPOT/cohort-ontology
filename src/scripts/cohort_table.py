#!/usr/bin/env python3
"""
Write coho-cohorts.csv, the table of the cohorts and their metadata, from the
edit file and its components. `om make prepare_release` rewrites it (the
table's target in owlmake.yaml), so each release commits the table of its own
data.

Sources:
  src/ontology/tmp/coho-cohorts.nt   the edit file merged with its components
                                     (and imports), as N-Triples
  src/templates/definitions.tsv      the definitions and their sources, which
                                     carry the curated source order

One row per cohort, cohort aggregation or temporary unclassified placeholder,
sorted by ID. Multiple values in a cell are sorted and joined with |, as in
the curation tables.

Usage: src/scripts/cohort_table.py
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRIPLES = ROOT / "src/ontology/tmp/coho-cohorts.nt"
DEFINITIONS = ROOT / "src/templates/definitions.tsv"
CSV = ROOT / "coho-cohorts.csv"

COHO = "http://www.ebi.ac.uk/coho/"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
SEE_ALSO = "http://www.w3.org/2000/01/rdf-schema#seeAlso"
EXAMPLE = "http://purl.obolibrary.org/obo/IAO_0000112"
CURATION_STATUS = "http://purl.obolibrary.org/obo/IAO_0000114"
UNCURATED = "http://purl.obolibrary.org/obo/IAO_0000124"
SYNONYM = "http://www.geneontology.org/formats/oboInOwl#hasRelatedSynonym"
SYNONYM_TYPE = "http://www.geneontology.org/formats/oboInOwl#hasSynonymType"
ACRONYM = "http://purl.obolibrary.org/obo/OMO_0003000"
IN_SUBSET = "http://www.geneontology.org/formats/oboInOwl#inSubset"
XREF = "http://www.geneontology.org/formats/oboInOwl#hasDbXref"
LOCATION = COHO + "has_data_collection_location"
NUMBERS = {
    COHO + "numberOfParticipants": "participants",
    COHO + "numberOfCases": "cases",
    COHO + "numberOfControls": "controls",
}
SUB_COHORT_OF = COHO + "isSubCohortOf"
HAS_COHORT = COHO + "hasCohort"
AXIOM = "http://www.w3.org/2002/07/owl#Axiom"
ANNOTATED_SOURCE = "http://www.w3.org/2002/07/owl#annotatedSource"
ANNOTATED_PROPERTY = "http://www.w3.org/2002/07/owl#annotatedProperty"
ANNOTATED_TARGET = "http://www.w3.org/2002/07/owl#annotatedTarget"

# row types, in the order their classes are declared
TYPES = {
    COHO + "COHO_0000000": "cohort",
    COHO + "COHO_0000001": "cohort aggregation",
    COHO + "TEMP_temporary_unclassified": "temporary unclassified",
}

TRIPLE = re.compile(r"^(<[^>]*>|_:\S+) <([^>]*)> (.*?) \.$")
UNESCAPE = re.compile(r"\\(?:u([0-9A-Fa-f]{4})|U([0-9A-Fa-f]{8})|(.))")
PLAIN = {"t": "\t", "n": "\n", "r": "\r", '"': '"', "\\": "\\"}


def unescape(text):
    return UNESCAPE.sub(
        lambda m: chr(int(m.group(1) or m.group(2), 16))
        if m.group(1) or m.group(2)
        else PLAIN.get(m.group(3), m.group(3)),
        text,
    )


def term(token):
    """An N-Triples term as (kind, value): IRI and bnode values are the bare
    identifier, a literal's is its text without language tag or datatype."""
    if token.startswith("<"):
        return "iri", token[1:-1]
    if token.startswith("_:"):
        return "bnode", token
    match = re.match(r'^"(.*)"(?:@[A-Za-z-]+|\^\^<[^>]*>)?$', token, re.S)
    if not match:
        raise SystemExit(f"unparsed N-Triples object: {token[:80]}")
    return "literal", unescape(match.group(1))


def read_triples():
    """(subject, predicate, (kind, value)) for every triple in the merge."""
    with open(TRIPLES, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            match = TRIPLE.match(line)
            if not match:
                raise SystemExit(f"unparsed N-Triples line: {line[:80]}")
            subject = match.group(1)
            subject = subject[1:-1] if subject.startswith("<") else subject
            yield subject, match.group(2), term(match.group(3))


def curie(iri):
    return "COHO:" + iri[len(COHO) + len("COHO_") :]


def cell(values):
    return "|".join(sorted(values))


def main():
    by_subject = defaultdict(lambda: defaultdict(list))
    for subject, predicate, obj in read_triples():
        by_subject[subject][predicate].append(obj)

    # the synonyms asserted to be acronyms: axiom annotations typing the
    # synonym with OMO:0003000
    acronyms = set()
    for subject, properties in by_subject.items():
        if not subject.startswith("_:"):
            continue
        if ("iri", AXIOM) not in properties.get(RDF_TYPE, []):
            continue
        if ("iri", SYNONYM) not in properties.get(ANNOTATED_PROPERTY, []):
            continue
        if ("iri", ACRONYM) not in properties.get(SYNONYM_TYPE, []):
            continue
        for kind, source in properties.get(ANNOTATED_SOURCE, []):
            for target_kind, text in properties.get(ANNOTATED_TARGET, []):
                if kind == "iri" and target_kind == "literal":
                    acronyms.add((source, text))

    # the sources of each cohort's numbers of participants, cases and controls:
    # axiom annotations on the number assertions
    number_sources = defaultdict(set)
    for subject, properties in by_subject.items():
        if not subject.startswith("_:"):
            continue
        if ("iri", AXIOM) not in properties.get(RDF_TYPE, []):
            continue
        if not any(("iri", p) in properties.get(ANNOTATED_PROPERTY, []) for p in NUMBERS):
            continue
        for kind, source in properties.get(ANNOTATED_SOURCE, []):
            for source_kind, value in properties.get(XREF, []):
                if kind == "iri" and source_kind == "literal":
                    number_sources[source].add(value)

    # each cohort's aggregations, inverted from the aggregations' hasCohort
    member_of = defaultdict(set)
    for subject, properties in by_subject.items():
        for kind, target in properties.get(HAS_COHORT, []):
            if kind == "iri":
                member_of[target].add(subject)

    definitions = {}
    with open(DEFINITIONS, encoding="utf-8", newline="") as f:
        for row in list(csv.reader(f, delimiter="\t"))[2:]:
            definitions[row[0]] = (row[3], row[4])

    def label(iri):
        for kind, value in by_subject[iri].get(LABEL, []):
            if kind == "literal":
                return value
        return iri.rsplit("/", 1)[-1].replace("_", " ")

    rows = []
    for subject, properties in by_subject.items():
        types = [t for kind, t in properties.get(RDF_TYPE, []) if t in TYPES]
        if subject.startswith("_:") or not types:
            continue
        of = lambda predicate: properties.get(predicate, [])
        synonyms = [v for kind, v in of(SYNONYM) if kind == "literal"]
        definition, sources = definitions.get(curie(subject), ("", ""))
        rows.append(
            {
                "ID": curie(subject),
                "label": label(subject),
                "type": TYPES[min(types, key=list(TYPES).index)],
                "curation status": "uncurated"
                if ("iri", UNCURATED) in of(CURATION_STATUS)
                else "",
                "acronyms": cell(s for s in synonyms if (subject, s) in acronyms),
                "other synonyms": cell(
                    s for s in synonyms if (subject, s) not in acronyms
                ),
                "definition": definition,
                "definition source": sources,
                **{
                    column: cell(v for kind, v in of(p) if kind == "literal")
                    for p, column in NUMBERS.items()
                },
                "participants source": cell(number_sources[subject]),
                "data collection locations": cell(
                    label(v) for kind, v in of(LOCATION) if kind == "iri"
                ),
                "sub-cohort of": cell(
                    curie(v) for kind, v in of(SUB_COHORT_OF) if kind == "iri"
                ),
                "member of": cell(curie(v) for v in member_of[subject]),
                "subsets": cell(
                    v.rsplit("#", 1)[-1] for kind, v in of(IN_SUBSET) if kind == "iri"
                ),
                "cross references": cell(v for kind, v in of(XREF)),
                "see also": cell(v for kind, v in of(SEE_ALSO)),
                "example studies": cell(v for kind, v in of(EXAMPLE)),
            }
        )

    rows.sort(key=lambda r: r["ID"])
    with open(CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{CSV.relative_to(ROOT)}: {len(rows)} rows")


if __name__ == "__main__":
    main()
