#!/usr/bin/env python3
"""Reproduce get_captcha_base64 exactly -- find the real failure point."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir("/nas-tools"); sys.path.insert(0, "/nas-tools")

from app.helper import ChromeHelper
from app.utils import RequestUtils, StringUtils
from app.sites.site_cookie import SiteCookie
from config import Config

# replicate the private url builder
def build_captcha_url(siteurl, imageurl):
    if not siteurl or not imageurl:
        return ""
    if imageurl.startswith("/"):
        imageurl = imageurl[1:]
    return "%s/%s" % (StringUtils.get_base_url(siteurl), imageurl)

SRC = "image.php?action=regimage&imagehash=TESTHASH&secret="
SITEURL = "https://ptcafe.club/login.php"
url = build_captcha_url(SITEURL, SRC)
print("=== built captcha url ===")
print("  ", url)

print("\n=== A. fetch with chrome UA + cookies (what the code does) ===")
ch = ChromeHelper()
print("  chrome status:", ch.get_status())
ok = ch.visit(url="https://ptcafe.club/login.php", proxy=False)
print("  visit:", ok, "cf:", ch.pass_cloudflare())
ua = ch.get_ua()
ck = ch.get_cookies()
print("  ua=%r" % (ua[:80] if ua else None))
print("  cookies=%r" % (ck if not ck or len(str(ck)) < 200 else "len=%d" % len(str(ck))))

try:
    r = RequestUtils(headers=ua, cookies=ck).get_res(url)
    print("  -> %s" % ("None (request failed!)" if r is None
                       else "%s bytes=%s ct=%s" % (r.status_code, len(r.content),
                                                   r.headers.get('Content-Type'))))
    if r is not None:
        print("  first bytes:", r.content[:12])
except Exception as e:
    print("  EXC %s: %s" % (type(e).__name__, str(e)[:150]))

print("\n=== B. same url, no UA / no cookies ===")
r = RequestUtils().get_res(url)
print("  -> %s" % ("None" if r is None
                   else "%s bytes=%s" % (r.status_code, len(r.content))))

print("\n=== C. was that a real imagehash? test with the live one ===")
import re
from lxml import etree
html_text = ch.get_html() or ""
m = re.search(r'<img[^>]+alt="CAPTCHA"[^>]+src="([^"]+)"', html_text)
print("  live src =", m.group(1) if m else None)
if m:
    from html import unescape
    live = unescape(m.group(1))
    lurl = build_captcha_url(SITEURL, live)
    print("  live url =", lurl)
    r = RequestUtils(headers=ua, cookies=ck).get_res(lurl)
    print("  -> %s" % ("None" if r is None
                       else "%s bytes=%s ct=%s" % (r.status_code, len(r.content),
                                                   r.headers.get('Content-Type'))))
    # now what SiteCookie.get_captcha_base64 does
    try:
        b64 = SiteCookie.get_captcha_base64(ch, lurl)
        print("  get_captcha_base64 -> len=%s" % (len(b64) if b64 else 0))
    except Exception as e:
        import traceback; traceback.print_exc()
print("__DONE__")
