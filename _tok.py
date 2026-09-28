#!/usr/bin/env python3
"""Call the REAL cookie-update path for 咖啡 with dummy creds to see how far it gets."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir("/nas-tools"); sys.path.insert(0, "/nas-tools")

from app.sites.site_cookie import SiteCookie
from app.sites import Sites

sc = SiteCookie()
site = Sites().get_sites(siteid=12)   # 咖啡
print("site:", site.get("name"), site.get("signurl"))

# 用假凭据调私有方法，只为看它走到哪一步、返回什么 message
meth = sc._SiteCookie__get_site_cookie_ua
cookie, ua, msg = meth(
    url="https://ptcafe.club/login.php",
    username="__dummy_user__",
    password="__dummy_pass__",
    twostepcode=None,
    ocrflag=False,
    proxy=False)
print("cookie:", "None" if not cookie else "len=%d" % len(str(cookie)))
print("ua    :", None if not ua else str(ua)[:60])
print("msg   : %r" % msg)
print("__DONE__")
