#!/bin/bash
set -euo pipefail

plugin_source=/plugins/netbox_access_relations

if [[ ! -f "${plugin_source}/pyproject.toml" ]]; then
  echo "Plugin source is not mounted at ${plugin_source}" >&2
  exit 1
fi

/usr/local/bin/uv pip install \
  --python /opt/netbox/venv/bin/python \
  --no-deps \
  --link-mode copy \
  --editable "${plugin_source}"

exec /opt/netbox/docker-entrypoint.sh "$@"
