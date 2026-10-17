# Linux amd64 离线部署速查

本文只列出 Linux `amd64` 服务器上的离线部署关键步骤。介质制作、校验和升级见[严格离线部署手册](offline.md)；备份恢复见[关键命令](commands.md)。已有完整 amd64 运行镜像时，导入后按 [Docker 部署](docker.md)启动，无需源码构建。

## 前提

- 目标机为 Linux `amd64`，已安装 Docker Engine 和 Docker Compose v2。
- 在联网的 amd64 构建机制作离线源码交付包；包内包括完整项目源码、NetBox/Python/PostgreSQL/Redis 公共镜像、生产 wheelhouse 和文件校验和。
- 目标机不访问 Docker Hub 或 PyPI。具体版本和镜像 digest 见 [`locks/images.md`](../../../locks/images.md)。

## 目标机部署

将完整的 `dist/offline-source-release-1.3.6/` 目录转入离线服务器，然后执行：

```bash
sudo install -d -m 0750 /opt/netbox-access-relations
sudo cp -a /mnt/release/offline-source-release-1.3.6/. /opt/netbox-access-relations/
cd /opt/netbox-access-relations
sha256sum --check SHA256SUMS
docker load --input images.tar
scripts/build-offline-release
```

完成后按[严格离线部署手册](offline.md)中的生产配置说明和“首次启动与验收”继续。构建脚本以 `--network=none` 构建最终镜像；运行时使用镜像内已安装的插件 wheel，不挂载项目源码。

amd64 与 arm64 镜像包不可混用。arm64 的离线部署也遵循同一完整手册，但必须在 arm64 构建机制作交付包。
