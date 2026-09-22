# Updating the Documentation

The documentation for COHO is managed in two places (relative to the repository root):

1. The `docs` directory contains all the files that pertain to the content of the documentation (more below)
2. the `mkdocs.yaml` file contains the documentation config, in particular its navigation bar and theme.

The documentation is hosted using GitHub pages, on a special branch of the repository (called `gh-pages`). It is important that this branch is never deleted - it contains all the files GitHub pages needs to render and deploy the site. It is also important to note that _the gh-pages branch should never be edited manually_. All changes to the docs happen inside the `docs` directory on the `main` branch.

## Editing the docs

### Changing content
All the documentation is contained in the `docs` directory, and is managed in _Markdown_. Markdown is a very simple and convenient way to produce text documents with formatting instructions, and is very easy to learn - it is also used, for example, in GitHub issues. This is a normal editing workflow:

1. Open the `.md` file you want to change in an editor of choice (a simple text editor is often best).
2. Perform the edit and save the file
3. Commit the file to a branch, and create a pull request as usual. 
4. If your development team likes your changes, merge the docs into main branch.
5. The documentation is deployed (see below)

## Deploy the documentation

The documentation is deployed by GitHub Actions (`.github/workflows/docs.yml`) whenever a change reaches the `main` branch; the workflow can also be started by hand from the repository's Actions tab. Give GitHub a few minutes, and the change is visible at https://EBISPOT.github.io/cohort-ontology/.

To look at the site before merging, install [mkdocs](https://www.mkdocs.org/) with the `mkdocs-material` theme and run `mkdocs serve --config-file mkdocs.yaml` from the top of the repository.
