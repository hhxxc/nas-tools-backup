# -*- coding: utf-8 -*-
import json, urllib.request, urllib.parse, http.cookiejar
BASE = "http://127.0.0.1:8080"
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
data = urllib.parse.urlencode({"username":"admin","password":"Qbt@2026x"}).encode()
op.open(BASE+"/api/v2/auth/login", data=data, timeout=10)
def get(ep, params=None):
    url = BASE+ep
    if params: url += "?" + urllib.parse.urlencode(params)
    return json.loads(op.open(url, timeout=15).read().decode())
torrents = get("/api/v2/torrents/info", {"tag":"刷流"})
su=ss=sd=0
for t in torrents:
    su+=t.get("uploaded",0); ss+=t.get("upspeed",0); sd+=t.get("dlspeed",0)
    print("%-42s | %s | 进度 %.1f%% | dl %d KB/s | up %d KB/s | uploaded %.2f GB | peers %d" % (
        t["name"][:42], t["state"], t.get("progress",0)*100,
        t.get("dlspeed",0)//1024, t.get("upspeed",0)//1024,
        t.get("uploaded",0)/1e9, t.get("num_leechs",0)))
print("TOTAL: upspeed %d KB/s | dlspeed %d KB/s | uploaded_total %.3f GB" % (ss//1024, sd//1024, su/1e9))
