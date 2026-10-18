# 江苏预防接种 APP · 余号监控提醒

只做**监控 + 提醒**，不自动预约、不绕过风控。零第三方依赖（纯 Python 标准库）。

## 为什么是自己搭

- 网上能搜到的「约苗 / 九价 抢苗」项目基本都停在 **2021–2022 年**（`xiangmingzhe0928/hpv4g`、`alexchenx/HPV_MiaoMiao`、`hbkooo/HPVOrder` 等），而且针对的是约苗公众号，不是江苏预防接种。
- **江苏预防接种 APP** 是江苏省疾控 2024 年才上线的官方应用（包名 `cn.app.jsepi.jsyfjz`，v1.2.2），目前**没有任何公开的逆向 / 监控项目**。
- 所以能复用的只有「轮询 + 判据 + 通知」这套骨架，接口必须自己抓包。本目录就是把骨架做成可配置的。

## 两种玩法

### 玩法 A：定时提醒（零抓包，5 分钟就能用）← 先用这个

不需要抓包、不需要 token。放号时间基本固定的门诊（江苏多数是工作日 7:30–8:00）
用这个就够：到点给你发封邮件，提醒你去 APP / 育苗通 手动预约。

```bash
python reminder.py --list    # 看提醒时间
python reminder.py --test    # 测邮件
python reminder.py           # 常驻，到点自动发
```

时间写在 `config.json` 的 `reminders.items`：`days` 支持 `["mon","tue",...]`
或 `["一","二"]`，`"*"` 表示每天；`time` 是 `HH:MM`。

### 玩法 B：全自动余号监控（需抓一次包）

抓到接口后，脚本自动轮询，**有号才提醒**，比定时提醒准得多。见下面「三步用法」。

---

### 1. 抓包，拿到接口

**手机端（推荐）**
1. 手机 Wi-Fi 代理指向电脑上的 Charles / Fiddler / mitmproxy（需在手机安装并信任证书）。
2. 打开江苏预防接种 APP，进入你要监控的页面（接种预约列表 / 紧俏疫苗预订），**手动刷新一次**，让它发出真实请求。
3. 在抓包工具里找到那个返回「号源列表 / 库存」的请求，右键 → **Copy as cURL**，或直接记录：URL、method、请求头（尤其 `token`、`Cookie`）、请求体。
4. 顺手跑一次 "Copy as cURL" → 转 Python 的网站（如 curlconverter），确认请求能在电脑上复现。

> **抓包指引（按你的环境选一份）**
> - [`抓包指引_iPhone免电脑.md`](抓包指引_iPhone免电脑.md) —— 只用 iPhone，装 Stream/Proxyman 自己抓
> - [`抓包指引_iOS.md`](抓包指引_iOS.md) —— 电脑跑 Charles，iPhone 做代理
> - [`抓包指引_PC微信小程序.md`](抓包指引_PC微信小程序.md) —— Windows 微信里开小程序抓（需 Proxifier）

**不用手填配置**：Charles 里右键 → 「Copy cURL Request」，然后直接跑

```bash
python curl2config.py        # 自动读剪贴板，写入 config.json
```

它会解析 URL / method / 请求头 / 请求体，并保留你已填好的邮箱设置。

**验证**：

```bash
python monitor.py --once
```

看 `monitor.log` 里的原始判断详情。如果返回的是「请重新登录 / 登录超时」，说明抓到的登录态不对或已过期，重抓。

### 2. 配判据（`detect`），告诉它什么叫「有号」

先看 `--once` 打印出来的 JSON 结构，再挑一个：

| 场景 | 判据写法 |
|---|---|
| 列表里存在可预约的项 | `{"type":"list_field_eq","path":"data.list","field":"status","value":"1"}` |
| 剩余数量 > 0 | `{"type":"list_field_gt","path":"data.list","field":"remainNum","value":"0"}` |
| 列表条数 > 0 | `{"type":"list_count_gt","path":"data.list","value":"0"}` |
| 某个开关为 true | `{"type":"json_path_true","path":"data.hasNumber"}` |
| 响应里出现固定字样 | `{"type":"contains","substring":"可预约"}` |
| 正则匹配 | `{"type":"regex","pattern":"剩余\\s*[1-9]"}` |

`path` 用点号表示层级，数组下标也写进去，例如 `data.result.list.0.status`。
`message_template` 里可用 `{name}`（配置里的 name）和 `{time}`，也可以在 `context` 里加自定义变量。

### 3. 配通知（`notify`），把 `enabled` 打开

| 通道 | 填什么 | 备注 |
|---|---|---|
| `bark` | iOS Bark App 里的推送 URL | 最省事，推荐 |
| `serverchan` | Server 酱 SendKey | 微信接收 |
| `pushplus` | pushplus token | 微信接收 |
| `wecom` | 企业微信群机器人 Webhook | 微信接收 |
| `dingtalk` | 钉钉群机器人 Webhook（+secret） | 自动算签名 |
| `email` | QQ/163 邮箱 + **授权码** | 注意不是登录密码 |
| `sound` | 无需配置 | 本机响铃/朗读，先开着调试用 |

填完先测一次：

```bash
python monitor.py --test-notify
```

## 运行方式

```bash
python monitor.py                # 常驻轮询
python monitor.py --once         # 只查一次（适合 cron / 计划任务）
python monitor.py --test-notify  # 只测通知
python monitor.py -c my.json     # 用别的配置文件
```

- **自己电脑**：直接 `python monitor.py`。
- **NAS / 云服务器**（7×24）：建议用 `--once` + 计划任务，例如每 2 分钟一次：
  ```
  */2 * * * * cd /path/to/vaccine_monitor && /usr/bin/python3 monitor.py --once >> cron.log 2>&1
  ```
- 去重逻辑：同一状态在 `renotify_cooldown_seconds`（默认 30 分钟）内只提醒一次；号没了会自动清标记，下次放号立刻再提醒。

## 重要提醒

- **登录态会过期**。`token` / `Cookie` 一般几小时到几天，失效后脚本会主动通知你「需重新抓包」。所以这个方案本质是「短周期值守」，不是一劳永逸。
- **放号时间**普遍在**工作日早上**（无锡太湖街道是提前一个工作日上午 8 点起，张家港是门诊开诊日 7:30，扬州 HPV 是每月固定日上午 8 点）。把 `quiet_hours` 设成夜间，间隔调到 30–60 秒，把频率集中在放号时段即可，别全天高频刷。
- 江苏预防接种 APP 本身自带**「接种通知提醒」和「紧俏疫苗预订 → 到苗及时通知」**。先确认官方通知够不够用——如果够，就不必折腾抓包。
- 请仅用于本人预约，控制请求频率，不要用于代抢、转卖。
