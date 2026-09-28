#!/bin/bash
D=/usr/local/bin/docker

echo "===== A. DOWNLOADER table ====="
python3 - <<'PYEOF'
import sqlite3
con = sqlite3.connect('file:/volume2/docker/nastool/config/user.db?mode=ro', uri=True)
cols = [r[1] for r in con.execute("PRAGMA table_info(DOWNLOADER)")]
print("cols:", cols)
for row in con.execute("select * from DOWNLOADER"):
    d = dict(zip(cols, row))
    for k, v in d.items():
        if k in ('PASSWORD',):
            print("   %-12s len=%s" % (k, len(v or "")))
        else:
            print("   %-12s %r" % (k, v))
    print("   ---")
con.close()
PYEOF

echo
echo "===== B. config.yaml downloader section ====="
grep -n -A6 "^downloader:" /volume2/docker/nastool/config/config.yaml

echo
echo "===== C. 8085 listening? ====="
netstat -tlnp 2>/dev/null | grep -E ':8085|:8080|:8090' || echo "  none of 8085/8080/8090 listening on host"
echo "--- container ports ---"
$D ps --format '  {{.Names}} | {{.Ports}}'

echo
echo "===== D. recent downloader errors ====="
$D logs --tail 400 nastool 2>&1 | grep -E "登录出错|添加任务|未下载到资源|Downloader" | tail -25

echo "__DONE__"
