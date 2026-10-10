# -*- coding: utf-8 -*-
"""
MoviePilot 插件兼容层（MP-Compat）
- analyze_plugin_compat: 静态 AST 扫描插件 import，判定兼容级别
- install_mp_compat_shims: 加载 mp_shim 级远程插件前注入模块别名/基类存根
详见 .workbuddy/reports/mp-compat-prd-2026-10-10.md
"""
import ast
import importlib
import sys
from types import ModuleType as _ModuleType

# ---------------- 兼容度扫描 ----------------

# MP 专有模块（出现即判 mp_deep，NASTool 无对应实现）
MP_ONLY_PREFIXES = (
    "app.core.", "app.db", "app.chain", "app.indexer", "app.mediaserver",
    "app.modules.", "app.scheduler", "app.helper.sites", "app.helper.browser",
    "app.helper.cloudflare", "app.helper.words",
    "app.site", "app.apiv1", "app.endpoints",
)

# 可 shim 的 MP 模块（加载前注入别名/存根）
SHIMMABLE = {
    "app.utils.http",       # → app.utils.http_utils (RequestUtils)
    "app.utils.string",     # → app.utils.string_utils (StringUtils)
    "app.log",              # → logger
    "app.plugins",          # → _PluginBase（仅补属性，不动包本体）
    "app.core.event",       # → eventmanager.register 存根
    "app.core.config",      # → settings 空配置存根
    "app.schemas",          # → 空存根
    "app.schemas.types",    # → EventType/NotificationType 存根枚举
    "app.helper.module",    # → ModuleHelper 存根
}

# NASTool 本体已存在的 app.* 模块（视为兼容）
NASTOOL_APPS = {
    "app", "app.conf", "app.helper", "app.message", "app.filter",
    "app.plugins", "app.rss", "app.subscribe",
    "app.sync", "app.torrent", "app.utils",
}


def _collect_imports(source_code):
    """
    AST 提取顶层导入模块路径集合
    """
    roots = set()
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return None  # 无法解析（可能是包片段），交由加载时报错
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                roots.add(node.module)
    return roots


def analyze_plugin_compat(source_code):
    """
    静态判定插件兼容级别
    :return: {"level": "nastool"|"mp_shim"|"mp_deep"|"unknown",
              "missing": [依赖的MP专有模块]}
    """
    roots = _collect_imports(source_code)
    if roots is None:
        return {"level": "unknown", "missing": []}
    missing = []
    shim_needed = False
    for mod in sorted(roots):
        if not mod.startswith("app"):
            continue  # 标准库/第三方，环境自备
        if mod in SHIMMABLE:
            shim_needed = True
            continue
        if any(mod == p or mod.startswith(p) for p in MP_ONLY_PREFIXES):
            missing.append(mod)
            continue
        if mod in NASTOOL_APPS or mod.startswith("app.utils."):
            continue  # NASTool 已有
        # app 下未知模块：MP 生态概率大，标记为需 shim
        missing.append(mod)
        shim_needed = True
    if missing:
        # 硬性专有依赖 → 不兼容
        if any(any(m == p or m.startswith(p) for p in MP_ONLY_PREFIXES) for m in missing):
            return {"level": "mp_deep", "missing": missing}
        return {"level": "mp_shim", "missing": missing}
    if shim_needed:
        return {"level": "mp_shim", "missing": []}
    return {"level": "nastool", "missing": []}


# ---------------- 轻量 shim 注入 ----------------

class _MPPluginBase:
    """
    MoviePilot _PluginBase 存根（挂到 app.plugins 属性）。
    继承 NASTool _IPluginModule，补齐 MP 方法面默认实现，
    init_config → init_plugin 桥接。
    """
    # 延迟继承，避免 import 期依赖（在函数内构造基类）
    plugin_name = ""
    plugin_desc = ""
    plugin_icon = ""
    plugin_version = "1.0"
    plugin_author = ""
    author_url = ""
    plugin_order = 0
    # MP 风格属性别名（部分插件读 module_name 等）
    module_name = ""
    module_desc = ""
    module_icon = ""
    module_version = "1.0"
    module_author = ""
    module_config_prefix = "plugin_"
    auth_level = 1

    @classmethod
    def _build(cls):
        from app.plugins.modules._base import _IPluginModule
        return type("MPPluginBase", (_IPluginModule,), dict(cls.__dict__))


def _make_forwarder_module(alias, target_name):
    """
    创建转发到真实模块的别名模块
    """
    target = importlib.import_module(target_name)
    m = _ModuleType(alias)
    m.__dict__.update({k: v for k, v in target.__dict__.items()
                       if not k.startswith("__")})
    return m


def _install_shims():
    """
    幂等注入 MP 兼容模块（仅远程插件加载路径调用）
    """
    shims = {}

    # 1. MPPluginBase 挂到 app.plugins
    import app.plugins as _app_plugins
    if not hasattr(_app_plugins, "_PluginBase"):
        setattr(_app_plugins, "_PluginBase", _MPPluginBase._build())

    # 2. 模块别名
    alias_map = {
        "app.utils.http": "app.utils.http_utils",     # RequestUtils
        "app.utils.string": "app.utils.string_utils",  # StringUtils
    }
    for alias, target in alias_map.items():
        if alias in sys.modules:
            continue
        try:
            m = _make_forwarder_module(alias, target)
            sys.modules[alias] = m
            parent, _, child = alias.rpartition(".")
            if parent in sys.modules:
                setattr(sys.modules[parent], child, m)
        except Exception:
            pass

    # 3. app.log（logger）
    if "app.log" not in sys.modules:
        try:
            import log as _ntlog
            m = _ModuleType("app.log")
            m.logger = _ntlog
            m.logger2 = _ntlog
            sys.modules["app.log"] = m
        except Exception:
            pass

    # 4. app.core.event（eventmanager.register 存根：注册进 NASTool EventManager）
    if "app.core.event" not in sys.modules:
        m = _ModuleType("app.core.event")

        class _Event:
            def __init__(self, event_type=None, data=None):
                self.event_type = event_type
                self.event_data = data or {}

        class _EventManagerStub:
            @staticmethod
            def register(event_type):
                def deco(func):
                    return func  # 存根：MP 事件体系与 NT 不同，暂不桥接
                return deco

        m.Event = _Event
        m.eventmanager = _EventManagerStub()
        sys.modules["app.core.event"] = m

    # 5. app.core.config（settings 空配置）
    if "app.core.config" not in sys.modules:
        m = _ModuleType("app.core.config")

        class _Settings:
            ROOT_PATH = ""
            TEMP_PATH = ""
            CACHE_PATH = ""
            CONFIG_PATH = ""
            SUPERUSER = "admin"

            def __getattr__(self, name):
                return ""

        m.settings = _Settings()
        sys.modules["app.core.config"] = m

    # 6. app.schemas / app.schemas.types（枚举存根）
    if "app.schemas" not in sys.modules:
        sys.modules["app.schemas"] = _ModuleType("app.schemas")
    if "app.schemas.types" not in sys.modules:
        m = _ModuleType("app.schemas.types")

        class _EnumStub:
            def __getattr__(self, name):
                return name

        m.EventType = _EnumStub()
        m.NotificationType = _EnumStub()
        m.MediaTypeEnum = _EnumStub()
        sys.modules["app.schemas.types"] = m
        setattr(sys.modules["app.schemas"], "types", m)

    # 7. app.helper.module（ModuleHelper 存根）
    if "app.helper.module" not in sys.modules:
        m = _ModuleType("app.helper.module")

        class ModuleHelper:
            @staticmethod
            def load(*args, **kwargs):
                return []

        m.ModuleHelper = ModuleHelper
        sys.modules["app.helper.module"] = m

    return shims


def ensure_mp_compat(level):
    """
    按兼容级别注入 shim（mp_shim 及以上）
    """
    if level in ("mp_shim",):
        return _install_shims()
    return None
