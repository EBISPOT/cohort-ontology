# Update Imports Workflow

This page discusses how to update the contents of your imports, like adding or removing terms. To change which ontologies are imported, edit `import_group` in `owlmake.yaml` and run `om update-repo`, then [refresh the imports](#refresh-imports); see [Build configuration](BuildConfiguration.md).

COHO imports terms from these ontologies, listed under `import_group` in `owlmake.yaml`:

| Import | URL | Type |
| ------ | --- | ---- |
| ro | http://purl.obolibrary.org/obo/ro.owl | slme |
| omo | http://purl.obolibrary.org/obo/omo.owl | mirror |
| NCIT | http://purl.obolibrary.org/obo/NCIT.owl | slme |

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
