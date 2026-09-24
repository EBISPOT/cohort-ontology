# Sparql checks

[SPARQL](https://www.w3.org/TR/rdf-sparql-query/) is a W3C standard
query language for RDF. This directory contains useful SPARQL queries
for perfoming over the ontology.

SPARQL can be executed on a triplestore or directly on any OWL
file. The queries here are all executed on either coho-edit.obo or
downstream products in the [ontology](../ontology/) folder. We use
`robot` as this allows easy execution over any Obo-format or OWL file.

We break the queries into 3 categories:

## Constraint Violation checks

These are all named `*violation.sparql`. Checks listed under
`robot_report.custom_sparql_checks` in [owlmake.yaml](../../owlmake.yaml)
run with `om make test IMP=false` and in GitHub Actions. If they return
any results, the build fails.

Consult the individual sparql files to see the intent of the check

COHO completeness and synonym checks:

| Check | Requirement |
| --- | --- |
| `cohort-aggregation-members` (report, WARN) | Every cohort aggregation has `hasCohort` links to at least two distinct, named, active individuals typed as cohorts or cohort aggregations (including subclasses). Anonymous restrictions, self-links, deprecated members and links to other types do not count. Run at WARN by `src/ontology/profile.txt` (the QC report's rule set), not as a failing check: most aggregations' members are not yet COHO terms. |
| `missing-usage-example` | Every COHO individual, including aggregations and temporarily unclassified records, has a non-empty `IAO:0000112` example of usage, expressed as a literal or IRI. |
| `missing-definition` | Every COHO class, individual and property has a non-empty literal `IAO:0000115` definition. This includes temporary classes and local subset properties. |
| `overlapping-synonyms` | Two COHO terms sharing an exact, related, broad or narrow synonym must each have a non-empty literal `IAO:0000116` editor note. Comparison ignores case and normalises whitespace, across synonym types; each term pair is reported once per shared synonym. |

The checked subjects exclude terms marked `owl:deprecated true` and terms from
external namespaces. These checks run on the merged edit ontology and the full
release so imported usage examples and definitions are visible. Definitions
in a curation worksheet do not satisfy QC until they are added to the ontology
or an imported component. Existing gaps will fail QC until curated. Violation
reports are written under `src/ontology/reports/`.

## Construct queries

These are named `construct*.sparql`, and always have the form `CONSTRUCT ...`.

These are used to generate new OWL axioms that can be inserted back
into the ontology.

## Reports

The remaining SPARQL queries are for informative purposes. A subset
may be executed with each release.
