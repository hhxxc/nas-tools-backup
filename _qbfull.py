#!/usr/bin/env python3
"""Exercise every qbt API NASTool calls, against the real qB instances."""
import sys, io, os, json, sqlite3, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

TARGET = "/tmp/qbnew"
if not os.path.isdir(TARGET):
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                    "--target", TARGET, "qbittorrent-api==2026.8.1"], check=False)
sys.path.insert(0, TARGET)
import qbittorrentapi

con = sqlite3.connect('file:/config/user.db?mode=ro', uri=True)
rows = [r for r in con.execute("select ID,NAME,CONFIG from DOWNLOADER")]
con.close()

for did, name, cfg in rows:
    c = json.loads(cfg)
    if c.get("port") == "8419":
        continue  # stopped container, skip
    print("=== %s (%s:%s) ===" % (name, c.get("host"), c.get("port")))
    qbt = qbittorrentapi.Client(host=c.get("host"), port=c.get("port"),
                                username=c.get("username"),
                                password=c.get("password"),
                                VERIFY_WEBUI_CERTIFICATE=False,
                                REQUESTS_ARGS={'timeout': (10, 30)})
    qbt.auth_log_in()
    checks = [
        ("app_version",            lambda: qbt.app_version()),
        ("app_preferences",        lambda: len(qbt.app_preferences() or {})),
        ("torrent_categories",     lambda: len(qbt.torrent_categories.categories or {})),
        ("torrents_info(hashes)",  lambda: len(qbt.torrents_info(torrent_hashes="nonexistent") or [])),
        ("torrents_categories(rq)", lambda: len(qbt.torrents_categories(requests_args={'timeout': (10, 30)}) or {})),
        ("transfer_info",          lambda: bool(qbt.transfer_info())),
        ("transfer.info",          lambda: bool(qbt.transfer.info)),
        ("transfer.upload_limit",  lambda: qbt.transfer.upload_limit),
        ("transfer.download_limit", lambda: qbt.transfer.download_limit),
        ("torrents_pause(alias)",  lambda: qbt.torrents_pause(torrent_hashes="nonexistent")),
        ("torrents_resume(alias)", lambda: qbt.torrents_resume(torrent_hashes="nonexistent")),
        ("torrents_recheck",       lambda: qbt.torrents_recheck(torrent_hashes="nonexistent")),
        ("torrents_files",         lambda: qbt.torrents_files(torrent_hash="nonexistent")),
        ("torrents_delete_tags",   lambda: qbt.torrents_delete_tags(torrent_hashes="x", tags="x")),
    ]
    bad = []
    for label, fn in checks:
        try:
            fn()
            print("   [ok  ] %s" % label)
        except Exception as e:
            bad.append(label)
            print("   [FAIL] %-24s %s: %s" % (label, type(e).__name__, str(e)[:80]))
    print("   -> %d/%d ok" % (len(checks) - len(bad), len(checks)))
    print()
print("__DONE__")
