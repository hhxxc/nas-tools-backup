from app.plugins import EventHandler
from app.plugins.modules._base import _IPluginModule
from app.plugins.remote_plugin_helper import RemotePluginHelper
from app.conf import SystemConfig
from app.utils.types import EventType, SystemConfigKey


class RemotePluginMarket(_IPluginModule):
    # 插件名称
    module_name = "插件市场"
    # 插件描述
    module_desc = "在线浏览安装第三方插件。"
    # 插件图标
    module_icon = "market.png"
    # 主题色
    module_color = "#6C5CE7"
    # 插件版本
    module_version = "1.0"
    # 插件作者
    module_author = "nastool"
    # 作者主页
    author_url = "https://github.com/hsuyelin/nas-tools"
    # 插件配置项ID前缀
    module_config_prefix = "remotepluginmarket_"
    # 加载顺序
    module_order = 12
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _sources = ""
    _gh_proxy = ""

    @staticmethod
    def get_fields():
        return [
            # 同一板块
            {
                'type': 'div',
                'content': [
                    # 同一行
                    [
                        {
                            'title': '市场源',
                            'required': False,
                            'tooltip': '第三方插件市场源，每行一个，格式为：名称|user/repo|branch，'
                                       '仓库根目录需包含package.json清单文件',
                            'type': 'textarea',
                            'content':
                                {
                                    'id': 'sources',
                                    'placeholder': 'MoviePilot官方|jxxghp/MoviePilot-Plugins|main',
                                    'rows': 6,
                                }
                        }
                    ],
                    [
                        {
                            'title': 'GitHub加速代理',
                            'required': False,
                            'tooltip': '访问GitHub直连失败时使用的加速代理前缀，如：https://ghproxy.net/，'
                                       '留空使用默认代理',
                            'type': 'text',
                            'content':
                                {
                                    'id': 'gh_proxy',
                                    'placeholder': 'https://ghproxy.net/'
                                }
                        }
                    ]
                ]
            }
        ]

    def init_config(self, config=None):
        # 读取配置
        if config:
            self._sources = config.get("sources") or ""
            self._gh_proxy = config.get("gh_proxy") or ""
            # 解析市场源并保存到系统配置
            sources = []
            for line in str(self._sources).split('\n'):
                if not line or "|" not in line:
                    continue
                name, repo, branch = (line.split("|") + ["", "", ""])[:3]
                if not repo:
                    continue
                sources.append({
                    "name": name.strip(),
                    "repo": repo.strip(),
                    "branch": (branch.strip() or "main")
                })
            if sources:
                RemotePluginHelper().save_market_sources(sources)
            # 保存加速代理配置
            if self._gh_proxy:
                conf = SystemConfig().get(SystemConfigKey.UserRemotePlugins) or {}
                conf["gh_proxy"] = self._gh_proxy
                SystemConfig().set(SystemConfigKey.UserRemotePlugins, conf)

    @EventHandler.register(EventType.PluginReload)
    def reload(self, event):
        """
        响应插件重载事件
        """
        plugin_id = event.event_data.get("plugin_id")
        if not plugin_id:
            return
        if plugin_id != self.__class__.__name__:
            return
        return self.init_config(self.get_config())

    def get_page(self):
        """
        插件额外页面，提供市场入口
        """
        return "第三方插件市场", """
        <div class="text-center p-4">
          <p>点击下方按钮进入第三方插件市场，浏览并安装来自GitHub仓库的远程插件。</p>
          <p class="text-muted">注意：第三方插件由社区开发者提供，安装前请自行评估安全风险。</p>
          <a href="javascript:navmenu('remote_plugin_market')" class="btn btn-primary">
            进入第三方插件市场
          </a>
        </div>
        """, "关闭"

    def get_state(self):
        return True

    def stop_service(self):
        """
        退出插件
        """
        pass
