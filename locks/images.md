# Container image lock

Resolved on 2026-10-12 from the official Docker Hub manifest. Compose and `Dockerfile.dev` use the OCI index digest so Docker selects the matching native manifest. Development and the production release gate must be verified on each target architecture before rollout.

| Purpose | Immutable reference | OCI index | linux/amd64 manifest | linux/arm64 manifest |
|---|---|---|---|---|
| NetBox 4.7.2 / netbox-docker 5.1.1 | `docker.io/netboxcommunity/netbox:v4.7.2-5.1.1@sha256:3cf9d3bd77aa186233b84d0ea1cf1755581d5e5678fa7d86ec3be62f79d0c643` | `sha256:3cf9d3bd77aa186233b84d0ea1cf1755581d5e5678fa7d86ec3be62f79d0c643` | `sha256:4cd4c0349c8c947d8a3214f6b71e6d42243e39f5a1a32fba2eff4d2b895cfbdc` | `sha256:37c8a88a4010dcec69215e136bab2ee117e7ea90d37840dc06d564705955d623` |
| PostgreSQL 18.6 Alpine | `docker.io/library/postgres:18.6-alpine@sha256:d3e1620b530c944afa6e887d22eb899824da68e19c52024bf98f5220c88a65b2` | `sha256:d3e1620b530c944afa6e887d22eb899824da68e19c52024bf98f5220c88a65b2` | `sha256:63bdc97d67b5133bf0e5ebd500bec6d046fa851dc81340d838f0347e616107e8` | `sha256:cbe15165195f7f2d63885b4d990fdec7b602248533cb05bd992284a45a58fed3` |
| Redis 7.4.11 Alpine | `docker.io/library/redis:7.4.11-alpine@sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf` | `sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf` | `sha256:1db42ccef14898aa29bae778452d567534b59c107129cbc1163fb552de184d3c` | `sha256:f8d15882ba108587477ce13c00ab0551933a84138427b7cc9abadfbe45ffd973` |

Do not treat index availability as production architecture validation. Resolve and natively test every deployment platform before rollout.
