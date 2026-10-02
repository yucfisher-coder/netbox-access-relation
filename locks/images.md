# Container image lock

Resolved on 2026-10-02 from the official Docker Hub manifest. Compose and `Dockerfile.dev` use the OCI index digest so Docker selects the matching native manifest. Development and the 1.3.1 production release gate must be verified on each target architecture before rollout.

| Purpose | Immutable reference | OCI index | linux/amd64 manifest | linux/arm64 manifest |
|---|---|---|---|---|
| NetBox 4.7.2 / netbox-docker 5.1.1 | `docker.io/netboxcommunity/netbox:v4.7.2-5.1.1@sha256:6f7177d3ff4db2d65212420a4d8dffab22e15de0d767c2bf3b06d36e588df5e9` | `sha256:6f7177d3ff4db2d65212420a4d8dffab22e15de0d767c2bf3b06d36e588df5e9` | `sha256:5a651e29340570b69585a56224ef5023ed1c6339cee6c7028c336e35099291bc` | `sha256:51e626a8d02d642f15f9d04d6310f682aa10b4e73c3ff3418b00affcf23489b5` |
| PostgreSQL 18.6 Alpine | `docker.io/library/postgres:18.6-alpine@sha256:d3e1620b530c944afa6e887d22eb899824da68e19c52024bf98f5220c88a65b2` | `sha256:d3e1620b530c944afa6e887d22eb899824da68e19c52024bf98f5220c88a65b2` | `sha256:63bdc97d67b5133bf0e5ebd500bec6d046fa851dc81340d838f0347e616107e8` | `sha256:cbe15165195f7f2d63885b4d990fdec7b602248533cb05bd992284a45a58fed3` |
| Redis 7.4.11 Alpine | `docker.io/library/redis:7.4.11-alpine@sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf` | `sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf` | `sha256:1db42ccef14898aa29bae778452d567534b59c107129cbc1163fb552de184d3c` | `sha256:f8d15882ba108587477ce13c00ab0551933a84138427b7cc9abadfbe45ffd973` |

Do not treat index availability as production architecture validation. Resolve and natively test every deployment platform before rollout.
