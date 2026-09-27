# Compatibility Matrix

| Plugin release | Minimum NetBox version | Maximum NetBox version | Python |
| --- | --- | --- | --- |
| 1.0.x | 4.7.0 | 4.7.x | >=3.12 |

## Policy

- Compatibility is guaranteed only for combinations listed above and covered
  by the release test suite.
- A new NetBox minor release requires an explicit compatibility review and a
  new plugin release before it is considered supported.
- The `PluginConfig` compatibility bounds and Python package dependency bounds
  must agree with this matrix.
- Patch releases in the supported NetBox minor series are accepted unless a
  verified upstream regression is documented.
