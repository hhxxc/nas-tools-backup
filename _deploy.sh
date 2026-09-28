#!/bin/bash
D=/usr/local/bin/docker
IMG=ghcr.io/hhxxc/nas-tools:latest

echo "=== pull with retries (capture real exit status) ==="
ok=0
for i in 1 2 3 4 5 6; do
  echo "--- attempt $i ---"
  out=$($D pull "$IMG" 2>&1)
  rc=$?
  echo "$out" | tail -2
  if [ $rc -eq 0 ]; then ok=1; break; fi
  echo "  (rc=$rc) retry in 12s"
  sleep 12
done

if [ "$ok" != "1" ]; then
  echo "PULL_FAILED_AFTER_RETRIES"
  exit 1
fi

echo
echo "=== rebuild ==="
cd /volume2/docker/nastool && /usr/local/bin/docker-compose up -d 2>&1 | tail -4

echo
echo "=== wait for app ==="
for i in $(seq 1 45); do
  if curl -sS -o /dev/null --max-time 3 http://127.0.0.1:3004/ 2>/dev/null; then
    echo "  responding after ${i} tries"; break
  fi
  sleep 2
done
curl -sS -o /dev/null -w '  http_code=%{http_code}\n' --max-time 10 http://127.0.0.1:3004/
$D ps --filter name=^nastool$ --format '  {{.Names}} | {{.Status}}'
echo "__DONE__"
