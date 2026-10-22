#!/usr/bin/env python3
"""
Write the evidence for the cohorts' names as the component
src/ontology/components/names.owl: for every quote in
src/curation/name_evidence.tsv that uses a name the term carries in
coho-edit.owl (its label, or a synonym of any kind), a copy of that label or
synonym assertion annotated with the quote (rdfs:comment) and its sources
(oboInOwl:hasDbXref: the paper's PMID, when the document is a paper, and the
document's URL). The copy keeps the assertion's own annotations (the synonym
type), so it is the same assertion with its evidence; one copy per quote keeps
each quote with its own source. A name that no document uses but a catalogue
does (src/curation/name_sources.tsv, written by name_sources.py) gets a copy
with the catalogue record's URL as oboInOwl:hasDbXref and no quote: the record
is the evidence. A variant of the name its source uses (capitals,
punctuation, a leading "The") carries that source and a note (IAO:0000116) saying
how the source writes it. A quote or record for a name the term no longer carries is
left out and counted.

Usage: src/scripts/names.py
"""

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mint_cohorts as M  # noqa: E402

TABLE = M.ROOT / "src/curation/name_evidence.tsv"
SOURCES = M.ROOT / "src/curation/name_sources.tsv"
COMPONENT = M.ROOT / "src/ontology/components/names.owl"
HEADER = """Prefix(owl:=<http://www.w3.org/2002/07/owl#>)
Prefix(rdf:=<http://www.w3.org/1999/02/22-rdf-syntax-ns#>)
Prefix(xml:=<http://www.w3.org/XML/1998/namespace>)
Prefix(xsd:=<http://www.w3.org/2001/XMLSchema#>)
Prefix(rdfs:=<http://www.w3.org/2000/01/rdf-schema#>)
Prefix(obo:=<http://purl.obolibrary.org/obo/>)
Prefix(coho:=<http://www.ebi.ac.uk/coho/>)
Prefix(oboInOwl:=<http://www.geneontology.org/formats/oboInOwl#>)


Ontology(<http://www.ebi.ac.uk/coho/components/names.owl>

"""
ANN = r'Annotation\((?:[^()"]|"(?:[^"\\]|\\.)*")*\)'
NAME = re.compile(rf'^AnnotationAssertion\(((?:{ANN}\s*)*)(rdfs:label|oboInOwl:has(?:Exact|Related|Broad|Narrow)Synonym) '
                  r'coho:(COHO_\d+) "((?:[^"\\]|\\.)*)"(@\w+)?\)$')


def evidence(quote, pmid, url, note=""):
    notes = [f'Annotation(rdfs:comment "{M.esc(quote)}")'] if quote else []
    notes += [f'Annotation(oboInOwl:hasDbXref "{M.esc(x)}")' for x in (pmid, url) if x]
    if note.startswith(("the source writes it", "the catalogue writes it")):
        # a variant (capitals, punctuation, a leading "The") of the name its source uses: say how the source writes it
        notes.append(f'Annotation(obo:IAO_0000116 "{M.esc(note.split(":")[0])}")')
    return " ".join(notes)


def main():
    names = {}  # (term, name) -> [(existing annotations, property, lang)]
    for line in M.EDIT.read_text(encoding="utf-8").splitlines():
        m = NAME.match(line)
        if m:
            anns, prop, c, value, lang = m.groups()
            names.setdefault((c, M.unesc(value)), []).append((anns.strip(), prop, lang or ""))
    out, gone, terms = [], 0, set()
    with open(TABLE, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            c = M.local(r["ID"])
            found = names.get((c, r["name"]))
            if not found:
                gone += 1
                continue
            for anns, prop, lang in found:
                lead = (anns + " ") if anns else ""
                out.append(f'AnnotationAssertion({lead}{evidence(r["quote"], r["PMID"], r["URL"], r.get("note") or "")} {prop} coho:{c} "{M.esc(r["name"])}"{lang})')
                terms.add(c)
    records = 0
    if SOURCES.exists():
        with open(SOURCES, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                c = M.local(r["ID"])
                found = names.get((c, r["name"]))
                if not found:
                    gone += 1
                    continue
                for anns, prop, lang in found:
                    lead = (anns + " ") if anns else ""
                    out.append(f'AnnotationAssertion({lead}{evidence("", "", r["URL"], r["note"])} {prop} coho:{c} "{M.esc(r["name"])}"{lang})')
                    terms.add(c)
                    records += 1
    out = sorted(set(out))
    lines = [HEADER] + [f"Declaration(NamedIndividual(coho:{c}))" for c in sorted(terms)] + [""] + out + [")\n"]
    COMPONENT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{COMPONENT.relative_to(M.ROOT)}: {len(out) - records} name assertions with a quote and {records} with a catalogue record, on {len(terms)} terms"
          + (f"; {gone} quotes for names the term no longer carries left out" if gone else ""))


if __name__ == "__main__":
    main()
