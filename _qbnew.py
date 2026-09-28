#!/usr/bin/env python3
"""Test qbittorrent-api 2026.8.1 against all three real qB instances."""
import sys, io, os, json, sqlite3, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# install into an isolated dir so we don't disturb the running container
TARGET = "/tmp/qbnew"
subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                "--target", TARGET, "qbittorrent-api==2026.8.1"],
               check=False)
sys.path.insert(0, TARGET)

import qbittorrentapi
from importlib.metadata import version as _v
try:
    print("installed qbittorrent-api:", _v("qbittorrent-api"))
except Exception:
    print("installed from:", qbittorrentapi.__file__)

con = sqlite3.connect('file:/config/user.db?mode=ro', uri=True)
print()
print("=== login + method smoke test per downloader ===")
for did, name, cfg in con.execute("select ID,NAME,CONFIG from DOWNLOADER"):
    c = json.loads(cfg)
    h, p = c.get("host"), c.get("port")
    try:
        qbt = qbittorrentapi.Client(host=h, port=p,
                                    username=c.get("username"),
                                    password=c.get("password"),
                                    VERIFY_WEBUI_CERTIFICATE=False,
                                    REQUESTS_ARGS={'timeout': (10, 30)})
        qbt.auth_log_in()
        ver = qbt.app_version()
        info = qbt.transfer_info()
        cats = qbt.torrent_categories.categories
        trs = qbt.torrents_info()
        print("  [OK  ] %-38s qB=%-9s up=%s dl=%s cats=%d torrents=%d" % (
            name, ver, info.get('up_info_speed'), info.get('dl_info_speed'),
            len(cats), len(trs)))
    except Exception as e:
        print("  [FAIL] %-38s %s: %s" % (name, type(e).__name__, str(e)[:100]))
con.close()
print("__DONE__")
