These notes are for the EDITORS of coho

This project was created using the [ontology development kit](https://github.com/INCATools/ontology-development-kit), and is built with [owlmake](https://github.com/EBISPOT/owlmake).

For more details on ontology management, please see the 
[OBO Academy Tutorials](https://oboacademy.github.io/obook/), the
[OBO tutorial](https://github.com/jamesaoverton/obo-tutorial) or the [Gene Ontology Editors Tutorial](https://go-protege-tutorial.readthedocs.io/en/latest/)

The editors' documentation is in [docs/workflows](../../docs/workflows/index.md), published at https://EBISPOT.github.io/cohort-ontology/.

The ontology is built with [owlmake](https://github.com/EBISPOT/owlmake) from [owlmake.yaml](../../owlmake.yaml), at the top of the repository:

```
om make test IMP=false                  # run the quality control checks
om make prepare_release -B IMP=false    # build a release
```
