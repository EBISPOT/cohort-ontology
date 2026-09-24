# Curating COHO

Conventions for anyone, human or agent, adding or changing cohort terms. See `docs/workflows/components.md` for the curation pipeline.

## Terms

- Cohorts are OWL named individuals of `cohort` (COHO:0000000) or `cohort aggregation` (COHO:0000001: a consortium, meta-analysis or umbrella that collects cohorts). Never model a cohort as a class.
- The label is the cohort's full name as the cohort itself uses it. Keep any label a database actually tags, however ugly.
- **Acronyms are always included as synonyms**, with synonym type `OMO:0003000` (acronym): the cohort's own acronym, and every tag the GWAS Catalog, PGS Catalog, EGA, MetaboLights or PRIDE uses for it. **Never withhold an acronym because another cohort already uses it.** When two cohorts share an acronym, both terms carry it and both get an `IAO:0000116` editor note of the form "The acronym X also denotes Y (COHO:nnnnnnn); this term is Z." The `overlapping-synonyms` QC check allows a shared synonym only when both terms carry such a note. Notes are for clashes with other cohorts only, not for acronyms that also name a disease, an institution or something else.
- **Capitalisation is significant.** A name that differs from the label, or from another synonym, only in capitalisation is still kept as a synonym: "CATHeterization GENetics" spells out how the acronym CATHGEN is formed, and "Genetic Investigation of ANthropometric Traits" does the same for GIANT. Only an exact duplicate of the label is left out, and the `synonym-as-label` check compares exact strings.
- A cohort that is part of another is linked with `isSubCohortOf`; a cohort that belongs to an aggregation is linked from the aggregation with `hasCohort`, and so is an aggregation that belongs to another (a consortium of consortia). Each such assertion carries a verbatim quote and its source URL.

## Evidence

- Every definition (`IAO:0000115`) is written from a source that was actually read, cites it as `IAO:0000119` (a `PMID:` or a URL), and names the model or person that drafted it, and any that checked it, as `dcterms:contributor` on the definition axiom. Nothing else on a term records who edited it or when.
- Every cohort has an example study (`IAO:0000112`): a study that used the cohort (an EGA study, GWAS Catalog study, MetaboLights study, PRIDE project, or a paper), with a quote naming the cohort. Quotes are copied verbatim from fetched text; PMIDs, accessions and quotes are never reconstructed from memory. If something cannot be verified, say so in the curation table rather than guessing.
- **A cohort in a subset must have an example from that subset's resource**: EGA subset, an EGA study (`EGAS…`); GWAS subset, a GWAS Catalog study (`GCST…`); MetaboLights subset, a MetaboLights study (`MTBLS…`); PRIDE subset, a PRIDE project (`PXD…`). The `subset-example` QC check enforces this. So a cohort has one example per subset it belongs to, or one example if it belongs to none. Put a cohort in a subset only together with an example from that resource; if the resource has no study that used the cohort, the cohort does not belong in that subset.
- Data collection locations use the DBpedia names in `src/templates/gaz_xrefs.tsv`, with a verbatim quote and URL from open-access text; a country may be asserted without a quote only when the cohort's name gives it, and the note says so.
- No "all known studies" cross-references: at most one example per resource.

## Pipeline and build

- Curated evidence lives in `src/curation/*_curated.tsv` (which override the `*_evidence.tsv` files). `example_studies_curated.tsv` takes one line per example (ID, example study, PMID, note, quote, URL); a cohort with curated lines gets exactly those examples and no automatic one, so when you add a second example to a cohort, write its first one there too. The scripts in `src/scripts` turn them into `src/templates/*.tsv`; `om make recreate-components` builds the components. Rows decided in `catalog_cohorts_review.tsv` are minted with `src/scripts/mint_cohorts.py --from-row N` (a dry run first with `--dry-run`). Do not hand-edit generated templates or components.
- Every `om make` invocation carries `IMP=false PAT=false MIR=false`. After any `om make`, run `git status` at the repository root: the root release files (`coho*.owl`, `coho*.obo`, `coho*.json`) are hard links to build outputs and get rewritten; restore them with `git checkout` before committing unless you are cutting a release.
- Work on `main`. Do not push, tag or release unless asked.
