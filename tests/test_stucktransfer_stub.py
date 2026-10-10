# -*- coding: utf-8 -*-
"""stucktransfer 插件逻辑桩测试：不依赖真实 NAS 环境"""
import sys
import types
import time


def mod(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


# ---- 桩：日志 ----
class _Log:
    def info(self, *a, **k): print("[INFO]", *a)
    def warn(self, *a, **k): print("[WARN]", *a)
    def error(self, *a, **k): print("[ERROR]", *a)
    def debug(self, *a, **k): pass


mod("log", info=_Log().info, warn=_Log().warn, error=_Log().error, debug=_Log().debug)

# ---- 桩：config ----
cfg = mod("config")
cfg.Config = lambda: types.SimpleNamespace(get_timezone=lambda: "Asia/Shanghai")
cfg.PT_TAG = "NASTOOL"

# ---- 桩：apscheduler / pytz ----
aps = mod("apscheduler")
sched_mod = mod("apscheduler.schedulers")
sched_bg = mod("apscheduler.schedulers.background")


class FakeScheduler:
    def __init__(self, *a, **k): self.jobs = []
    def add_job(self, fn, trigger=None, **k): self.jobs.append((fn, trigger, k))
    def get_jobs(self): return self.jobs
    def print_jobs(self): pass
    def start(self): print("[SCHED] started with", len(self.jobs), "jobs")
    def remove_all_jobs(self): self.jobs.clear()
    def shutdown(self, *a, **k): pass
    running = False


sched_bg.BackgroundScheduler = FakeScheduler
trig_mod = mod("apscheduler.triggers")
trig_int = mod("apscheduler.triggers.interval")
trig_int.IntervalTrigger = lambda **k: ("interval", k)
mod("apscheduler.triggers.cron", CronTrigger=None)
sys.modules["apscheduler.schedulers.background"] = sched_bg
mod("pytz", timezone=lambda tz: tz)

# ---- 桩：app 包骨架 ----
app = mod("app")
app.plugins = types.SimpleNamespace()
mod("app.conf", SystemConfig=type("SystemConfig", (), {}))
mod("app.utils", ThreadHelper=type("ThreadHelper", (), {}))

# ---- 桩：_base ----
base = mod("app.plugins.modules._base")


class _IPluginModule:
    def history(self, key, value): print("[HISTORY]", key, value)
    def send_message(self, title=None, text=None, image=None):
        print("[MSG]", title, "|", text)
    def update_config(self, config, plugin_id=None): pass
    def get_config(self, plugin_id=None): return {}
    def get_data_path(self, plugin_id=None): return "."


base._IPluginModule = _IPluginModule

# ---- 桩：Downloader / DbHelper / Subscribe / Message ----
downloader = mod("app.downloader")


class FakeDownloader:
    def get_torrents(self, *a, **k): return FakeDownloader.torrents
    def delete_torrents(self, ids=None, delete_file=False):
        FakeDownloader.deleted.append((ids, delete_file))
        return True


FakeDownloader.torrents = []
FakeDownloader.deleted = []
downloader.Downloader = FakeDownloader
FakeDownloader.default_downloader_id = "qb1"

helper = mod("app.helper")


class FakeDb:
    rss_movies = []
    rss_tvs = []
    hist_by_id = {}   # {(downloader, download_id): SimpleNamespace}
    def get_rss_movies(self, *a, **k): return FakeDb.rss_movies
    def get_rss_tvs(self, *a, **k): return FakeDb.rss_tvs
    def get_download_history_by_downloader(self, downloader, download_id):
        return FakeDb.hist_by_id.get((downloader, download_id))


helper.DbHelper = FakeDb
fake_db = FakeDb()
mod("app.message", Message=type("Message", (), {}))


class FakeSubscribe:
    searched = []
    def subscribe_search_movie(self, rssid=None, state="D"): FakeSubscribe.searched.append(("MOV", rssid))
    def subscribe_search_tv(self, rssid=None, state="D"): FakeSubscribe.searched.append(("TV", rssid))


mod("app.subscribe", Subscribe=FakeSubscribe)
# app.utils 里 ThreadHelper.start_thread 需要真执行
import threading
def start_thread(fn, args=(), **k):
    threading.Thread(target=fn, args=args).start()
sys.modules["app.utils"].ThreadHelper.start_thread = staticmethod(start_thread)

# ---- 加载插件本体 ----
import importlib.util
spec = importlib.util.spec_from_file_location("stucktransfer", "app/plugins/modules/stucktransfer.py")
plugin_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin_mod)
StuckTransfer = plugin_mod.StuckTransfer
print("== 插件加载成功 ==", StuckTransfer.module_name)

# ---- 用例1：卡种命中电影订阅（下载历史反查，中文标题 vs 英文种子名） ----
sub = types.SimpleNamespace(ID=11, NAME="阿凡达", YEAR="2009", TMDBID="19995")
tv = types.SimpleNamespace(ID=22, NAME="黑暗荣耀", YEAR="2022", TMDBID="119110")
FakeDb.rss_movies = [sub]
FakeDb.rss_tvs = [tv]
FakeDb.hist_by_id = {
    ("qb1", "aaa"): types.SimpleNamespace(TMDBID="19995", TITLE="阿凡达"),
}
FakeDownloader.torrents = [
    # 卡种：命中阿凡达
    {"hash": "aaa", "name": "Avatar.2009.1080p.BluRay.x264",
     "state": "stalledDL", "dlspeed": 0, "num_seeds": 0, "num_complete": 0,
     "added_on": time.time() - 8 * 3600, "tags": "NASTOOL"},
    # 下载中不卡：不处理
    {"hash": "bbb", "name": "黑暗荣耀 S01E03", "state": "downloading",
     "dlspeed": 1024 * 1024, "num_seeds": 3, "num_complete": 5,
     "added_on": time.time() - 9 * 3600, "tags": "NASTOOL"},
    # 卡种但无做种时间不够：不处理
    {"hash": "ccc", "name": "黑暗荣耀 S01E04", "state": "stalledDL",
     "dlspeed": 0, "num_seeds": 0, "num_complete": 0,
     "added_on": time.time() - 60, "tags": "NASTOOL"},
    # HR 排除标签：不处理
    {"hash": "ddd", "name": "黑暗荣耀 S01E05", "state": "stalledDL",
     "dlspeed": 0, "num_seeds": 0, "num_complete": 0,
     "added_on": time.time() - 9 * 3600, "tags": "NASTOOL,HR"},
]

p = StuckTransfer()
p._enabled = True
p._stuck_hours = 6
p._delete_file = True
p._exclude_tags = "HR"
p._only_nastool = True
p._notify = True
p.dbhelper = fake_db

p._StuckTransfer__check_stuck()
time.sleep(0.5)  # 等重搜线程

assert FakeDownloader.deleted and FakeDownloader.deleted[0][0] == ["aaa"], "删种结果不对"
assert ("MOV", 11) in FakeSubscribe.searched, "未触发电影重搜"
assert not any(x[0][0] in ("bbb", "ccc", "ddd") for x in FakeDownloader.deleted), "误删了不该删的"
print("== 用例1 通过：卡种 aaa 已删并触发 MOV/11 重搜，其余 3 个未误删 ==")

# ---- 用例2：表单结构 ----
fields = StuckTransfer.get_fields()
ids = []
for row in fields[0]["content"]:
    for block in row:
        for c in (block.get("content") or []):
            ids.append(c.get("id"))
        if block.get("type") == "switch":
            ids.append(block.get("id"))
need = {"interval_min", "stuck_hours", "exclude_tags", "enabled", "onlyonce", "delete_file", "only_nastool", "notify"}
missing = need - set(filter(None, ids))
assert not missing, f"表单缺少配置项: {missing}"
print("== 用例2 通过：get_fields 含全部 8 个配置项 ==")
print("== 全部通过 ==")
