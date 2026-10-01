#!/bin/bash
set -euo pipefail

plugin_source=/plugin
plugin_install_source=$(mktemp -d /tmp/netbox-access-relations.XXXXXX)

if [[ ! -f "${plugin_source}/pyproject.toml" ]]; then
  echo "Plugin source is not mounted at ${plugin_source}" >&2
  exit 1
fi

# The bind-mounted source is owned by the host user. setuptools creates
# ``*.egg-info`` alongside pyproject.toml while building an editable install,
# so prepare that build in a container-writable copy instead of modifying the
# host checkout.
cp -a "${plugin_source}/." "${plugin_install_source}/"

/usr/local/bin/uv pip install \
  --python /opt/netbox/venv/bin/python \
  --no-deps \
  --link-mode copy \
  --editable "${plugin_install_source}"

exec /opt/netbox/docker-entrypoint.sh "$@"
