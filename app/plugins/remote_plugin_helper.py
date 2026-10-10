import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from cachetools import TTLCache

import log
from app.conf import SystemConfig
from app.utils import PathUtils
from app.utils.commons import singleton
from app.utils.http_utils import RequestUtils
from app.utils.types import SystemConfigKey
from config import Config

# 默认市场源，格式：名称|user/repo|branch
DEFAULT_SOURCES = ["MoviePilot官方|jxxghp/MoviePilot-Plugins|main"]
# GitHub 加速代理前缀列表，直连失败时依次回落（部分代理不稳定，多个互为备份）
GITHUB_PROXY_PREFIXES = ["https://ghproxy.net/", "https://gh-proxy.com/"]
# 清单缓存时间（秒）
_CACHE_TTL = 300


@singleton
class RemotePluginHelper:
    """
    第三方远程插件助手
    负责拉取市场清单、下载/安装/卸载/加载远程插件
    """
    systemconfig = None
    # 远程插件py文件目录
    remote_plugin_path = None
    # 远程插件依赖目录
    deps_path = None
    # 清单缓存 {source: [plugin_dict]}
    _cache = None

    def __init__(self):
        self.systemconfig = SystemConfig()
        self.remote_plugin_path = Config().get_remote_plugin_path()
        self.deps_path = os.path.join(self.remote_plugin_path, ".deps")
        if not os.path.exists(self.remote_plugin_path):
            os.makedirs(self.remote_plugin_path, exist_ok=True)
        self._cache = TTLCache(maxsize=10, ttl=_CACHE_TTL)

    def __get_proxy(self):
        """
        获取加速代理前缀（优先插件配置），默认第一个可用代理
        """
        conf = self.systemconfig.get(SystemConfigKey.UserRemotePlugins) or {}
        return conf.get("gh_proxy") or GITHUB_PROXY_PREFIXES[0]

    def get_market_sources(self):
        """
        获取市场源列表
        :return: [{name, repo, branch}]
        """
        sources = self.systemconfig.get(SystemConfigKey.UserRemoteMarketSources)
        if not sources:
            sources = []
            for line in DEFAULT_SOURCES:
                name, repo, branch = (line.split("|") + ["", "", ""])[:3]
                sources.append({"name": name, "repo": repo, "branch": branch or "main"})
            return sources
        # 兼容直接存 [{name,repo,branch}] 或字符串行格式
        result = []
        for source in sources:
            if isinstance(source, dict):
                if source.get("repo"):
                    result.append({
                        "name": source.get("name") or source.get("repo"),
                        "repo": source.get("repo"),
                        "branch": source.get("branch") or "main"
                    })
            elif isinstance(source, str):
                name, repo, branch = (source.split("|") + ["", "", ""])[:3]
                if repo:
                    result.append({"name": name or repo, "repo": repo, "branch": branch or "main"})
        return result

    def save_market_sources(self, sources):
        """
        保存市场源配置
        :param sources: [{name, repo, branch}]
        """
        self.systemconfig.set(SystemConfigKey.UserRemoteMarketSources, sources)
        self._cache.clear()

    def __fetch_text(self, url, validate_json=False):
        """
        拉取文本内容：先直连，再依次回落加速代理，共最多 1+N 次尝试
        :param validate_json: 校验响应为合法 JSON（拉清单用），
                              防止代理返回截断/错误页被当成功导致市场空列表
        """
        # 用户自定义代理优先，否则用内置代理列表
        conf = self.systemconfig.get(SystemConfigKey.UserRemotePlugins) or {}
        custom = conf.get("gh_proxy")
        proxies = [custom] if custom else GITHUB_PROXY_PREFIXES
        for req_url in [url] + [f"{p}{url}" for p in proxies]:
            try:
                res = RequestUtils(accept_type="application/json",
                                   timeout=15).get(req_url)
            except Exception as err:
                log.warn(f"【RemotePlugin】请求异常 {req_url[:80]}：{str(err)}")
                continue
            if not res:
                log.warn(f"【RemotePlugin】请求无响应：{req_url[:80]}")
                continue
            if validate_json:
                try:
                    json.loads(res)
                except Exception as err:
                    log.warn(f"【RemotePlugin】响应非合法JSON（疑似代理截断）：{req_url[:80]} - {str(err)}")
                    continue
            return res
        return None

    def __parse_manifest(self, manifest_text, source):
        """
        宽松解析清单（兼容 MoviePilot package.json 格式）
        支持字典形式 {id: {...}} 与列表形式 [{...}]
        :return: [{id, name, description, author, version, icon, level, file, history, source}]
        """
        try:
            data = json.loads(manifest_text)
        except Exception as err:
            log.warn(f"【RemotePlugin】清单解析失败 {source.get('name')}：{str(err)}")
            return []
        plugins = []
        items = []
        if isinstance(data, dict):
            # 字典格式：键即插件ID（MoviePilot package.json 条目内不含 id 字段）
            items = [dict(v, id=k) if isinstance(v, dict) else None
                     for k, v in data.items()]
        elif isinstance(data, list):
            items = data
        for item in items:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            pid = str(item.get("id"))
            plugins.append({
                "id": pid,
                "name": item.get("name") or item.get("module_name") or pid,
                "description": item.get("description") or item.get("module_desc") or "",
                "author": item.get("author") or item.get("module_author") or "",
                "version": str(item.get("version") or "1.0"),
                "icon": item.get("icon") or "",
                "level": item.get("level") or 1,
                "file": item.get("file") or f"{pid}.py",
                "history": item.get("history") or "",
                "requirements": item.get("requirements") or [],
                "source_name": source.get("name"),
                "source_repo": source.get("repo"),
                "source_branch": source.get("branch") or "main"
            })
        return plugins

    def get_remote_plugins(self, refresh=False):
        """
        获取所有市场源的远程插件清单（合并视图）
        :param refresh: 强制刷新缓存
        :return: {id: plugin_dict}
        """
        if not refresh:
            cached = self._cache.get("plugins")
            if cached is not None:
                return cached
        all_plugins = {}
        for source in self.get_market_sources():
            repo = str(source.get("repo")).strip("/")
            branch = source.get("branch") or "main"
            raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/package.json"
            text = self.__fetch_text(raw_url, validate_json=True)
            if not text:
                log.warn(f"【RemotePlugin】获取清单失败：{source.get('name')} ({repo})")
                continue
            plugins = self.__parse_manifest(text, source)
            log.info(f"【RemotePlugin】获取 {source.get('name')} 清单成功，共 {len(plugins)} 个插件")
            for plugin in plugins:
                all_plugins[plugin["id"]] = plugin
        # 缓存
        self._cache["plugins"] = all_plugins
        return all_plugins

    @staticmethod
    def compare_version(version_a, version_b):
        """
        版本比对：按 "." 分段逐段整数比较（短段补0），
        任一段非纯数字则回退为字符串不等即视为 version_a < version_b（有新版）
        :return: True 表示 version_a < version_b
        """
        if not version_b:
            # 远端版本未知，视为无新版
            return False
        if not version_a:
            # 本地版本未知，视为有新版
            return True
        parts_a = str(version_a).split(".")
        parts_b = str(version_b).split(".")
        # 任一段非纯数字则回退字符串比较
        for part in parts_a + parts_b:
            if not part.strip().isdigit():
                return str(version_a) != str(version_b)
        # 短段补0后逐段比较
        length = max(len(parts_a), len(parts_b))
        parts_a += ["0"] * (length - len(parts_a))
        parts_b += ["0"] * (length - len(parts_b))
        for a, b in zip(parts_a, parts_b):
            if int(a) != int(b):
                return int(a) < int(b)
        return False

    def __get_installed(self):
        """
        获取已安装远程插件信息
        """
        return self.systemconfig.get(SystemConfigKey.UserInstalledRemotePlugins) or {}

    def __save_installed(self, installed):
        """
        保存已安装远程插件信息
        """
        self.systemconfig.set(SystemConfigKey.UserInstalledRemotePlugins, installed)

    @staticmethod
    def is_safe_plugin_id(plugin_id):
        """
        校验插件ID合法性，防止路径穿越（如 ../xxx、绝对路径）
        """
        if not plugin_id or not isinstance(plugin_id, str):
            return False
        if plugin_id in (".", "..") or "/" in plugin_id or "\\" in plugin_id:
            return False
        return plugin_id.replace("_", "").replace("-", "").isalnum()

    @staticmethod
    def __candidate_files(plugin):
        """
        插件文件候选路径（按顺序尝试）：
        清单 file 字段 → plugins/<id小写>/__init__.py → plugins.v2/.v3 包路径 → <id>.py
        （兼容 MoviePilot 目录包结构：清单通常不含 file 字段）
        """
        pid = str(plugin.get("id"))
        lower = pid.lower()
        cands = []
        if plugin.get("file"):
            cands.append(str(plugin["file"]))
        cands += [
            f"plugins/{lower}/__init__.py",
            f"plugins.v2/{lower}/__init__.py",
            f"plugins.v3/{lower}/__init__.py",
            f"{pid}.py",
        ]
        # 去重保序
        seen, result = set(), []
        for c in cands:
            if c not in seen:
                seen.add(c)
                result.append(c)
        return result

    def __download_plugin_file(self, plugin):
        """
        下载插件主文件到远程插件目录（多候选路径依次尝试）
        """
        repo = str(plugin.get("source_repo")).strip("/")
        branch = plugin.get("source_branch") or "main"
        file_path = os.path.join(self.remote_plugin_path, f"{plugin.get('id')}.py")
        for file_name in self.__candidate_files(plugin):
            raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{file_name}"
            content = self.__fetch_text(raw_url)
            if not content:
                continue
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return True
            except Exception as err:
                log.error(f"【RemotePlugin】写入插件文件失败 {plugin.get('id')}：{str(err)}")
                return False
        return False

    def __install_requirements(self, requirements):
        """
        安装插件依赖到独立目录，失败仅告警不阻断
        """
        if not requirements:
            return True
        if not os.path.exists(self.deps_path):
            os.makedirs(self.deps_path, exist_ok=True)
        import importlib.util
        todo = []
        for req in requirements:
            # 形如 requests>=2.0 / requests
            module_name = str(req).split(">")[0].split("<")[0].split("=")[0].strip()
            if module_name and importlib.util.find_spec(module_name) is None:
                todo.append(str(req))
        if not todo:
            return True
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--target",
                 self.deps_path, *todo],
                check=False, timeout=300,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log.info(f"【RemotePlugin】依赖安装完成：{todo}")
        except Exception as err:
            log.warn(f"【RemotePlugin】依赖安装失败（不影响插件安装）：{str(err)}")
        return True

    def install_remote_plugin(self, plugin_id):
        """
        安装远程插件
        :return: (True, 提示) / (False, 错误)
        """
        plugins = self.get_remote_plugins()
        plugin = plugins.get(plugin_id)
        if not plugin:
            return False, "插件不存在或清单未加载，请先刷新市场"
        if not self.is_safe_plugin_id(plugin_id):
            return False, "插件ID不合法"
        # 下载插件文件
        if not self.__download_plugin_file(plugin):
            return False, "插件文件下载失败"
        # 安装依赖
        self.__install_requirements(plugin.get("requirements") or [])
        # 更新已安装列表
        installed = self.__get_installed()
        installed[plugin_id] = {
            "version": plugin.get("version"),
            "installed_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": plugin.get("source_name") or plugin.get("source_repo")
        }
        self.__save_installed(installed)
        log.info(f"【RemotePlugin】远程插件 {plugin.get('name')} 安装成功")
        return True, "插件安装成功"

    def uninstall_remote_plugin(self, plugin_id):
        """
        卸载远程插件：删除py文件及已安装记录
        """
        if not self.is_safe_plugin_id(plugin_id):
            return False, "插件ID不合法"
        installed = self.__get_installed()
        installed.pop(plugin_id, None)
        self.__save_installed(installed)
        # 删除插件文件
        file_path = os.path.join(self.remote_plugin_path, f"{plugin_id}.py")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as err:
                log.warn(f"【RemotePlugin】删除插件文件失败 {plugin_id}：{str(err)}")
        # 清理pycache
        self.clear_pycache(plugin_id)
        log.info(f"【RemotePlugin】远程插件 {plugin_id} 已卸载")
        return True, "插件卸载成功"

    def clear_pycache(self, plugin_id):
        """
        清理插件pycache
        """
        pycache = os.path.join(self.remote_plugin_path, "__pycache__")
        if not os.path.exists(pycache):
            return
        for cache_file in PathUtils.get_dir_level1_files(pycache, [".pyc"]):
            if str(cache_file).startswith(plugin_id + "."):
                try:
                    os.remove(cache_file)
                except Exception as err:
                    log.warn(f"【RemotePlugin】清理pycache失败：{str(err)}")

    def load_remote_plugin_module(self, plugin_id):
        """
        动态加载远程插件模块
        :return: 模块对象 或 None
        """
        if not self.is_safe_plugin_id(plugin_id):
            log.error(f"【RemotePlugin】插件ID不合法：{plugin_id}")
            return None
        file_path = os.path.join(self.remote_plugin_path, f"{plugin_id}.py")
        if not os.path.exists(file_path):
            log.error(f"【RemotePlugin】插件文件不存在：{plugin_id}")
            return None
        # 依赖目录加入搜索路径
        if os.path.exists(self.deps_path) and self.deps_path not in sys.path:
            sys.path.insert(0, self.deps_path)
        # 清理旧模块与pycache，保证热重载
        sys.modules.pop(plugin_id, None)
        self.clear_pycache(plugin_id)
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(plugin_id, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[plugin_id] = module
            spec.loader.exec_module(module)
            return module
        except Exception as err:
            log.error(f"【RemotePlugin】加载插件模块失败 {plugin_id}：{str(err)} - {traceback.format_exc()}")
            sys.modules.pop(plugin_id, None)
            return None

    def update_remote_plugin(self, plugin_id):
        """
        更新远程插件（覆盖下载后重载）
        """
        plugins = self.get_remote_plugins()
        plugin = plugins.get(plugin_id)
        if not plugin:
            return False, "插件不存在或清单未加载，请先刷新市场"
        installed = self.__get_installed()
        local_version = (installed.get(plugin_id) or {}).get("version") or "1.0"
        if not self.compare_version(local_version, plugin.get("version")):
            return False, "当前已是最新版本"
        # 覆盖下载
        if not self.__download_plugin_file(plugin):
            return False, "插件文件下载失败"
        self.__install_requirements(plugin.get("requirements") or [])
        # 更新记录并重载
        installed[plugin_id] = {
            "version": plugin.get("version"),
            "installed_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": plugin.get("source_name") or plugin.get("source_repo")
        }
        self.__save_installed(installed)
        from app.plugins.plugin_manager import PluginManager
        # 先停旧实例（stop_service -> sys.modules.pop -> 清pycache），避免旧线程/事件监听残留
        PluginManager().unload_remote_plugin(plugin_id)
        PluginManager().load_remote_plugin(plugin_id)
        log.info(f"【RemotePlugin】远程插件 {plugin.get('name')} 更新成功")
        return True, f"插件更新成功：{local_version} -> {plugin.get('version')}"

    def get_risk_confirmed(self):
        """
        是否已确认首次安装风险
        """
        conf = self.systemconfig.get(SystemConfigKey.UserRemotePlugins) or {}
        return conf.get("confirmed") or False

    def confirm_risk(self):
        """
        记录用户已确认第三方插件风险
        """
        conf = self.systemconfig.get(SystemConfigKey.UserRemotePlugins) or {}
        conf["confirmed"] = True
        self.systemconfig.set(SystemConfigKey.UserRemotePlugins, conf)

    def delete_plugin_data(self, plugin_id):
        """
        删除插件数据目录（预留）
        """
        data_path = os.path.join(self.remote_plugin_path, plugin_id)
        if os.path.exists(data_path):
            shutil.rmtree(data_path, ignore_errors=True)
