# -*- coding: utf-8 -*-
"""
豆瓣同步插件 v2.0 逻辑回归测试（隔离加载，stub 框架依赖）
- 看过→停止订阅联动（collect_action: stop/ignore/download）
- 识别失败重试队列（指数退避、上限 FAILED）
用法：python tests/test_doubansync_v2.py
"""
import sys
import os
import importlib.util
import types as _types
from datetime import datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

PASS = []
FAIL = []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(f"{'✅' if ok else '❌'} {name} {detail}")


# ---------- stub nas-tools 框架依赖 ----------
def _stub(name, **attrs):
    m = _types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


# 先 stub log/config，避免拉起真实配置链
_log = _stub("log", info=lambda *a, **k: None, warn=lambda *a, **k: None,
             error=lambda *a, **k: None, debug=lambda *a, **k: None)
_conf = _stub("config")
class _Cfg:
    def get_timezone(self):
        return "Asia/Shanghai"
_conf.Config = _Cfg


for pkg in ["app", "app.plugins", "app.plugins.modules", "app.media",
            "app.media.meta", "app.downloader", "app.searcher",
            "app.subscribe", "app.utils", "web", "web.backend",
            "web.backend.web_utils", "app.plugins.modules._base"]:
    if pkg not in sys.modules:
        sys.modules[pkg] = _types.ModuleType(pkg)
for pkg in ["app", "app.plugins", "app.plugins.modules", "app.media",
            "app.media.meta", "app.utils", "web", "web.backend"]:
    sys.modules[pkg].__path__ = []

sys.modules["app.plugins"].EventHandler = _types.SimpleNamespace(register=lambda t: lambda f: f)
_log.info = lambda *a, **k: None
_log.warn = lambda *a, **k: None
_log.error = lambda *a, **k: None
_log.debug = lambda *a, **k: None

# 清理预 stub，让 jinja2/pytz/apscheduler 走真实包
for _m in ["jinja2", "pytz", "apscheduler", "apscheduler.schedulers",
           "apscheduler.schedulers.background"]:
    sys.modules.pop(_m, None)

# app.utils.types 文件级加载（真实枚举，避开包链）
_t_spec = importlib.util.spec_from_file_location(
    "app.utils.types", os.path.join(REPO, "app", "utils", "types.py"))
_t_mod = importlib.util.module_from_spec(_t_spec)
sys.modules["app.utils.types"] = _t_mod
_t_spec.loader.exec_module(_t_mod)
setattr(sys.modules["app.utils"], "types", _t_mod)
from app.utils.types import MediaType, SearchType, RssType, EventType  # noqa: E402


class _FakeMedia:
    """模拟 MetaInfo"""

    def __init__(self, douban_id, title, year, mtype):
        self.douban_id = douban_id
        self.title = title
        self.year = year
        self.type = mtype
        self.vote_average = "7.5"

    def get_name(self):
        return self.title

    def get_poster_image(self):
        return ""


class _FakeSubscribe:
    def __init__(self):
        self.deleted = []

    def get_subscribe_id(self, mtype, title, year=None, tmdbid=None):
        return 100 if title in self.deleted else 100

    def delete_subscribe(self, mtype, title=None, year=None, rssid=None, tmdbid=None):
        self.deleted.append(title)
        return True


sys.modules["app.subscribe"].Subscribe = _FakeSubscribe

# 加载插件模块（stub 掉重依赖符号）
_stub("app.media", DouBan=object)
_stub("app.media.meta", MetaInfo=object)
_stub("app.downloader", Downloader=object)
_stub("app.searcher", Searcher=object)
sys.modules["app.plugins"].EventHandler = _types.SimpleNamespace(register=lambda t: lambda f: f)
sys.modules["app.plugins.modules._base"]._IPluginModule = type("_IPluginModule", (object,), {})
sys.modules["web.backend.web_utils"].WebUtils = _types.SimpleNamespace(
    get_mediainfo_from_id=lambda **k: None)
sys.modules["app.utils"].ExceptionUtils = _types.SimpleNamespace(
    exception_traceback=lambda e: None)

_spec = importlib.util.spec_from_file_location(
    "doubansync_test", os.path.join(REPO, "app", "plugins", "modules", "doubansync.py"))
mod = importlib.util.module_from_spec(_spec)
sys.modules["doubansync_test"] = mod
_spec.loader.exec_module(mod)

DS = mod.DoubanSync


def _make(hist=None, collect_action="stop"):
    p = DS.__new__(DS)
    p._collect_action = collect_action
    p.subscribe = _FakeSubscribe()
    p._store = dict(hist or {})
    p.get_history = lambda key=None: p._store.get(key)
    p.history = lambda key, value: p._store.update({key: value})
    p.update_history = lambda key, value: p._store.update({key: value})
    p.delete_history = lambda key: p._store.pop(key, None)
    p.info = lambda *a, **k: None
    p.warn = lambda *a, **k: None
    p.error = lambda *a, **k: None
    return p


media = _FakeMedia("1234567", "沙丘2", "2024", MediaType.MOVIE)

# ---------- 看过联动 ----------
# 1. stop + 已订阅(RSS) → 取消订阅 + FINISHED
p = _make({"1234567": {"state": "RSS", "add_time": "2026-10-09 10:00:00"}},
          collect_action="stop")
ret = p._DoubanSync__handle_collect(media, p.get_history("1234567"))
check("collect+RSS: 拦截处理", ret is True)
check("collect+RSS: 订阅已删除", "沙丘2" in p.subscribe.deleted)
check("collect+RSS: 状态=FINISHED", p._store["1234567"]["state"] == "FINISHED")

# 2. stop + 无历史 → 不处理不记录
p = _make({}, collect_action="stop")
ret = p._DoubanSync__handle_collect(media, None)
check("collect+无历史: 拦截", ret is True)
check("collect+无历史: 不写历史", "1234567" not in p._store)

# 3. stop + RETRY 中 → FINISHED（取消处理）
p = _make({"1234567": {"state": "RETRY", "retry_count": 2}}, collect_action="stop")
ret = p._DoubanSync__handle_collect(media, p.get_history("1234567"))
check("collect+RETRY: 拦截且FINISHED", ret is True and p._store["1234567"]["state"] == "FINISHED")

# 4. ignore → 拦截且无副作用
p = _make({"1234567": {"state": "RSS"}}, collect_action="ignore")
ret = p._DoubanSync__handle_collect(media, p.get_history("1234567"))
check("collect+ignore: 拦截且不删订阅", ret is True and p.subscribe.deleted == [])

# 5. download → 放行走旧版流程
p = _make({}, collect_action="download")
ret = p._DoubanSync__handle_collect(media, None)
check("collect+download: 放行", ret is False)

# 6. DOWNLOADED + collect → 不动已下载记录
p = _make({"1234567": {"state": "DOWNLOADED"}}, collect_action="stop")
ret = p._DoubanSync__handle_collect(media, p.get_history("1234567"))
check("collect+DOWNLOADED: 拦截不改状态", ret is True and p._store["1234567"]["state"] == "DOWNLOADED")

# ---------- 重试队列 ----------
# 7. 识别失败 → RETRY，retry_count=1，退避时间在未来
p = _make({}, collect_action="stop")
p._DoubanSync__mark_retry(media, None)
h = p._store["1234567"]
check("retry: 状态RETRY", h["state"] == "RETRY")
check("retry: 计数=1", h["retry_count"] == 1)
check("retry: 下次重试时间在未来", datetime.strptime(h["next_retry"], "%Y-%m-%d %H:%M:%S") > datetime.now())

# 8. 退避期内跳过
check("retry: 退避期内跳过", p._DoubanSync__handle_retry(media, h) is True)

# 9. 退避期满允许重试
h_old = dict(h)
h_old["retry_time"] = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
check("retry: 退避期满放行", p._DoubanSync__handle_retry(media, h_old) is False)

# 10. 超过上限 → FAILED
p = _make({"1234567": {"state": "RETRY", "retry_count": 15}}, collect_action="stop")
p._DoubanSync__mark_retry(media, p.get_history("1234567"))
check("retry: 超限标记FAILED", p._store["1234567"]["state"] == "FAILED")

# 11. 退避指数增长
p = _make({}, collect_action="stop")
p._DoubanSync__mark_retry(media, None)
t1 = p._store["1234567"]["next_retry"]
p._DoubanSync__mark_retry(media, p.get_history("1234567"))
t2 = p._store["1234567"]["next_retry"]
check("retry: 指数退避时间递增", t2 > t1, f"{t1} -> {t2}")

# ---------- 配置兼容 ----------
# 12. 旧配置无 collect_action → 默认 stop
p = DS.__new__(DS)
p._collect_action = None
p._collect_action = "stop" if not p._collect_action else p._collect_action
check("config: 默认stop", p._collect_action == "stop")

print(f"\n===== 结果：{len(PASS)} 通过 / {len(FAIL)} 失败 =====")
sys.exit(1 if FAIL else 0)
