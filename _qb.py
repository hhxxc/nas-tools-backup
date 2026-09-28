#!/usr/bin/env python3
"""Test qbittorrent login for each configured downloader."""
import sys, io, os, json, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir("/nas-tools")
sys.path.insert(0, "/nas-tools")

con = sqlite3.connect('file:/config/user.db?mode=ro', uri=True)

print("=== qbittorrent login test (from inside nastool container) ===")
try:
    import qbittorrentapi
    print("  qbittorrentapi", qbittorrentapi.__version__ if hasattr(qbittorrentapi, '__version__') else '?')
except Exception as e:
    print("  import fail:", e)

for row in con.execute("select ID,NAME,ENABLED,CONFIG from DOWNLOADER"):
    did, name, enabled, cfg = row
    try:
        c = json.loads(cfg)
    except Exception:
        print("  %-40s bad config" % name)
        continue
    host, port = c.get("host"), c.get("port")
    user, pwd = c.get("username"), c.get("password")
    try:
        qbt = qbittorrentapi.Client(host=host, port=port, username=user,
                                    password=pwd,
                                    VERIFY_WEBUI_CERTIFICATE=False,
                                    REQUESTS_ARGS={'timeout': (10, 30)})
        qbt.auth_log_in()
        ver = qbt.app_version()
        print("  [OK  ] %-40s %s:%s -> qB %s" % (name, host, port, ver))
    except Exception as e:
        print("  [FAIL] %-40s %s:%s -> %s: %s" % (
            name, host, port, type(e).__name__, str(e)[:110]))
con.close()
print("__DONE__")
