# iOS 抓包指引（江苏预防接种 APP · 儿童分时预约）

> 本文件是「**电脑 + iPhone**」方案：电脑上跑 Charles，iPhone 做代理转发。
> 如果你不想开电脑、只想用手机自己抓，看
> [`抓包指引_iPhone免电脑.md`](抓包指引_iPhone免电脑.md)。

目标：抓到「儿童预防接种分时预约」页面那个**返回号源列表**的请求，然后把它的
URL + 请求头（token / Cookie）+ 请求体 填进 `config.json`。

---

## 一、先确认一件事：能不能抓

江苏预防接种是政务类 APP，**有可能做了证书绑定（SSL Pinning）**。
现象是：Charles 里这个域名下的请求全部显示 `<ssl>` 或 `Connection closed`，
看不到明文内容。如果是这样，iOS 上基本无解（除非越狱用 frida 脱壳），
需要换安卓设备抓（安卓上绕过证书绑定更成熟）。

> 所以下面第 4 步「试抓」很关键，**不要跳过**。

---

## 二、方案 A：电脑 + Charles（推荐）

手机只做代理，电脑负责解密，能看到完整请求，也方便以后反复调试。

### 1. 电脑装 Charles

- 下载：https://www.charlesproxy.com/download/ （30 天试用，够用）
- Windows 首次启动会问是否允许防火墙，**选允许**。

### 2. 拿到电脑的局域网 IP

```bash
ipconfig
```

找当前 Wi-Fi 网卡的「IPv4 地址」，形如 `192.168.31.101`。

### 3. iPhone 设置代理

1. 设置 → 无线局域网 → 点当前 Wi-Fi 右边的 **ⓘ**
2. 拉到底 → **配置代理** → **手动**
3. 服务器：填电脑 IP（如 `192.168.31.101`）
4. 端口：`8888`
5. 存储

> ⚠️ iPhone 和电脑必须在**同一个 Wi-Fi**。

### 4. 安装并信任证书（最关键的一步，漏了就全是乱码）

1. **让 Charles 弹授权框**：先在 iPhone 上随便开个网页（如 example.com），
   Charles 会弹「A connection request…」，点 **Allow**。
2. iPhone **Safari** 打开 `chls.pro/ssl` → 下载描述文件 → 允许。
3. 设置 → 通用 → **VPN 与设备管理** → 找到 Charles Proxy CA → **安装**
   （要输锁屏密码）。
4. 设置 → 通用 → **关于本机** → 拉到最底 → **证书信任设置** →
   把 **Charles Proxy CA** 的开关**打开**。
   ⚠️ 这一步不打开，HTTPS 一律无法解密。

### 5. 开启 HTTPS 解密

Charles 菜单 → **Proxy → SSL Proxying Settings** → Add →
Host 填 `*`，Port 填 `443` → OK。

### 6. 试抓（验证链路）

- 先在 iPhone Safari 打开 `https://example.com`，Charles 里能看到明文 HTML
  = 链路通了。
- 再打开江苏预防接种 APP，进「儿童预防接种分时预约」页面。
- **看得到明文** → 继续。**只有 `<ssl>` / Connection closed** → 大概率是证书
  绑定，走本文件末尾的「方案 C」。

### 7. 抓目标请求

1. Charles 里点 **扫帚图标清空**（Clear）。
2. iPhone 上：进分时预约页 → **切换日期 / 下拉刷新 / 点「查询」**。
3. Charles 里按 `jsepi` 或 `appoint`、`order`、`subscribe` 之类的关键词过滤，
   找到那个**返回号源列表（一堆日期时间段 + 剩余数）**的请求。
4. 右键该请求 → **Copy cURL Request**（有的版本在 Copy URL 下拉里）。

> 提示：如果分不清哪个是，就看响应体——里面有几号、时间段、`status`/`remain`/
> `total` 这类字段的就是它。

---

## 三、方案 B：纯 iPhone，不装电脑

在 App Store 装 **Stream** 或 **HttpCatcher（网球）**，打开后按引导安装
VPN 描述文件 + 信任证书，然后在 App 内抓包、导出 cURL。

- 优点：不用电脑，几分钟上手。
- 缺点：只能抓本机流量；请求历史有限；长跑调试不方便；
  遇到证书绑定同样抓不到。

---

## 四、方案 C：抓不到该怎么办

按可能性从高到低：

1. **换成微信小程序入口**（如果江苏预防接种有小程序，或当地疾控公众号里有
   预约入口）。小程序走的是微信流量，Charles 里就是普通 HTTPS，通常更容易抓。
2. **换安卓设备/模拟器**抓。安卓侧绕过证书绑定手段多（root 后 frida /
   objection），或者部分机型改包即可。
3. **用「抓不到就监控不了」以外的路子**：直接依赖 APP 自带的
   「接种通知提醒」和「紧俏疫苗预订 → 到苗及时通知」。
   官方通知如果够快，就不用折腾了。

---

## 五、抓到之后（3 条命令）

```bash
cd D:\nas-tools-backup\vaccine_monitor

# 1. 在 Charles 里「Copy cURL Request」后，直接跑（自动读剪贴板）
python curl2config.py

# 2. 看一次真实返回，确认 token 有效、看清 JSON 结构
python monitor.py --once

# 3. 按实际结构改 config.json 里的 detect 判据，再测邮件
python monitor.py --test-notify
python monitor.py
```

### detect 判据怎么改（看你 --once 打印出来的 JSON）

| 返回长什么样 | 判据 |
|---|---|
| `{"data":{"list":[{"status":"1",...}]}}` | `{"type":"list_field_eq","path":"data.list","field":"status","value":"1"}` |
| 列表里有 `remainNum` / `surplus` 剩余数 | `{"type":"list_field_gt","path":"data.list","field":"remainNum","value":"0"}` |
| 号源是 `{"date":"2026-10-13","times":[{"id":66505}]}` 两层嵌套 | 用 `list_count_gt` 配 `path` 指向时间段那层，如 `data.list.0.times` |
| 直接返回 `{"data":{"hasNumber":true}}` | `{"type":"json_path_true","path":"data.hasNumber"}` |
| 返回里有「可预约」字样 | `{"type":"contains","substring":"可预约"}` |

`path` 用点号分层，数组下标直接写数字，如 `data.result.list.0.status`。

---

## 六、QQ 邮箱授权码怎么拿（发通知用）

1. 电脑浏览器登录 QQ 邮箱 → 设置 → **账号**
2. 找到「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务」
3. 开启 **IMAP/SMTP 服务**（要短信验证）
4. 生成 **授权码**（16 位字母）
5. 把它填到 `config.json` 的 `notify.email.password`，
   ⚠️ **不是 QQ 登录密码**。

`mail.163.com`、`smtp.163.com` 同理；Gmail 需要开应用专用密码。

---

## 七、几个容易踩的坑

- **先关掉 iPhone 的移动数据**（或让 APP 走 Wi-Fi），否则走 4G 的请求抓不到。
- **APP 启动时就建长连接**，所以顺序要「清空 Charles → 打开 APP → 操作」，
  不要先开着 APP 再清空。
- 抓完记得 **iPhone 设置 → 关掉 Wi-Fi 代理**，否则断网。
- 抓到的 `token` 一般几小时到几天就失效，脚本会发邮件提醒你「需重新抓包」，
  重跑一次 `curl2config.py` 就行。
