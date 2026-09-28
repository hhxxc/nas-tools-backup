#!/usr/bin/env python3
"""Get the REAL reason qbittorrentapi login fails for 8085."""
import sys, io, os, json, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir("/nas-tools"); sys.path.insert(0, "/nas-tools")
import qbittorrentapi, requests

print("qbittorrentapi version:", getattr(qbittorrentapi, "__version__", "unknown"))
print("file:", qbittorrentapi.__file__)

HOST, PORT = "192.168.31.198", 8085
USER, PWD = "admin", "huhai123"

print("\n=== 1. raw HTTP (what the lib does under the hood) ===")
s = requests.Session()
s.headers.update({"Referer": "http://%s:%s" % (HOST, PORT),
                  "Origin": "http://%s:%s" % (HOST, PORT)})
r = s.post("http://%s:%s/api/v2/auth/login" % (HOST, PORT),
           data={"username": USER, "password": PWD}, timeout=10)
print("   status=%s text=%r" % (r.status_code, r.text[:60]))
print("   cookies=%s" % list(s.cookies.keys()))
r2 = s.get("http://%s:%s/api/v2/app/version" % (HOST, PORT), timeout=10)
print("   after login version=%s body=%r" % (r2.status_code, r2.text[:40]))

print("\n=== 2. qbittorrentapi with full traceback ===")
try:
    qbt = qbittorrentapi.Client(host=HOST, port=PORT, username=USER,
                                password=PWD, VERIFY_WEBUI_CERTIFICATE=False,
                                REQUESTS_ARGS={'timeout': (15, 60)})
    qbt.auth_log_in()
    print("   auth_log_in OK, version =", qbt.app_version())
except Exception as e:
    print("   EXC type=%s" % type(e).__name__)
    print("   str=%r" % str(e))
    print("   repr=%r" % repr(e))
    traceback.print_exc()

print("\n=== 3. what NASTool constructs (from DOWNLOADER table) ===")
from app.downloader.client.qbittorrent import Qbittorrent
import sqlite3
con = sqlite3.connect('file:/config/user.db?mode=ro', uri=True)
row = con.execute("select CONFIG from DOWNLOADER where ID=1").fetchone()
cfg = json.loads(row[0])
print("   cfg:", {k: (v if k != 'password' else '***') for k, v in cfg.items()})
con.close()
q = Qbittorrent(client_type=None, name="8085-套件", config=cfg)
print("   host=%r port=%r user=%r pwd_len=%s" % (
    q.host, q.port, q.username, len(q.password or "")))
q.connect()
print("   connect -> self.qbc =", q.qbc)
print("   get_status() =", q.get_status())
print("__DONE__")
