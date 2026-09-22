![Build Status](https://github.com/EBISPOT/cohort-ontology/actions/workflows/qc.yml/badge.svg)
[![Built with owlmake](https://img.shields.io/static/v1?label=Built%20with&message=owlmake&color=blue&style=flat)](https://github.com/EBISPOT/owlmake)
[![Powered by the ROBOT](https://img.shields.io/static/v1?label=Powered%20by&message=ROBOT&color=green&style=flat)](http://robot.obolibrary.org/)
# Cohort Ontology

A lightweight ontology for consistent identification and description of human cohorts across EMBL-EBI resources. It defines a unique cohort identifier with minimal metadata, enabling linkage, discovery, and integration of cohort-related data while supporting both named and implicitly defined cohorts.

### Editors' version

Editors of this ontology should use the edit version, [src/ontology/coho-edit.owl](src/ontology/coho-edit.owl)

### Building

COHO is built with [owlmake](https://github.com/EBISPOT/owlmake) from [owlmake.yaml](owlmake.yaml): `om make test IMP=false` runs the quality control checks and `om make prepare_release -B IMP=false` builds a release. See the [workflows documentation](docs/workflows/index.md).

## Contact

Please use this GitHub repository's [Issue tracker](https://github.com/EBISPOT/cohort-ontology/issues) to request new terms/classes or report errors or specific concerns related to the ontology.

## Acknowledgements

This ontology repository was created using the [Ontology Development Kit (ODK)](https://github.com/INCATools/ontology-development-kit), and is built with [owlmake](https://github.com/EBISPOT/owlmake).