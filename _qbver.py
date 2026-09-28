#!/usr/bin/env python3
"""Confirm the login-response change across qB versions, and that the newer lib fixes it."""
import sys, io, os, json, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir("/nas-tools"); sys.path.insert(0, "/nas-tools")
import requests

con = sqlite3.connect('file:/config/user.db?mode=ro', uri=True)
print("=== login response body per qB version (the exact thing the lib checks) ===")
for did, name, cfg in con.execute("select ID,NAME,CONFIG from DOWNLOADER"):
    c = json.loads(cfg)
    h, p = c.get("host"), c.get("port")
    base = "http://%s:%s" % (h, p)
    s = requests.Session()
    s.headers.update({"Referer": base, "Origin": base})
    try:
        r = s.post(base + "/api/v2/auth/login",
                   data={"username": c.get("username"), "password": c.get("password")},
                   timeout=8)
        v = s.get(base + "/api/v2/app/version", timeout=8).text
        match = "OK  " if r.text == "Ok." else "MISMATCH"
        print("  %-38s qB=%-10s login_status=%s body=%r -> lib check: %s" % (
            name, v[:10], r.status_code, r.text[:12], match))
    except Exception as e:
        print("  %-38s unreachable: %s" % (name, str(e)[:60]))
con.close()

print()
print("=== is qbittorrentapi 2023.9.53 the installed one? ===")
import qbittorrentapi
py = r = None
try:
    import importlib.metadata as md
    print("  installed:", md.version("qbittorrent-api"))
except Exception as e:
    print("  (no metadata)", e)
# the lib's supported-version table
try:
    from qbittorrentapi.definitions import Version
    import inspect
    src = inspect.getsource(Version)
    print("  --- Version.is_app_version_supported ---")
    i = src.find("def is_app_version_supported")
    print(src[i:i + 700])
except Exception as e:
    print("  EXC", str(e)[:150])
print("__DONE__")
