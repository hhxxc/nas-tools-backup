#!/usr/bin/env python3
"""Reproduce the EXACT captcha path used by token update (咖啡)."""
import sys, io, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir("/nas-tools"); sys.path.insert(0, "/nas-tools")

from lxml import etree
from app.helper import ChromeHelper
from app.sites.siteconf import SiteConf
from app.utils import RequestUtils, StringUtils
from config import Config

sc = SiteConf()
base = StringUtils.get_base_url("https://ptcafe.club/")
conf = sc.get_grap_conf(url=base)
print("=== 1. site conf for ptcafe ===")
for k in ("LOGIN", "CAPTCHA", "CAPTCHA_IMG", "USERNAME", "PASSWORD", "SUBMIT"):
    v = conf.get(k) if isinstance(conf, dict) else None
    print("  %-12s %r" % (k, v))
login_conf = sc.get_login_conf()
print("\n=== 2. login_conf xpaths ===")
for k, v in (login_conf or {}).items():
    print("  %-12s %r" % (k, v))

print("\n=== 3. run the real captcha fetch ===")
ch = ChromeHelper()
ok = ch.visit(url="https://ptcafe.club/login.php", proxy=False)
print("  visit=%s cf=%s" % (ok, ch.pass_cloudflare()))
html_text = ch.get_html() or ""
html = etree.HTML(html_text)


def first(xps):
    for xp in xps or []:
        try:
            r = html.xpath(xp)
            if r:
                return xp, r[0]
        except Exception as e:
            print("    xpath %r EXC %s" % (xp, str(e)[:60]))
    return None, None


cap_xp, cap_el = first(login_conf.get("captcha"))
print("  captcha xpath  = %r -> %r" % (cap_xp, cap_el))
img_xp, img_val = first(login_conf.get("captcha_img"))
print("  captcha_img xp = %r -> %r" % (img_xp, img_val))

if img_val:
    from app.sites.site_cookie import SiteCookie
    url = SiteCookie._SiteCookie__get_captcha_url("https://ptcafe.club/login.php", img_val)
    print("  built url      = %s" % url)
    ua = ch.get_ua()
    ck = ch.get_cookies()
    print("  ua len=%s cookies=%r" % (len(ua or ""), (ck if not ck else "len=%d" % len(ck))))
    r = RequestUtils(headers=ua, cookies=ck).get_res(url)
    print("  fetch -> %s bytes=%s" % (
        r.status_code if r else "None", len(r.content) if r else 0))
    if r is not None:
        print("  data-uri prefix ok:", r.content[:8])
print("__DONE__")
