# Container image lock

Resolved on 2026-09-12 with Docker Buildx. Compose and `Dockerfile.dev` use the OCI index digest so Docker selects the matching native manifest. Development and the 1.0.0 production release gate were verified on `linux/arm64`; other production architectures require a native rebuild and validation.

| Purpose | Immutable reference | OCI index | linux/amd64 manifest | linux/arm64 manifest |
|---|---|---|---|---|
| NetBox 4.7.0 / netbox-docker 5.1.1 | `docker.io/netboxcommunity/netbox:v4.7.0-5.1.1@sha256:1685e91c61bb4050089db2bb1603718820ae3ce0b266d4d069ff7c682f5d9c58` | `sha256:1685e91c61bb4050089db2bb1603718820ae3ce0b266d4d069ff7c682f5d9c58` | `sha256:fa7ffa268c39fb258bed80bd256360a525f1a129ee4ee06298f10d6708578eba` | `sha256:801563a44551e2b05fc6985fc378068a0a4cd1087947bc0ecea073dd0928a3c6` |
| PostgreSQL 18.6 Alpine | `docker.io/library/postgres:18.6-alpine@sha256:d3e1620b530c944afa6e887d22eb899824da68e19c52024bf98f5220c88a65b2` | `sha256:d3e1620b530c944afa6e887d22eb899824da68e19c52024bf98f5220c88a65b2` | `sha256:63bdc97d67b5133bf0e5ebd500bec6d046fa851dc81340d838f0347e616107e8` | `sha256:cbe15165195f7f2d63885b4d990fdec7b602248533cb05bd992284a45a58fed3` |
| Redis 7.4.11 Alpine | `docker.io/library/redis:7.4.11-alpine@sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf` | `sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf` | `sha256:1db42ccef14898aa29bae778452d567534b59c107129cbc1163fb552de184d3c` | `sha256:f8d15882ba108587477ce13c00ab0551933a84138427b7cc9abadfbe45ffd973` |

Do not treat index availability as production architecture validation. Resolve and natively test every deployment platform before rollout.
