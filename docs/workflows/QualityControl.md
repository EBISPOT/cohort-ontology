# Quality control and Continuous Integration

## Running the checks

```
om make test IMP=false
```

This runs, over the edit file with its imports and components:

- a reasoner check: the ontology must be consistent, with no unsatisfiable classes;
- the [ROBOT report](http://robot.obolibrary.org/report), failing on anything it grades `ERROR`. The report is written to `src/ontology/reports/coho-edit.owl-obo-report.tsv`;
- the constraint violation checks described below, over both the edit file and `coho-full.owl`;
- a check that the released ontology is within the OWL 2 DL profile;
- a check of the ID ranges in `src/ontology/coho-idranges.owl`.

`IMP=false` reuses the committed import modules rather than rebuilding them.

## Continuous Integration

The same checks run on GitHub Actions for every pull request and every push to `main`. The workflow is `.github/workflows/qc.yml`: it installs the owlmake version named by `OWLMAKE_VERSION` and runs `om make test`. To build with a newer owlmake, change that version there.

## Constraint violation checks

We can define custom checks using [SPARQL](https://www.w3.org/TR/rdf-sparql-query/). SPARQL queries define bad modelling patterns (missing labels, misspelt URIs, and many more) in the ontology. If these queries return any results, then the build will fail.

### Steps to add a constraint violation check:

1. Add the SPARQL query in `src/sparql`. The name of the file should end with `-violation.sparql`. Please give a name that helps to understand which violation the query wants to check.
2. Add the name of the new file (without the `-violation.sparql` part) to the `custom_sparql_checks` list under `robot_report` in `owlmake.yaml`:

    ``` yaml
    robot_report:
      custom_sparql_checks:
      - name-of-the-file-check
    ```

The check is part of `om make test` from then on.
