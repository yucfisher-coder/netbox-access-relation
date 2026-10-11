# Windows Docker Desktop 开发指南

本文说明如何在 Windows + Docker Desktop 上开发和评估 NetBox Access Relations。Windows Docker Desktop 运行的是 Linux 容器，适用于开发和评估；本项目验证过的生产目标是 Linux `amd64` 与 `arm64` Docker 主机。生产部署请阅读[Docker 部署](docker.md)或[严格离线部署](offline.md)。

## 前置条件

1. 安装并启动 [Docker Desktop](https://www.docker.com/products/docker-desktop/)，推荐启用 WSL 2 后端。
2. 在 PowerShell 确认 Docker 和 Compose 可用：

   ```powershell
   docker --version
   docker compose version
   ```

3. 如 PowerShell 阻止本地脚本运行，可按组织策略设置当前用户的执行策略；本指南的基本 Compose 流程不依赖 PowerShell 脚本。

## 启动开发环境

在项目根目录打开 PowerShell。首次运行前创建本地环境配置：

```powershell
Copy-Item .env.example .env
```

将 `.env` 中的占位值替换为本机开发密钥，然后构建并启动：

```powershell
docker compose up -d --build
docker compose ps
docker compose logs -f
```

等待 `netbox` 状态变为 `healthy` 后，访问 <http://localhost:8000>。首次使用时创建管理员：

```powershell
docker compose exec netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py createsuperuser
```

## 常用操作

| 操作 | 命令 |
|---|---|
| 查看状态 | `docker compose ps` |
| 查看日志 | `docker compose logs -f [服务名]` |
| 停止服务并保留数据 | `docker compose stop` |
| 移除容器并保留数据 | `docker compose down` |
| 重启 worker | `docker compose restart worker` |
| 进入 Django shell | `docker compose exec netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py shell` |

不要使用 `docker compose down -v`，它会删除数据库等持久化卷。修改插件 Python 代码后，开发容器会自动重载；环境或基础镜像变化后可运行 `docker compose up -d --build` 重新构建。

## Windows 特有事项

- Compose 自动读取项目根目录的 `.env` 和 `docker-compose.yml`，通常无需显式指定文件。
- 默认 Web 端口为 `8000`。如端口已被占用，可修改 `.env` 中的 `NETBOX_HTTP_PORT`。
- Compose 中的相对路径由 Docker Desktop 转换，无需改成 Windows 路径格式。
- 如需使用项目 PowerShell 封装脚本，先确认本机执行策略允许运行本地脚本；也可以直接使用上面的标准 `docker compose` 命令。

Linux 和 macOS 的开发流程见[本地开发指南](../development.md)。本页不定义 Windows 生产部署、备份或恢复流程。
