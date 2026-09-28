#!/usr/bin/env python3
"""Confirm: old qbittorrentapi vs qBittorrent 5.x login response change."""
import sys, io, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir("/nas-tools"); sys.path.insert(0, "/nas-tools")

import qbittorrentapi, inspect
from qbittorrentapi import auth

print("=== qbittorrentapi version ===")
try:
    from importlib.metadata import version
    print("  installed:", version("qbittorrentapi"))
except Exception as e:
    print("  metadata err:", e)
print("  path:", qbittorrentapi.__file__)

print("\n=== auth_log_in source ===")
print(inspect.getsource(auth.AuthAPIMixIn.auth_log_in))

print("=== _post / login response handling ===")
src = inspect.getsource(auth)
for m in re.finditer(r'.*Ok\..*', src):
    print("  ", m.group(0).strip())

print("\n=== app_version via raw vs lib, per downloader ===")
import requests, sqlite3, json
con = sqlite3.connect('file:/config/user.db?mode=ro', uri=True)
for did, name, cfg in con.execute("select ID,NAME,CONFIG from DOWNLOADER"):
    c = json.loads(cfg)
    h, p = c.get("host"), c.get("port")
    base = "http://%s:%s" % (h, p)
    s = requests.Session()
    s.headers.update({"Referer": base, "Origin": base})
    try:
        r = s.post(base + "/api/v2/auth/login",
                   data={"username": c.get("username"),
                         "password": c.get("password")}, timeout=8)
        v = s.get(base + "/api/v2/app/version", timeout=8)
        print("  %-38s login=%s text=%-8r version=%s %s" % (
            name, r.status_code, r.text[:6], v.status_code, v.text[:20]))
    except Exception as e:
        print("  %-38s EXC %s" % (name, str(e)[:80]))
con.close()
print("__DONE__")
