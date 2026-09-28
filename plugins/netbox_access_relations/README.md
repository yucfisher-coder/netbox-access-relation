# NetBox Access Relations

`netbox-access-relations` is a NetBox 4.7 plugin for maintaining business
systems, their NetBox IPAM objects, and directional access policies between
systems.

## Features

- Business systems, aliases, owners, and lifecycle status
- Associations with NetBox prefixes, IP addresses, and IP ranges
- Directional, time-bounded access policies with TCP and UDP services
- Security-zone resolution and zone matrix views
- Read-only service queries and permission-aware CSV export
- Versioned XLSX templates with preview and transactional import
- NetBox-native UI, object permissions, change logging, and REST endpoints
- English and Simplified Chinese user interfaces

## Compatibility

| Plugin release | NetBox | Python |
| --- | --- | --- |
| 1.0.x | >=4.7.0,<4.8.0 | >=3.12 |

Only the versions in this table are supported. See
[`COMPATIBILITY.md`](COMPATIBILITY.md) for the compatibility policy.

## Installation

Install the package into the same Python environment as NetBox. For a standard
NetBox deployment, add the released package to
`/opt/netbox/local_requirements.txt` and run NetBox's upgrade script. A local
wheel can also be installed directly:

```shell
/opt/netbox/venv/bin/pip install netbox_access_relations-1.1.0-py3-none-any.whl
```

Enable the plugin in NetBox's `configuration.py`:

```python
PLUGINS = [
    "netbox_access_relations",
]

PLUGINS_CONFIG = {
    "netbox_access_relations": {},
}
```

Apply migrations and collect static files, then restart the NetBox web and
worker services:

```shell
cd /opt/netbox
/opt/netbox/venv/bin/python netbox/manage.py migrate
/opt/netbox/venv/bin/python netbox/manage.py collectstatic --no-input
```

The plugin does not currently define any required or optional settings.

### Docker deployment

For a containerized production deployment (PostgreSQL, Redis, NetBox, and the
plugin in one Compose stack with offline image packaging), see the project's
deployment guides:

- [Linux x86_64 (amd64) offline deployment](../../docs/linux-amd64-offline-deployment.md)
- [Windows Docker Desktop deployment](../../docs/windows-docker-desktop-deployment.md)
- [Full production deployment, backup, and recovery manual](../../docs/production-deployment.md)

## Usage

After installation, open **Access Relations** in the NetBox navigation menu.
Visibility and available actions follow NetBox object permissions. Grant users
the appropriate `view`, `add`, `change`, or `delete` permissions for objects in
the `netbox_access_relations` application.

The REST API is available below:

```text
/api/plugins/access-relations/
```

Before importing a workbook, download a fresh template from the corresponding
import page. Imports are previewed before confirmation and are applied within a
database transaction.

## Upgrade

1. Back up the NetBox database and media files.
2. Confirm that the target NetBox version is listed in `COMPATIBILITY.md`.
3. Install the new plugin release in the NetBox environment.
4. Run `manage.py migrate` and `manage.py collectstatic --no-input`.
5. Restart the NetBox web and worker services.

Review `CHANGELOG.md` before every upgrade. Never downgrade across a migration
without restoring a compatible database backup.

## Uninstallation

Disabling or uninstalling the Python package does not remove its database
tables. Take a backup first, remove `netbox_access_relations` from `PLUGINS`,
restart NetBox, and only then uninstall the package. Database removal is an
explicit administrative operation and is not performed automatically.

## Development

Development and contributions are described in
[`CONTRIBUTING.md`](CONTRIBUTING.md). The source distribution includes the
plugin templates, translations, and static assets required at runtime.

Simplified Chinese translations live in
`netbox_access_relations/locale/zh/LC_MESSAGES/django.po`. All user-facing
strings must use Django translation functions or `{% translate %}` tags.

## Support and security

Use the [GitHub issue tracker](https://github.com/yucfisher-coder/netbox-access-relation/issues)
for reproducible defects and feature requests. Do not disclose credentials, production data, or security-sensitive
details in public reports. Until a private security contact is published,
report suspected vulnerabilities privately to the package distributor or the
maintainer from whom the release was obtained. See
[`SECURITY.md`](SECURITY.md) for the disclosure policy.

## License

Licensed under the Apache License 2.0. See [`LICENSE`](LICENSE).
