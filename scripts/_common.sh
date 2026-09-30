#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${repo_root}/.env"
dev_compose="${repo_root}/docker-compose.yml"
production_compose="${repo_root}/docker-compose.prod.yml"

require_env() {
  if [[ ! -f "${env_file}" ]]; then
    echo "Missing ${env_file}; run scripts/init-env first." >&2
    exit 1
  fi
}

dev_compose_cmd() {
  require_env
  docker compose --env-file "${env_file}" -f "${dev_compose}" "$@"
}

production_compose_cmd() {
  local production_env="${PRODUCTION_ENV_FILE:-${repo_root}/.env.production}"
  if [[ ! -f "${production_env}" ]]; then
    echo "Missing ${production_env}; copy .env.production.example and inject production secrets." >&2
    exit 1
  fi
  PRODUCTION_ENV_FILE="${production_env}" docker compose \
    --env-file "${production_env}" -f "${production_compose}" "$@"
}
