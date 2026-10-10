import time
import re
from datetime import datetime, timedelta
from threading import Event

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

import log
from app.downloader import Downloader
from app.helper import DbHelper, ThreadHelper
from app.plugins.modules._base import _IPluginModule
from app.subscribe import Subscribe
from config import Config, PT_TAG


class StuckTransfer(_IPluginModule):
    """
    卡种自动换源插件：
    定时检查下载器中长时间停滞、无做种的种子，若命中当前订阅，
    自动删除该种子（可选连文件），并触发订阅重新搜索下载，
    配合订阅洗版规则实现全自动换种。
    """
    # 插件名称
    module_name = "卡种自动换源"
    # 插件描述
    module_desc = "自动检测下载停滞的订阅种子，删除后重新搜索换源，配合洗版规则全自动换种。"
    # 插件图标
    module_icon = "transfer.png"
    # 主题色
    module_color = "#E86A33"
    # 插件版本
    module_version = "1.0"
    # 插件作者
    module_author = "hhxxc"
    # 作者主页
    author_url = "https://github.com/hhxxc"
    # 插件配置项ID前缀
    module_config_prefix = "stucktransfer_"
    # 加载顺序
    module_order = 22
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _onlyonce = False
    _interval_min = 30
    _stuck_hours = 6
    _delete_file = True
    _exclude_tags = ""
    _only_nastool = True
    _notify = True
    _scheduler = None
    dbhelper = None

    # 退出事件
    _event = Event()

    @staticmethod
    def get_fields():
        return [
            {
                'type': 'div',
                'content': [
                    [
                        {
                            'title': '检查间隔(分钟)',
                            'required': "required",
                            'tooltip': '定时检查下载器中卡种的间隔，仅处理能匹配到当前订阅的种子',
                            'type': 'text',
                            'content': [
                                {
                                    'id': 'interval_min',
                                    'placeholder': '30',
                                }
                            ]
                        },
                        {
                            'title': '卡种判定(小时)',
                            'required': "required",
                            'tooltip': '种子添加超过该时长且无下载速度、无做种，判定为卡种',
                            'type': 'text',
                            'content': [
                                {
                                    'id': 'stuck_hours',
                                    'placeholder': '6',
                                }
                            ]
                        },
                        {
                            'title': '排除标签',
                            'required': "",
                            'tooltip': '含任一标签的种子不处理，多个标签用英文逗号分隔，如 HR,hnr（H&R 站务必配置）',
                            'type': 'text',
                            'content': [
                                {
                                    'id': 'exclude_tags',
                                    'placeholder': 'HR',
                                }
                            ]
                        },
                    ],
                    [
                        {
                            'title': '启用插件',
                            'required': "",
                            'tooltip': '开启后按检查间隔自动运行',
                            'type': 'switch',
                            'id': 'enabled',
                        },
                        {
                            'title': '立即运行一次',
                            'required': "",
                            'tooltip': '保存后立即执行一次检查',
                            'type': 'switch',
                            'id': 'onlyonce',
                        },
                        {
                            'title': '同时删除文件',
                            'required': "",
                            'tooltip': '删种时连同旧文件一起删除，换源后旧文件无保留价值建议开启',
                            'type': 'switch',
                            'id': 'delete_file',
                        },
                        {
                            'title': '仅处理NASTOOL标签种子',
                            'required': "",
                            'tooltip': '开启后只处理由 NASTOOL 添加的种子，避免误删手动任务',
                            'type': 'switch',
                            'id': 'only_nastool',
                        },
                        {
                            'title': '发送通知',
                            'required': "",
                            'tooltip': '每次自动换源后发送消息通知',
                            'type': 'switch',
                            'id': 'notify',
                        },
                    ],
                ]
            },
        ]

    def init_config(self, config=None):
        self.dbhelper = DbHelper()
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._interval_min = int(config.get("interval_min") or 30)
            self._stuck_hours = float(config.get("stuck_hours") or 6)
            self._delete_file = config.get("delete_file")
            self._exclude_tags = config.get("exclude_tags") or ""
            self._only_nastool = config.get("only_nastool")
            self._notify = config.get("notify")

        self.stop_service()

        if self._enabled or self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=Config().get_timezone())
            if self._enabled:
                self._scheduler.add_job(self.__check_stuck,
                                        IntervalTrigger(minutes=self._interval_min),
                                        id="stucktransfer_check")
            if self._onlyonce:
                self._scheduler.add_job(self.__check_stuck, 'date',
                                        run_date=datetime.now(tz=pytz.timezone(Config().get_timezone()))
                                        + timedelta(seconds=3),
                                        id="stucktransfer_once")
                # 关掉一次性开关
                self._onlyonce = False
                conf = self.get_config() or {}
                conf["onlyonce"] = False
                self.update_config(conf)
            if self._scheduler.get_jobs():
                self._scheduler.print_jobs()
                self._scheduler.start()

    @staticmethod
    def __normalize(name):
        """
        标题归一化：小写、去分隔符，便于与订阅名匹配
        """
        if not name:
            return ""
        return re.sub(r"[\s._\-()·]+", "", str(name)).lower()

    def __get_subscriptions(self):
        """
        汇总当前有效订阅：返回 (by_tmdbid, by_name)
        by_tmdbid: {str(tmdbid): (rtype, rssid, year, name)}
        by_name:   {归一化名称: (rtype, rssid, year, name)}
        """
        by_tmdbid = {}
        by_name = {}
        for rtype, rows in (("MOV", self.dbhelper.get_rss_movies() or []),
                            ("TV", self.dbhelper.get_rss_tvs() or [])):
            for row in rows:
                name = getattr(row, "NAME", None)
                rssid = getattr(row, "ID", None)
                if not name or not rssid:
                    continue
                year = str(getattr(row, "YEAR", "") or "")
                info = (rtype, rssid, year, name)
                tmdbid = str(getattr(row, "TMDBID", "") or "")
                if tmdbid:
                    by_tmdbid[tmdbid] = info
                by_name.setdefault(self.__normalize(name), info)
        return by_tmdbid, by_name

    def __resolve_subscription(self, torrent, sub_map):
        """
        解析卡种对应的订阅。
        优先用下载历史反查（TORRENT→TITLE/TMDBID，中英文名均可对上），
        历史查不到时降级为种子名归一化匹配订阅名。
        """
        by_tmdbid, by_name = sub_map
        tid = torrent.get("hash")
        tname = torrent.get("name") or ""

        # 1) 下载历史：DOWNLOAD_ID 对 qB 即种子 hash
        try:
            downloader_id = Downloader().default_downloader_id
            hist = self.dbhelper.get_download_history_by_downloader(
                downloader=downloader_id, download_id=tid)
            if hist:
                tmdbid = str(getattr(hist, "TMDBID", "") or "")
                if tmdbid and tmdbid in by_tmdbid:
                    return by_tmdbid[tmdbid]
                title = getattr(hist, "TITLE", None)
                if title and self.__normalize(title) in by_name:
                    return by_name[self.__normalize(title)]
        except Exception as err:
            self.warn(f"查询下载历史失败，降级为名称匹配：{str(err)}")

        # 2) 兜底：种子名归一化匹配订阅名（中文名不一致时匹配不到，仅作补充）
        tnorm = self.__normalize(tname)
        if not tnorm:
            return None
        for key, info in by_name.items():
            if key and key in tnorm:
                return info
        return None

    def __check_stuck(self):
        """
        主逻辑：找出卡种 → 匹配订阅 → 删种 → 重新搜索
        """
        if not self._enabled:
            return
        try:
            torrents = Downloader().get_torrents() or []
        except Exception as err:
            self.error(f"获取下载器种子失败：{str(err)}")
            return
        if not torrents:
            self.info(f"例行检查：下载器中当前没有下载任务")
            return

        sub_map = self.__get_subscriptions()
        if not (sub_map[0] or sub_map[1]):
            self.info(f"例行检查：当前没有有效订阅，跳过")
            return

        exclude_tags = [t.strip() for t in self._exclude_tags.split(",") if t.strip()]
        now = time.time()
        stuck_deadline = now - self._stuck_hours * 3600

        checked = 0
        stuck = 0
        swapped = 0
        for torrent in torrents:
            try:
                tags = str(torrent.get("tags") or "")
                if self._only_nastool and PT_TAG not in tags:
                    continue
                if any(tag in tags for tag in exclude_tags):
                    continue
                checked += 1

                state = torrent.get("state")
                # 只处理仍在下载中的状态
                if state not in ("stalledDL", "metaDL", "forcedMetaDL", "downloading"):
                    continue
                # 停滞判定：无下载速度
                if torrent.get("dlspeed", 0) != 0:
                    continue
                # 做种判定： swarm 与连接到的做种均为 0
                if torrent.get("num_complete", 0) != 0 or torrent.get("num_seeds", 0) != 0:
                    continue
                # 添加时间判定
                added_on = torrent.get("added_on") or 0
                if added_on > stuck_deadline:
                    continue

                tid = torrent.get("hash")
                tname = torrent.get("name")
                sub = self.__resolve_subscription(torrent, sub_map)
                if not sub:
                    continue
                stuck += 1
                rtype, rssid, year, sub_name = sub

                self.info(f"检测到卡种 {tname}，匹配订阅 {sub_name}，"
                          f"开始换源（删除种子{'及文件' if self._delete_file else ''}）")
                if Downloader().delete_torrents(ids=[tid], delete_file=self._delete_file):
                    swapped += 1
                    # 触发订阅重新搜索，洗版规则会筛选更优资源
                    if rtype == "MOV":
                        ThreadHelper().start_thread(Subscribe().subscribe_search_movie, (rssid,))
                    else:
                        ThreadHelper().start_thread(Subscribe().subscribe_search_tv, (rssid,))
                    self.__record_history(sub_name, tname)
                    if self._notify:
                        self.send_message(
                            title=f"【{self.module_name}】已自动换源",
                            text=f"订阅：{sub_name}\n卡种：{tname}\n"
                                 f"已删除并重新搜索下载")
                else:
                    self.warn(f"删除卡种失败：{tname}")
            except Exception as err:
                self.error(f"处理种子异常：{str(err)}")

        self.info(f"例行检查完成：NASTOOL 种子 {checked} 个，"
                  f"卡种 {stuck} 个，换源 {swapped} 个（判定阈值 {self._stuck_hours:g}h · 检查间隔 {self._interval_min}min）")

    def __record_history(self, sub_name, torrent_name):
        """
        记录换源历史
        """
        try:
            self.history(key=datetime.now().strftime("%Y%m%d%H%M%S"),
                         value={"subscribe": sub_name,
                                "torrent": torrent_name,
                                "delete_file": self._delete_file,
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        except Exception as err:
            self.error(f"记录历史失败：{str(err)}")

    def get_state(self):
        return self._enabled

    def stop_service(self):
        """
        退出插件
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._event.set()
                    self._scheduler.shutdown()
                    self._event.clear()
                self._scheduler = None
        except Exception as e:
            print(str(e))
