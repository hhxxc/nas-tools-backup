#!/bin/sh
# nas_vpn_logcheck.sh —— 黑群晖 StarVPN「组网掉线」一键取证（只读，不改任何配置）
# 用法（在 NAS 上）： sudo sh nas_vpn_logcheck.sh [容器名]
# 默认容器名 stars.client，若不是，先看第 0 段输出再带参数重跑。

CONN="${1:-stars.client}"
DOCKER=/usr/local/bin/docker
[ -x "$DOCKER" ] || DOCKER=docker

echo "===== 0. 找到组网客户端容器 ====="
$DOCKER ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}' 2>/dev/null | grep -iE 'stars|vpn|tun|tailscale|zerotier|frp'

echo
echo "===== 1. 容器病历（$CONN）====="
$DOCKER inspect "$CONN" --format '状态={{.State.Status}}
重启次数={{.RestartCount}}
运行中={{.State.Running}}
启动于={{.State.StartedAt}}
结束于={{.State.FinishedAt}}
退出码={{.State.ExitCode}}
OOM被杀={{.State.OOMKilled}}
重启策略={{.HostConfig.RestartPolicy.Name}}
网络模式={{.HostConfig.NetworkMode}}
特权={{.HostConfig.Privileged}}
CapAdd={{.HostConfig.CapAdd}}
Devices={{.HostConfig.Devices}}
compose项目={{index .Config.Labels "com.docker.compose.project"}}
compose目录={{index .Config.Labels "com.docker.compose.project.working_dir"}}' 2>&1

echo
echo "===== 2. 最近 200 行日志（带时间戳）====="
$DOCKER logs --tail 200 --timestamps "$CONN" 2>&1

echo
echo "===== 3. 只挑错误关键行（命中率最高，先看这段）====="
$DOCKER logs --tail 3000 "$CONN" 2>&1 | grep -iE 'error|fail|timeout|refused|unauthor|token|expire|tun|permission|route|dial|connect|EOF|panic|denied|no such' | tail -40

echo
echo "===== 4. 容器内部网络实况 ====="
$DOCKER exec "$CONN" sh -c 'ip addr 2>/dev/null || ifconfig 2>/dev/null; echo "--- route ---"; ip route 2>/dev/null || route -n; echo "--- resolv ---"; cat /etc/resolv.conf 2>/dev/null; echo "--- tun ---"; ls -l /dev/net/tun 2>/dev/null' 2>&1

echo
echo "===== 5. 宿主机侧 ====="
echo "[tun 设备]"; ls -l /dev/net/tun 2>/dev/null || echo "!! /dev/net/tun 缺失"
echo "[组网地址 188.x]"; ip -br addr 2>/dev/null | grep -E '188|tun|stars' || echo "(未见 188.x 地址)"
echo "[相关路由]"; ip route 2>/dev/null | grep -E '188|100\.100'
echo "[内核最近 30 行]"; dmesg 2>/dev/null | tail -30

echo
echo "===== 6. 出网连通性 ====="
ping -c 3 100.100.100.100 2>&1 | tail -3
curl -s -o /dev/null -w 'baidu=%{http_code}\n' --max-time 6 https://www.baidu.com

echo
echo "===== 7. compose / 配置目录 ====="
ls -d /volume*/docker/*stars* 2>/dev/null
for d in /volume*/docker/*stars*; do
  [ -d "$d" ] && { echo "--- $d ---"; ls -la "$d"; }
done

echo
echo "===== 取证结束（本脚本全程只读，未改动任何配置）====="
