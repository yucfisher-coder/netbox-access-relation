# Contributing

Thank you for helping improve NetBox Access Relations.

## Before opening a change

- Search existing issues and describe the operational problem being solved.
- Keep changes compatible with the versions in `COMPATIBILITY.md`.
- Do not include production data, credentials, database dumps, or generated
  build artifacts.
- Discuss schema changes before implementation. Every model change must include
  a migration and upgrade/recovery consideration.

## Development setup

This plugin is developed in the parent repository's NetBox Docker environment.
Initialize the environment and start the development stack from the repository
root:

```shell
scripts/init-env
scripts/dev
```

The plugin can also be installed in editable mode in a compatible NetBox
development environment:

```shell
python -m pip install -e plugins/netbox_access_relations
```

## Tests and verification

Run the full verification gate before proposing a release:

```shell
scripts/verify
```

New behavior must include tests. Changes to user-visible strings must update
the Simplified Chinese catalog and compiled message file. Do not edit existing
migrations after release.

## Style and scope

- Follow the surrounding Python and Django conventions.
- Prefer documented NetBox plugin APIs over internal NetBox implementation
  modules.
- Preserve NetBox object permissions and change logging on every write path.
- Keep commits focused and explain user-visible or operational effects.

## Pull requests

Include a concise summary, test evidence, compatibility impact, migration
impact, and screenshots for material UI changes. Update `CHANGELOG.md` for
user-visible changes.

## Release checklist

1. Update the version in `pyproject.toml` and `netbox_access_relations/__init__.py`.
2. Update `CHANGELOG.md` and `COMPATIBILITY.md`.
3. Run `scripts/verify` from the parent repository.
4. Build both a wheel and source distribution in a clean environment.
5. Inspect the archives for templates, translations, documentation, and the
   license; then install the wheel into a clean compatible NetBox environment.
6. Run migrations, collect static files, and smoke-test the UI and REST API.
