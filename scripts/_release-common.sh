#!/bin/bash
# Shared configuration and safety checks for release and offline-build scripts.

release_version="${RELEASE_VERSION:-1.3.6}"
image_name="${NETBOX_PRODUCTION_IMAGE:-netbox-access-relations:${release_version}}"
base_image="${NETBOX_BASE_IMAGE:-docker.io/netboxcommunity/netbox:v4.7.2-5.1.1@sha256:3cf9d3bd77aa186233b84d0ea1cf1755581d5e5678fa7d86ec3be62f79d0c643}"
python_builder_image="${PYTHON_BUILD_IMAGE:-python:3.12-slim}"
postgres_image="${POSTGRES_IMAGE:-docker.io/library/postgres:18.6-alpine}"
redis_image="${REDIS_IMAGE:-docker.io/library/redis:7.4.11-alpine}"
target_arch="${TARGET_ARCH:-amd64}"

host_arch() {
  case "$(uname -m)" in
    x86_64) echo amd64 ;;
    aarch64|arm64) echo arm64 ;;
    *) echo unknown ;;
  esac
}

require_target_arch() {
  local current_arch
  current_arch="$(host_arch)"
  if [[ "${current_arch}" != "${target_arch}" ]]; then
    echo "This operation targets ${target_arch}, but the host architecture is ${current_arch}." >&2
    exit 1
  fi
}

require_local_image() {
  local image="$1"
  docker image inspect "${image}" >/dev/null 2>&1 || {
    echo "Missing local image: ${image}." >&2
    exit 1
  }
}

require_image_arch() {
  local image="$1"
  local image_arch
  require_local_image "${image}"
  image_arch="$(docker image inspect "${image}" --format '{{.Architecture}}')"
  if [[ "${image_arch}" != "${target_arch}" ]]; then
    echo "Image ${image} is ${image_arch}; expected ${target_arch}." >&2
    exit 1
  fi
}

verify_locked_base_image() {
  local base_arch locked_manifest
  local locked_index="sha256:3cf9d3bd77aa186233b84d0ea1cf1755581d5e5678fa7d86ec3be62f79d0c643"
  base_arch="$(docker image inspect "${base_image}" --format '{{.Architecture}}' 2>/dev/null || true)"
  case "${base_arch}" in
    amd64) locked_manifest="sha256:4cd4c0349c8c947d8a3214f6b71e6d42243e39f5a1a32fba2eff4d2b895cfbdc" ;;
    arm64) locked_manifest="sha256:37c8a88a4010dcec69215e136bab2ee117e7ea90d37840dc06d564705955d623" ;;
    *) echo "Unsupported or missing local base image architecture: ${base_arch:-unknown}." >&2; exit 1 ;;
  esac

  if ! docker image inspect "${base_image}" --format '{{join .RepoDigests "\n"}}' \
    | grep -Eq "@(${locked_index}|${locked_manifest})$"; then
    echo "Local ${base_image} does not match locked ${base_arch} manifest ${locked_manifest}." >&2
    exit 1
  fi
}
