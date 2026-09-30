# Compatibility Matrix

| Plugin release | Minimum NetBox version | Maximum NetBox version | Python |
| --- | --- | --- | --- |
| 1.2.x | 4.7.0 | 4.7.x | >=3.12 |

## Platform support

| Scope | Supported environment | Notes |
| --- | --- | --- |
| Plugin package | Any compatible NetBox/Python environment | The Python package has no host-OS-specific runtime dependency. |
| Development | Linux, macOS, or Windows with Docker Engine / Docker Desktop and Compose v2 | Containers run as `linux/amd64` or `linux/arm64`; use Bash scripts on Linux/macOS and PowerShell or direct `docker compose` on Windows. |
| Production | Linux `amd64` and Linux `arm64` Docker hosts | These are the supported and release-validated production targets. Windows Docker Desktop is supported for local development and evaluation, not a validated production host. |

Apple Silicon is supported through Docker Desktop's native `linux/arm64` containers. This does not imply a native macOS NetBox deployment.

## Policy

- Compatibility is guaranteed only for combinations listed above and covered
  by the release test suite.
- A new NetBox minor release requires an explicit compatibility review and a
  new plugin release before it is considered supported.
- The `PluginConfig` compatibility bounds and Python package dependency bounds
  must agree with this matrix.
- Patch releases in the supported NetBox minor series are accepted unless a
  verified upstream regression is documented.
