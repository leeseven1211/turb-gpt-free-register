#!/usr/bin/env bash
# Oracle 独立实例备份；不删除历史备份，不读取本机数据库。
set -euo pipefail
umask 077

turb_root="${TURB_BACKUP_SOURCE_ROOT:-/srv/apps/turb-gpt-free-register}"
turb_backup_root="${TURB_BACKUP_ROOT:-/srv/backups/turb-gpt-free-register}"
turb_container="${TURB_BACKUP_PG_CONTAINER:-postgres}"

test -f "$turb_root/.env"
turb_root="$(cd "$turb_root" && pwd -P)"
test -x "$turb_root/.venv/bin/python"
mkdir -p "$turb_backup_root"
chmod 700 "$turb_backup_root"
exec 9>"$turb_backup_root/.backup.lock"
flock -n 9 || exit 0
turb_destination="$(mktemp -d "$turb_backup_root/$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")"
install -m 600 "$turb_root/.env" "$turb_destination/bootstrap.env"
# 只读取本次已经复制的配置，避免备份期间配置更新造成目标与回执不一致。
turb_target="$("$turb_root/.venv/bin/python" - "$turb_destination/bootstrap.env" "$turb_container" <<'PY'
import ipaddress
import json
import os
import re
import subprocess
import sys

from dotenv import dotenv_values
from psycopg.conninfo import conninfo_to_dict


def fail(reason):
    raise SystemExit(f"Turb 备份目标校验失败：{reason}")


try:
    raw = dotenv_values(sys.argv[1], interpolate=False).get("DATABASE_URL") or ""
    if not raw.startswith(("postgresql://", "postgres://")):
        fail("DATABASE_URL 必须为显式 PostgreSQL URL")
    connection = conninfo_to_dict(raw)
except Exception:
    fail("DATABASE_URL 格式无效")

database = connection.get("dbname", "")
if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", database):
    fail("数据库名缺失或包含不支持的字符")
override = os.getenv("TURB_BACKUP_DATABASE")
if override is not None and override != database:
    fail("TURB_BACKUP_DATABASE 与启动配置的数据库不一致")
if connection.get("service") or connection.get("hostaddr"):
    fail("不支持通过 service 或 hostaddr 间接指定目标")
host = connection.get("host", "")
try:
    addresses = [ipaddress.ip_address(value) for value in (
        ("127.0.0.1", "::1") if host == "localhost" else (host,)
    )]
    port = int(connection.get("port", "5432"))
except ValueError:
    fail("仅支持明确的本机回环地址和单一端口")
if not addresses or not all(address.is_loopback for address in addresses) or not 1 <= port <= 65535:
    fail("数据库连接必须指向本机回环地址和有效端口")

try:
    inspected = subprocess.run(
        ["docker", "inspect", "--type", "container", sys.argv[2]],
        capture_output=True, text=True, check=True,
    )
    containers = json.loads(inspected.stdout)
except (OSError, subprocess.CalledProcessError, ValueError):
    fail("无法读取目标 PostgreSQL 容器状态")
if not isinstance(containers, list) or len(containers) != 1:
    fail("目标必须对应唯一容器")
container = containers[0]
container_id = container.get("Id", "")
if not re.fullmatch(r"[a-f0-9]{64}", container_id) or not container.get("State", {}).get("Running"):
    fail("目标容器未运行或身份无效")
bindings = container.get("NetworkSettings", {}).get("Ports", {}).get("5432/tcp") or []
matched = False
for binding in bindings:
    if str(binding.get("HostPort")) != str(port):
        continue
    try:
        bound = ipaddress.ip_address(binding.get("HostIp", ""))
    except ValueError:
        continue
    if any(bound == address or (bound.is_unspecified and bound.version == address.version) for address in addresses):
        matched = True
if not matched:
    fail("启动配置地址/端口未映射到所选容器的 PostgreSQL 5432 端口")
# 后续固定容器 ID，避免容器名称在核验与导出之间被另一实例复用。
print(container_id, database)
PY
)"
read -r turb_container_id turb_database <<< "$turb_target"
# systemd 的 root 没有 sudo 的调用者身份；仅为本次命令信任明确的源码目录。
git -c "safe.directory=$turb_root" -C "$turb_root" rev-parse HEAD > "$turb_destination/commit.txt"
docker exec -u postgres "$turb_container_id" pg_dump -U postgres -h 127.0.0.1 -p 5432 -d "$turb_database" -Fc > "$turb_destination/database.dump.pending"
docker exec -i -u postgres "$turb_container_id" pg_restore --list < "$turb_destination/database.dump.pending" > "$turb_destination/database.toc"
mv "$turb_destination/database.dump.pending" "$turb_destination/database.dump"
touch "$turb_destination/COMPLETE"
printf 'Turb 配套备份完成：%s\n' "$turb_destination"
