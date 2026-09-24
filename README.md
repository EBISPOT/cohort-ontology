# Cohort Ontology

A lightweight ontology for consistent identification and description of human cohorts across EMBL-EBI resources. It defines a unique cohort identifier with minimal metadata, enabling linkage, discovery, and integration of cohort-related data while supporting both named and implicitly defined cohorts.

![Map of where COHO's cohorts recruited, with each country shaded by its number of cohorts](docs/images/cohort-map.svg)

### The cohorts as a table

[coho-cohorts.csv](coho-cohorts.csv) lists every cohort, cohort aggregation and uncurated placeholder with its names, definition, subsets, example studies, data collection locations, sub-cohorts and aggregations, and the sources of each, one row per term. Each release rewrites it.

### Editors' version

Editors of this ontology should use the edit version, [src/ontology/coho-edit.owl](src/ontology/coho-edit.owl)

### Building

COHO is built with [owlmake](https://github.com/EBISPOT/owlmake) from [owlmake.yaml](owlmake.yaml): `om make test IMP=false` runs the quality control checks and `om make prepare_release -B IMP=false` builds a release. See the [workflows documentation](docs/workflows/index.md).

## Contact

Please use this GitHub repository's [Issue tracker](https://github.com/EBISPOT/cohort-ontology/issues) to request new terms/classes or report errors or specific concerns related to the ontology.


