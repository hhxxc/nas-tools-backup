#!/bin/bash
D=/usr/local/bin/docker
$D exec nastool sh -c 'if [ -f /nas-tools/app/searcher.py.pre-fb ]; then cp /nas-tools/app/searcher.py.pre-fb /nas-tools/app/searcher.py && rm -f /nas-tools/app/searcher.py.pre-fb && echo REVERTED; else echo "nothing to revert"; fi'
echo "__DONE__"
