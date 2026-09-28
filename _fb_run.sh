#!/bin/bash
D=/usr/local/bin/docker
C="$D exec nastool sh -c"

echo "=== 1. backup + apply ==="
$C 'cp /nas-tools/app/searcher.py /nas-tools/app/searcher.py.pre-fb &&
    cp /config/_up_searcher.py /nas-tools/app/searcher.py && echo applied'

echo
echo "=== 2. syntax ==="
$C 'python3 -m py_compile /nas-tools/app/searcher.py && echo SYNTAX_OK'

echo
echo "=== 3. real subscription search for 特工 on 馒头 ==="
$C 'timeout 280 python3 -u /config/_why2.py 2>&1 | grep -vE "INFO: |WARNING: |ERROR: "'

echo "__DONE__"
