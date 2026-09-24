# NASTool（个人自维护版）

基于 [hsuyelin/nas-tools](https://github.com/hsuyelin/nas-tools) 3.4.1 的个人维护分支，
仅用于自己 NAS 上跑 Jellyfin + qBittorrent 的媒体库自动化。

> 上游 hsuyelin/nas-tools 仓库已删除（404），此仓库是其 3.4.1 版本的延续。

## 这个分支做了什么

主要目的是把原来跑在群晖套件里的 NASTool 迁到自建 Docker 镜像，打通
「改代码 → push → GitHub Actions 出镜像 → NAS 拉取」的流程。

- **自建 Docker 镜像**：`ghcr.io/hhxxc/nas-tools:latest`（公开包），
  push 到 `master` 即自动构建（alpine/amd64）
- **Dockerfile 修复两处构建腐化**（上游不锁版本导致，详见下）
- **Jellyfin 12.x 鉴权适配**：`DisableLegacyAuthorization` 迁移废弃了
  `?api_key=` 查询参数鉴权，只认 `Authorization: MediaBrowser Token="..."` 请求头。
  上游在 19 处仍用查询参数，导致所有 Jellyfin 调用 401，表现为订阅进度显示横杠、
  缺失集误判导致重复下载、刮削后刷新媒体库失败。
  已补丁 `app/utils/http_utils.py` 新增 `_fix_jellyfin_auth()`，仅对配置中的
  jellyfin host 生效
- **版本号链接**指向本仓库而非已删除的上游

### Dockerfile 的两处修复

上游 Dockerfile 不锁依赖版本，当年能构建、现在不行，已修：

| 问题 | 现象 | 修法 |
|---|---|---|
| `pip install --upgrade setuptools` | 装到 84 版，而 setuptools 81 移除了 `pkg_resources`，`cn2an → proces` 崩溃，**应用启动即挂** | 钉 `setuptools<81` |
| `fast-bencode==1.1.3` | 只有 glibc wheel，Alpine 是 musl 会退回源码编译并失败 | 升到 `1.1.8`（有 musllinux wheel） |

同时把 `apk`/`pip` 依赖清单改为从本仓库读取（原来是 `wget` 上游 raw 文件，上游删库后必然失败），
并让依赖层独立缓存，改应用代码时不必重装依赖。

## 部署

镜像地址：

```
ghcr.io/hhxxc/nas-tools:latest
```

NAS 上的部署目录为 `/volume2/docker/nastool/`，用 `docker-compose.yml` 管理，
端口映射 `3004:3003`，`restart: always`。

一键更新脚本：

```bash
sudo sh /volume2/docker/nastool/update.sh            # 拉最新镜像并重建
sudo sh /volume2/docker/nastool/update.sh --status   # 容器/镜像/端口/HTTP 状态
sudo sh /volume2/docker/nastool/update.sh --logs     # 跟踪日志
```

### 本地运行

仅支持 Python 3.10：

```bash
git clone -b master https://github.com/hhxxc/nas-tools-backup
python3 -m pip install --force-reinstall -r requirements.txt
export NASTOOL_CONFIG="/xxx/config/config.yaml"
nohup python3 run.py &
```

## 部署时容易踩的坑

这几条都是实际踩过的，换环境时注意：

- **容器内的 `127.0.0.1` 是容器自己**。配置里指向其他服务（如 Jellyfin）必须用局域网 IP，
  例如 `http://192.168.188.2:18090/`，写 `127.0.0.1` 连不上
- **挂载必须用与宿主机相同的路径**（`/volume3/videos:/volume3/videos`），
  否则 `config.yaml` 和 `DOWNLOADER.container_path` 里的绝对路径全部失效
- **`NASTOOL_AUTO_UPDATE` 必须为 `false`**，否则容器启动会执行
  `git clean -dffx` + `git reset --hard`，抹掉本地改动
- **精确搜索勿开英文名**：设置 → 实验室 → 「精确搜索使用英文名称」。
  中文资源站（如馒头）标题以中文为主，开启后英文名只命中零星条目，
  且搜索逻辑是「英文搜到 0 条才回退中文名」，会导致订阅整季资源被跳过、
  订阅永远不结束。**以中文资源为主时必须关闭**

## 常见问题

### 启动报错数据库 no such column

用 [SqliteBrowser](https://github.com/sqlitebrowser/sqlitebrowser) 打开 config 目录下的
`user.db`，删除 `alembic_version` 表后重启。

### 启动 inotify 报错 / 目录同步不生效

在**宿主机**上（不是容器里）执行：

```bash
echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf
echo fs.inotify.max_user_instances=524288 | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### 电影/电视剧订阅一直队列中

- 订阅启用了「订阅站点」→ 设置 → 基础设置 → 服务 → 订阅 RSS 周期
- 订阅启用了「搜索站点」→ 设置 → 基础设置 → 服务 → 订阅搜索周期
- 添加后点击订阅，选择刷新

### 识别转移错误码 -1

- 硬链接跨盘：转移前后目录的根目录需相同
- 群晖中，不同的共享文件夹会被系统视为跨盘

### 电视剧订阅在完结前自动删除

- TMDB 词条未更新集数，或下载资源无法识别集数
- 可在订阅中手动设置总集数

## 免责

本软件仅供学习交流使用。基于开源代码修改后分发、传播所产生的一切责任，
由代码修改发布者承担。
