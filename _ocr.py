#!/usr/bin/env python3
"""Test the OCR endpoint NASTool uses for captcha recognition."""
import sys, io, os, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.chdir("/nas-tools"); sys.path.insert(0, "/nas-tools")

from app.utils import RequestUtils
from app.helper import ChromeHelper
from config import Config

print("=== 1. current ocr config ===")
ocr = Config().get_config("ocr") or {}
print("  custom_ocr_url    =", repr(ocr.get("custom_ocr_url")))
print("  baiduocr_api_key  =", "set" if ocr.get("baiduocr_api_key") else "EMPTY")
print("  baiduocr_secret   =", "set" if ocr.get("baiduocr_secret_key") else "EMPTY")

print()
print("=== 2. default OCR service reachable? ===")
URL = "https://ocr.ddsrem.com/captcha/base64"
proxies = Config().get_proxies()
for label, px in (("direct", None), ("proxy", proxies)):
    try:
        r = RequestUtils(proxies=px, timeout=15).get_res(URL)
        print("  %-7s GET -> %s" % (label, r.status_code if r else "None"))
    except Exception as e:
        print("  %-7s GET -> EXC %s" % (label, str(e)[:80]))

print()
print("=== 3. fetch a REAL captcha from 咖啡 and try to OCR it ===")
ch = ChromeHelper()
ch.visit(url="https://ptcafe.club/login.php", proxy=False)
ch.pass_cloudflare()
html = ch.get_html() or ""
import re
from html import unescape
m = re.search(r'<img[^>]+alt="CAPTCHA"[^>]+src="([^"]+)"', html)
if not m:
    print("  no captcha image found on page")
else:
    src = unescape(m.group(1))
    url = "https://ptcafe.club/%s" % src.lstrip("/")
    r = RequestUtils(headers=ch.get_ua(), cookies=ch.get_cookies()).get_res(url)
    print("  captcha fetched: %s bytes=%s" % (
        r.status_code if r else None, len(r.content) if r else 0))
    if r is not None and r.content:
        b64 = base64.b64encode(r.content).decode()
        print("  b64 len =", len(b64))
        try:
            resp = RequestUtils(content_type="application/json").post_res(
                url=URL, json={"base64_img": b64}, timeout=25)
            if resp is None:
                print("  OCR -> None (failed)")
            else:
                print("  OCR -> %s %r" % (resp.status_code, resp.text[:200]))
        except Exception as e:
            print("  OCR EXC %s: %s" % (type(e).__name__, str(e)[:120]))
print("__DONE__")
