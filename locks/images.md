# Container image lock

Resolved on 2026-09-12 with Docker Buildx. Compose and `Dockerfile.dev` use the OCI index digest so Docker selects the matching native manifest. Development and the 1.0.0 production release gate were verified on `linux/arm64`; other production architectures require a native rebuild and validation.

| Purpose | Immutable reference | OCI index | linux/amd64 manifest | linux/arm64 manifest |
|---|---|---|---|---|
| NetBox 4.7.0 / netbox-docker 5.1.1 | `docker.io/netboxcommunity/netbox:v4.7.0-5.1.1@sha256:1685e91c61bb4050089db2bb1603718820ae3ce0b266d4d069ff7c682f5d9c58` | `sha256:1685e91c61bb4050089db2bb1603718820ae3ce0b266d4d069ff7c682f5d9c58` | `sha256:fa7ffa268c39fb258bed80bd256360a525f1a129ee4ee06298f10d6708578eba` | `sha256:801563a44551e2b05fc6985fc378068a0a4cd1087947bc0ecea073dd0928a3c6` |
| PostgreSQL 18.6 Alpine | `docker.io/library/postgres:18.6-alpine@sha256:d3e1620b530c944afa6e887d22eb899824da68e19c52024bf98f5220c88a65b2` | `sha256:d3e1620b530c944afa6e887d22eb899824da68e19c52024bf98f5220c88a65b2` | `sha256:63bdc97d67b5133bf0e5ebd500bec6d046fa851dc81340d838f0347e616107e8` | `sha256:cbe15165195f7f2d63885b4d990fdec7b602248533cb05bd992284a45a58fed3` |
| Redis 7.4.11 Alpine | `docker.io/library/redis:7.4.11-alpine@sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf` | `sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf` | `sha256:1db42ccef14898aa29bae778452d567534b59c107129cbc1163fb552de184d3c` | `sha256:f8d15882ba108587477ce13c00ab0551933a84138427b7cc9abadfbe45ffd973` |

Do not treat index availability as production architecture validation. Resolve and natively test every deployment platform before rollout.

## Local Docker labels after verification

The local ARM64 images were inspected before adding human-readable tags. Registry digest and local image ID are different identifiers and must not be compared as if they were interchangeable.

| Local tag | Verified RepoDigest or status | Local image ID |
|---|---|---|
| `netboxcommunity/netbox:v4.7.0-5.1.1` | ARM64 manifest `sha256:801563a44551e2b05fc6985fc378068a0a4cd1087947bc0ecea073dd0928a3c6` | `sha256:1df9c1f7868330c983d0ca82531c5f77377a1fba067368b5e5548d2f610753b5` |
| `postgres:18.6-alpine` | index `sha256:d3e1620b530c944afa6e887d22eb899824da68e19c52024bf98f5220c88a65b2` | `sha256:6def1cb8d5ffa3443c527419cc13f395ab328c27bf90fcb1e80831aae4103bc3` |
| `redis:7.4.11-alpine` | index `sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf` | `sha256:9a56851f1a97e0586f85f8d7f7652e65cb589b2409d965c5d6e275dfc2551907` |
| `netbox-access-relations-dev:local` | Final verified development build | `sha256:1ed6cf177c05cb9ab6f61c64ff885b98e1e56ca9751340af3937de5cd5ba7a4b` |
| `netbox-access-relations:1.0.0` | Final linux/arm64 release-gate build on 2026-09-22 | `sha256:888add3844684e71c601a35b52783b51ba8d4ee57a4dd578bb730f07d480e6e7` |
| `netbox-access-relations-dev:superseded-e5cb4238` | Superseded build which failed editable-install permission validation; do not use | `sha256:e5cb42386af6b9880a452e2f3f3e116119f164a84acc7aa133d242425d20e5e8` |
