# Repository structure

The main kinds of files in the repository:

1. The build configuration, [`owlmake.yaml`](BuildConfiguration.md)
2. The edit file, `src/ontology/coho-edit.owl`: the only ontology file edited by hand
3. Release files
4. Imports
5. [Components](#components)

## Release files
Release file are the file that are considered part of the official ontology release and to be used by the community. They are at the top of the repository: `coho.owl` and `coho.obo` (the primary release, the same as `coho-full.owl`), `coho-full.owl` (the ontology with its imports, classified) and `coho-base.owl` (only the axioms that belong to COHO itself). `coho-cohorts.csv` is the same cohorts as a table, one row per term (`src/scripts/cohort_table.py`).

## Imports
Imports are subsets of external ontologies that contain terms and axioms you would like to re-use in your ontology. These are considered "external", like dependencies in software development, and are not included in your "base" product, the release file which contains only those axioms that you personally maintain.

These are the current imports in COHO

| Import | URL | Type |
| ------ | --- | ---- |
| ro | http://purl.obolibrary.org/obo/ro.owl | slme |
| omo | http://purl.obolibrary.org/obo/omo.owl | mirror |
| NCIT | http://purl.obolibrary.org/obo/NCIT.owl | slme |

See [Imports management](UpdateImports.md).

## Components
Components, in contrast to imports, are considered full members of the ontology. This means that any axiom in a component is also included in the ontology base - which means it is considered _native_ to the ontology. While this sounds complicated, consider this: conceptually, no component should be part of more than one ontology. If that seems to be the case, we are most likely talking about an import. Components are often not needed for ontologies, but there are some use cases:

1. There is an automated process that generates and re-generates a part of the ontology
2. A part of the ontology is managed in ROBOT templates
3. The expressivity of the component is higher than the format of the edit file. For example, people still choose to manage their ontology in OBO format (they should not) missing out on a lot of owl features. They may choose to manage logic that is beyond OBO in a specific OWL component.

These are the components in COHO

| Filename | Built from |
| -------- | ---------- |
| gaz_xrefs.owl | `src/templates/gaz_xrefs.tsv` |
| GWAS.owl | `src/templates/GWAS.csv` |
| MetaboLight.owl | `src/templates/MetaboLight.csv` |
| EGA.owl | `src/templates/EGA.csv` |
| PRIDE.owl | `src/templates/PRIDE.csv` |

See [Components management](components.md).
