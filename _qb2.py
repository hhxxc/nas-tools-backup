#!/usr/bin/env python3
"""Check 8085 login: wrong password, or IP whitelist / bypass-auth?"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir("/nas-tools"); sys.path.insert(0, "/nas-tools")
import requests

BASE = "http://192.168.31.198:8085"
s = requests.Session()
s.headers.update({"Referer": BASE, "Origin": BASE})

print("=== 1. /api/v2/app/version without login ===")
try:
    r = s.get(BASE + "/api/v2/app/version", timeout=10)
    print("   status=%s body=%r" % (r.status_code, r.text[:80]))
except Exception as e:
    print("   EXC", str(e)[:100])

print()
print("=== 2. login attempts ===")
for user, pwd in (("admin", "huhai123"), ("admin", "adminadmin"),
                  ("admin", "Huhai0912")):
    try:
        r = s.post(BASE + "/api/v2/auth/login",
                   data={"username": user, "password": pwd}, timeout=10)
        print("   %-8s/%-12s -> %s %r" % (user, pwd, r.status_code, r.text[:50]))
    except Exception as e:
        print("   %-8s/%-12s -> EXC %s" % (user, pwd, str(e)[:80]))

print()
print("=== 3. WebUI prefs (needs auth) -- check bypass/whitelist ===")
r = s.get(BASE + "/api/v2/app/preferences", timeout=10)
print("   status=%s" % r.status_code)
if r.status_code == 200:
    j = r.json()
    for k in ("bypass_local_auth", "bypass_auth_subnet_whitelist_enabled",
              "bypass_auth_subnet_whitelist", "web_ui_username",
              "web_ui_port", "web_ui_address"):
        print("   %-40s %r" % (k, j.get(k)))
else:
    print("   body:", r.text[:120])

print()
print("=== 4. which container owns 8085? ===")
r = s.get(BASE + "/api/v2/app/version", timeout=10)
print("   version header:", r.headers.get("Server"))
print("__DONE__")
