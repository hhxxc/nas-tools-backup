# -*- coding: utf-8 -*-
"""
第三方插件市场端到端测试
- 离线：is_safe_plugin_id 路径穿越防护 / compare_version 版本比较 / __parse_manifest 清单解析
- 在线：真实拉取 MoviePilot 官方市场清单（直连+代理回落）+ 下载一个插件文件
用法：python tests/test_remote_plugin_market.py [--offline-only]
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---- 隔离加载 helper（stub 掉 nas-tools 框架依赖，避免全库 import） ----
import importlib.util
import types as _types

for _name in ["log", "config",
              "app", "app.conf", "app.utils", "app.utils.commons",
              "app.utils.http_utils", "app.utils.types"]:
    if _name not in sys.modules:
        _m = _types.ModuleType(_name)
        sys.modules[_name] = _m
sys.modules["log"].warn = lambda *a, **k: None
sys.modules["log"].info = lambda *a, **k: None
sys.modules["log"].error = lambda *a, **k: None
sys.modules["config"].Config = lambda *a, **k: None
sys.modules["app.conf"].SystemConfig = lambda *a, **k: None
sys.modules["app.utils"].PathUtils = None
sys.modules["app.utils.commons"].singleton = lambda cls: cls
sys.modules["app.utils.http_utils"].RequestUtils = None
sys.modules["app.utils.types"].SystemConfigKey = None

_spec = importlib.util.spec_from_file_location(
    "remote_plugin_helper",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "app", "plugins", "remote_plugin_helper.py"))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["remote_plugin_helper"] = _mod
_spec.loader.exec_module(_mod)
RemotePluginHelper = _mod.RemotePluginHelper

PASS = []
FAIL = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"{'✅' if ok else '❌'} {name} {detail}")


# ---------- 离线：路径穿越防护 ----------
check("safe_id: 正常ID", RemotePluginHelper.is_safe_plugin_id("MoviePilot123"))
check("safe_id: 穿越拒绝", not RemotePluginHelper.is_safe_plugin_id("../etc/passwd"))
check("safe_id: 反斜杠拒绝", not RemotePluginHelper.is_safe_plugin_id("a\\b"))
check("safe_id: 绝对路径拒绝", not RemotePluginHelper.is_safe_plugin_id("/etc/passwd"))
check("safe_id: 空值拒绝", not RemotePluginHelper.is_safe_plugin_id(""))
check("safe_id: 点号拒绝", not RemotePluginHelper.is_safe_plugin_id(".."))
check("safe_id: 特殊字符拒绝", not RemotePluginHelper.is_safe_plugin_id("a$b"))

# ---------- 离线：版本比较 ----------
cmp = RemotePluginHelper.compare_version
check("ver: 1.0<1.1", cmp("1.0", "1.1"))
check("ver: 1.9<1.10 (逐段整数)", cmp("1.9", "1.10"))
check("ver: 2.0>1.99", not cmp("2.0", "1.99"))
check("ver: 相等无新版", not cmp("1.2.3", "1.2.3"))
check("ver: 短段补0", cmp("1.2", "1.2.1"))
check("ver: 本地未知有新版", cmp("", "1.0"))
check("ver: 远端未知无新版", not cmp("1.0", ""))
check("ver: 非数字回退", cmp("v1", "v2"))

# ---------- 离线：清单解析（字典格式 MoviePilot package.json） ----------
helper = RemotePluginHelper.__new__(RemotePluginHelper)  # 不触发 __init__（避免依赖本地配置环境）

fake = type("F", (), {})()
# 注意：真实 MoviePilot package.json 的字典键即 ID，条目内不含 id 字段
manifest = json.dumps({
    "BrushFlow": {
        "name": "刷流", "description": "自动刷流",
        "author": "jxxghp", "version": "1.2", "level": 2,
        "icon": "a.png", "file": "brushflow.py",
        "requirements": ["requests>=2.0"]
    },
    "BadOne": {"name": "非字典值应被跳过"},
    "v2free": {"module_name": "V2Free", "module_desc": "兼容旧字段", "module_author": "x", "version": 2.1}
})
plugins = RemotePluginHelper._RemotePluginHelper__parse_manifest(
    helper, manifest, {"name": "测试源", "repo": "a/b", "branch": "main"})
check("manifest: 字典格式解析数量", len(plugins) == 3, f"got {len(plugins)}")
bf = next((p for p in plugins if p["id"] == "BrushFlow"), None)
check("manifest: 键作为ID+字段映射", bf and bf["name"] == "刷流" and bf["file"] == "brushflow.py"
      and bf["requirements"] == ["requests>=2.0"])
vf = next((p for p in plugins if p["id"] == "v2free"), None)
check("manifest: 旧字段兼容", vf and vf["name"] == "V2Free" and vf["version"] == "2.1")

list_manifest = json.dumps([
    {"id": "A", "name": "甲", "version": "1"},
    {"no_id": True},
    "not-a-dict"
])
plugins2 = RemotePluginHelper._RemotePluginHelper__parse_manifest(
    helper, list_manifest, {"name": "s", "repo": "a/b", "branch": "main"})
check("manifest: 列表格式+脏数据跳过", len(plugins2) == 1, f"got {len(plugins2)}")

check("manifest: 非法JSON返回空", RemotePluginHelper._RemotePluginHelper__parse_manifest(
    helper, "{bad json", {"name": "s", "repo": "a/b", "branch": "main"}) == [])

# ---------- 在线：真实拉取市场清单 + 下载插件文件 ----------
if "--offline-only" not in sys.argv:
    import urllib.request

    def fetch(url, timeout=20):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8")

    raw_url = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Plugins/main/package.json"

    def fetch_retry(url, tries=2):
        last = None
        for _ in range(tries):
            try:
                return fetch(url)
            except Exception as e:
                last = e
                import time as _t
                _t.sleep(2)
        print(f"   失败 {url[:60]}: {last}")
        return None

    # 与线上 __fetch_text 相同的回落顺序：直连 → ghproxy.net → gh-proxy.com
    # 且带 JSON 校验：截断/错误页视为失败继续回落
    text = None
    used = None
    for label, u in [("直连", raw_url),
                     ("ghproxy.net代理", "https://ghproxy.net/" + raw_url),
                     ("gh-proxy.com代理", "https://gh-proxy.com/" + raw_url)]:
        t = fetch_retry(u)
        if t:
            try:
                json.loads(t)
                text, used = t, label
                break
            except Exception:
                print(f"   {label} 返回非JSON（截断），继续回落")
                t = None
    if text:
        src = {"name": "MoviePilot官方", "repo": "jxxghp/MoviePilot-Plugins", "branch": "main"}
        plugins = RemotePluginHelper._RemotePluginHelper__parse_manifest(helper, text, src)
        check(f"在线: 拉取官方市场清单（{used}）", len(plugins) > 0, f"共 {len(plugins)} 个插件")
        if plugins:
            # 按与线上相同的候选链下载第一个插件主文件
            p = plugins[0]
            ok_dl = False
            used_file = None
            lower = str(p["id"]).lower()
            cands = ([p["file"]] if p.get("file") else []) + [
                f"plugins/{lower}/__init__.py",
                f"plugins.v2/{lower}/__init__.py",
                f"plugins.v3/{lower}/__init__.py",
                f"{p['id']}.py",
            ]
            seen = set()
            for fn in cands:
                if fn in seen:
                    continue
                seen.add(fn)
                fu = f"https://raw.githubusercontent.com/{src['repo']}/{src['branch']}/{fn}"
                c = fetch_retry(fu) or fetch_retry("https://ghproxy.net/" + fu) \
                    or fetch_retry("https://gh-proxy.com/" + fu)
                if c and ("class" in c or "def " in c):
                    ok_dl = True
                    used_file = fn
                    break
            check(f"在线: 下载插件主文件 {p['id']}", ok_dl, f"路径 {used_file}")
    else:
        check("在线: 拉取官方市场清单", False, "直连与代理均失败")

print(f"\n===== 结果：{len(PASS)} 通过 / {len(FAIL)} 失败 =====")
sys.exit(1 if FAIL else 0)
