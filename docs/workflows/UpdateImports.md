# Update Imports Workflow

This page discusses how to update the contents of your imports, like adding or removing terms. To change which ontologies are imported, edit `import_group` in `owlmake.yaml` and run `om update-repo`, then [refresh the imports](#refresh-imports); see [Build configuration](BuildConfiguration.md).

COHO imports terms from these ontologies, listed under `import_group` in `owlmake.yaml`:

| Import | URL | Type |
| ------ | --- | ---- |
| ro | http://purl.obolibrary.org/obo/ro.owl | slme |
| omo | http://purl.obolibrary.org/obo/omo.owl | mirror |
| NCIT | http://purl.obolibrary.org/obo/NCIT.owl | slme |
| mondo | http://purl.obolibrary.org/obo/mondo.owl | minimal |
| hp | http://purl.obolibrary.org/obo/hp.owl | minimal |
| ecto | http://purl.obolibrary.org/obo/ecto.owl | minimal |

Each has an import module, `src/ontology/imports/<id>_import.owl`, holding just the terms COHO uses and what the source ontology says about them. Import modules are never edited by hand: any edit is lost the next time the imports are refreshed.

## Importing a new term

Importing a new term is split into two sub-phases:

1. Declaring the terms to be imported
2. Refreshing imports dynamically

### Declaring terms to be imported
There are two ways to declare terms that are to be imported from an external ontology. Both can be used in parallel.

#### Protégé-based declaration

1. Open your ontology (edit file) in Protégé (5.5+).
1. Select 'owl:Thing'
1. Add a new class as usual.
1. Paste the _full iri_ in the 'Name:' field, for example, http://purl.obolibrary.org/obo/NCIT_C61512.
1. Click 'OK'

Now you can use this term for example to construct logical definitions. The next time the imports are refreshed (see how to refresh [here](#refresh-imports)), the metadata (labels, definitions, etc.) for this term are imported from the respective external source ontology and becomes visible in your ontology.

#### Using term files

Every import has a term file associated with it, which can be found in the imports directory: for the NCIT import `src/ontology/imports/NCIT_import.owl`, it is `src/ontology/imports/NCIT_terms.txt`. You can add terms in there simply as a list:

```
NCIT:C61512
NCIT:C17005
```

Now you can run the [refresh imports workflow](#refresh-imports) and the two terms will be imported.

The term files of the disease imports (`mondo_terms.txt`, `hp_terms.txt`) are not edited by hand: `src/scripts/diseases.py` writes them from the cohorts' disease mappings (see [Diseases](components.md#diseases)), so those imports are refreshed after a change to the disease table or its mappings, with `om make imports/mondo_import.owl imports/hp_import.owl IMP=true MIR=false` (add `MIR=true` to fetch fresh copies of the source ontologies first). They are minimal modules: the seed terms and their ancestors, with labels and definitions but no logical definitions, and their subset tags removed.

The term file of the exposure import (`ecto_terms.txt`) is written the same way by `src/scripts/exposures.py` from the cohorts' exposure mappings (see [Exposures](components.md#exposures)), and the import is refreshed with `om make imports/ecto_import.owl IMP=true MIR=false`. It is a minimal module of ECTO whose namespace takes in ExO, the ontology ECTO's root (exposure event) comes from. ExO's exposure stressor and exposure recipient are taken out of it with every axiom that mentions them: the exposure event has both as parts, and both are material entities, which RO's BFO axioms do not allow to be parts of a process, so with them every exposure term is unsatisfiable.

### Refresh imports

To rebuild the import modules so that they include any new terms you have added:

```
om refresh-imports
```

This downloads the imported ontologies again, so that the modules reflect their latest releases. NCIT is large, and this can take a while.

A single module is rebuilt by naming it:

```
om make imports/NCIT_import.owl -B IMP=true
```

If you wish to skip downloading the latest version of the source ontology and rebuild the module from the copy downloaded last time (kept in `src/ontology/mirror`, which is not committed), add `MIR=false`:

```
om make imports/NCIT_import.owl -B IMP=true MIR=false
```

Lastly, restart Protégé, and the term should be imported in ready to be used.

Refreshing imports brings in whatever changed in the source ontologies since the last refresh, so review the diff of the import modules before committing them.
