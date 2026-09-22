# Build configuration

COHO is built with [owlmake](https://github.com/EBISPOT/owlmake). The repository was created with the Ontology Development Kit (ODK) and owlmake builds it the way ODK 1.6.1 did, producing the same files, but from one configuration file and one program.

## Installing owlmake

1. Download the `om` binary for your machine from the [owlmake releases page](https://github.com/EBISPOT/owlmake/releases) (for example `om-macos-arm64` or `om-linux-amd64`).
2. Rename it to `om`, make it executable, and put it on your `PATH`:

```
chmod +x om-macos-arm64
mv om-macos-arm64 ~/.local/bin/om
```

`om --version` should now print a version of at least the `min_owlmake_version` stated in `owlmake.yaml`. Nothing else needs installing: no Docker, Java or ROBOT.

## `owlmake.yaml`

[`owlmake.yaml`](https://github.com/EBISPOT/cohort-ontology/blob/main/owlmake.yaml), at the top of the repository, holds what this repository decided and nothing else:

- `emulate_odk_version` — the standard build the file is written against. Everything the options below imply (release pipelines, import extraction, reports, QC checks) is that standard build, which is built into owlmake.
- `id`, `title`, `uribase`, `github_org`, `repo` — the ontology's identity.
- `release_artefacts`, `primary_release`, `export_formats` — which release files are made, and in which formats.
- `import_group` — the ontologies COHO imports terms from (see [Imports management](UpdateImports.md)).
- `components` — the parts of COHO generated from ROBOT templates (see [Components management](components.md)).
- `subset_group` — the subsets released alongside the ontology.
- `robot_report` — the quality control checks (see [Quality control](QualityControl.md)).

The options have the names and meanings they have in an ODK configuration, so the [ODK configuration reference](https://github.com/INCATools/ontology-development-kit/blob/master/docs/project-schema.md) applies to them.

A change to `owlmake.yaml` takes effect the next time `om` runs. After adding or removing an import or a component, run `om update-repo` as well: it updates the edit file's imports and the XML catalog to match, and creates the placeholder files the first build reads. `om make --plan-only` prints the whole build the file amounts to, and `om make --list-targets` every target that can be built.

## Commands

Run these from anywhere in the repository:

| Command | What it does |
| ------- | ------------ |
| `om make test IMP=false` | Run the quality control checks |
| `om make prepare_release -B IMP=false` | Build every release file and copy them to the top of the repository |
| `om refresh-imports` | Download the imported ontologies again and rebuild the import modules |
| `om make recreate-components` | Rebuild the components from their templates |
| `om update-repo` | Bring the edit file's imports, the XML catalog and placeholder files into step with `owlmake.yaml` |
| `om make coho.obo` | Build one file |

`IMP=false` reuses the import modules committed in `src/ontology/imports` instead of rebuilding them, and `MIR=false` reuses ontologies already downloaded. `-B` rebuilds everything, whether or not it looks up to date.

## Building something in a way of your own

A file that the standard build does not make, or makes differently from how COHO needs it, is described under a `targets` key in `owlmake.yaml`, as the file it makes, what it needs, and the steps that make it. See the [owlmake documentation](https://github.com/EBISPOT/owlmake#owlmakeyaml).
