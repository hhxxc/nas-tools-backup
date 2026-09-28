#!/bin/bash
D=/usr/local/bin/docker
IMG=ghcr.io/hhxxc/nas-tools:latest

before=$($D images "$IMG" --format '{{.ID}}' | head -1)
echo "before image id: $before"

echo
echo "=== pull (retry until the digest actually changes) ==="
ok=0
for i in $(seq 1 8); do
  echo "--- attempt $i ---"
  out=$($D pull "$IMG" 2>&1); rc=$?
  echo "$out" | tail -2
  if [ $rc -eq 0 ]; then
    after=$($D images "$IMG" --format '{{.ID}}' | head -1)
    if [ "$after" != "$before" ]; then
      echo "  image CHANGED: $before -> $after"
      ok=1; break
    else
      echo "  pull ok but image id unchanged ($after) -- may already be current"
      # 仍然检查一下镜像里是否含新库
      if $D run --rm --entrypoint sh "$IMG" -c 'grep -q "2026.8.1" /nas-tools/requirements.txt' 2>/dev/null; then
        echo "  image already contains the new requirement -> treat as current"
        ok=1; break
      fi
      echo "  image does NOT have new requirement yet; remote may not be updated"
    fi
  fi
  sleep 15
done

if [ "$ok" != "1" ]; then
  echo "PULL_INCOMPLETE (remote image may still be building or network blocked)"
  exit 1
fi

echo
echo "=== recreate container ==="
cd /volume2/docker/nastool && /usr/local/bin/docker-compose up -d --force-recreate 2>&1 | tail -4

echo
echo "=== verify library inside container ==="
for i in $(seq 1 30); do
  v=$($D exec nastool python3 -c "from importlib.metadata import version; print(version('qbittorrent-api'))" 2>/dev/null)
  [ -n "$v" ] && break
  sleep 2
done
echo "  qbittorrent-api in container = $v"
$D exec nastool sh -c 'grep -n "qbittorrent-api" /nas-tools/requirements.txt'
curl -sS -o /dev/null -w '  http_code=%{http_code}\n' --max-time 15 http://127.0.0.1:3004/
$D ps --filter name=^nastool$ --format '  {{.Names}} | {{.Status}}'
echo "__DONE__"
