# The release workflow
The release workflow is based on GitHub releases and works as follows:

1. Run a release with owlmake
2. Review the release
3. Merge to main branch
4. Create a GitHub release

These steps are outlined in detail in the following.

## Run a release with owlmake

Preparation:

1. Ensure that all your pull requests are merged into your main branch
2. Make sure that all changes to main are committed to GitHub (`git status` should say that there are no modified files)
3. Locally make sure you have the latest changes from main (`git pull`)
4. Checkout a new branch (e.g. `git checkout -b release-2021-01-01`)
5. You may or may not want to refresh your imports as part of your release strategy (see [here](UpdateImports.md))
6. Make sure you have [owlmake installed](BuildConfiguration.md#installing-owlmake), at the version `owlmake.yaml` asks for or newer (`om --version`)

To actually run the release, you:

1. Open a command line terminal window and navigate to the repository
2. Run the release pipeline: `om make prepare_release -B IMP=false`. (Leave out `IMP=false` to rebuild the import modules from the imported ontologies as part of the release.)
3. If everything went well, the output ends with `published 12 release file(s)` and `done.`

This will create all the specified release targets (OBO, OWL, JSON, and the variants, coho-full and coho-base) and copy them into your release directory (the top level of your repo).
It also redraws the map in the README of where the cohorts recruited, `docs/images/cohort-map.svg`, from the release's data collection locations (`src/scripts/cohort_map.py`), and rewrites `coho-cohorts.csv`, the table of the cohorts and their metadata, from the edit file and its components (`src/scripts/cohort_table.py`). Commit both with the release files.

## Review the release

1. (Optional) Rough check. This step is frequently skipped, but for the more paranoid among us, this is a 3 minute additional effort for some peace of mind. Open the main release (coho.owl) in you favourite development environment (i.e. Protégé) and eyeball the hierarchy. We recommend two simple checks:
    1. Does the very top level of the hierarchy look ok? This means that all new terms have been imported/updated correctly.
    2. Does at least one change that you know should be in this release appear? For example, a new class. This means that the release was actually based on the recent edit file.
2. Commit your changes to the branch and make a pull request
3. In your GitHub pull request, review the following three files in detail (based on our experience):
    1. `coho.obo` - this reflects a useful subset of the whole ontology (everything that can be covered by OBO format). OBO format has that speaking for it: it is very easy to review!
    2. `coho-base.owl` - this reflects the asserted axioms in your ontology that you have actually edited.
    3. Ideally also take a look at `coho-full.owl`, which may reveal interesting new inferences you did not know about. Note that the diff of this file is sometimes quite large.
4. Like with every pull request, we recommend to always employ a second set of eyes when reviewing a PR!

## Merge the main branch
Once your [CI checks](QualityControl.md#continuous-integration) have passed, and your reviews are completed, you can now merge the branch into your main branch (don't forget to delete the branch afterwards - a big button will appear after the merge is finished).

## Create a GitHub release

1. Go to your releases page on GitHub by navigating to your repository, and then clicking on releases (usually on the right, for example: https://github.com/EBISPOT/cohort-ontology/releases). Then click "Draft new release"
1. As the tag version you **need to choose the date on which your ontologies were build.** You can find this, for example, by looking at the `coho.obo` file and check the `data-version:` property. The date needs to be prefixed with a `v`, so, for example `v2020-02-06`.
1. You can write whatever you want in the release title, but we typically write the date again. The description underneath should contain a concise list of changes or term additions.
1. Attach the release files, `coho-cohorts.csv` among them.
1. Click "Publish release". Done.

## Debugging typical ontology release problems

### A check fails

The release runs the same [quality control checks](QualityControl.md) as the `test` target. When one fails, the output names the check and what it found. Fix the edit file or the template the message points at, and run the release again.

### The map leaves a large country unshaded

The map step prints the located countries it has no outline for. Only very small countries, such as Singapore, should be among them. A larger one means its name in the outlines (`src/map/countries-110m.json`) differs from its label in `src/templates/gaz_xrefs.tsv`: add the pair to `OUTLINE_NAMES` in `src/scripts/cohort_map.py` and run the release again.
