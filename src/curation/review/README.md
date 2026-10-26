# Reviews

The records of the reviews of 2026-09-22, in which every assertion COHO then made was checked against its sources: one row per cohort (or per aggregation and member) with the assertion, a verdict, the right value where the assertion was wrong, the evidence quote, its source and whether the quote was found in the source, the reviewer's confidence and remark.

- `definitions_evidence.tsv`: the definitions, their sources and supporting quotes.
- `location_evidence.tsv`: the data collection locations (verdicts `correct`, `incomplete`, `wrong`, `unverified`, `unlocated`).
- `aggregation_members_evidence.tsv`: the members of the aggregations, with `include` saying whether the source lists cohorts at all.
- `example_studies_evidence.tsv`: the example studies.

Nothing in the build reads these tables. Until 2026-10-26 the component scripts combined them with the curated tables; on that day every assertion they supplied was folded into the curated tables in `src/curation` (`definitions_curated.tsv`, `location_curated.tsv`, `aggregation_members_curated.tsv`, `example_studies_curated.tsv`, each row noting the review it came from), and the tables moved here as the record of the reviews.
