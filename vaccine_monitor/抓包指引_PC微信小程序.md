# PC 微信小程序抓包（Windows）

**结论：能抓。** PC 微信小程序跑在 `WeChatAppEx.exe` 里，用 **Proxifier 强制进程走代理**
就能抓到，还不用折腾手机证书。

---

## 第 0 步：先确认两件事（不确认就白忙）

### ① 那个小程序里到底有没有「儿童分时预约」

江苏省内**儿童预防接种预约的官方入口是 APP（江苏预防接种）**；微信小程序里更常见的
是 **「育苗通」**，主要用于 HPV/成人疫苗预约。

所以先确认：**你要监控的那个「儿童分时预约」页面，在微信小程序里有没有？**

- 有 → 继续往下
- 没有 → 这条路不通，回 APP 抓（见 `抓包指引_iOS.md` / `抓包指引_iPhone免电脑.md`）

### ② 小程序有没有做证书钉扎

先按下面步骤配好，随便打开一个小程序点几下。如果看到请求了（能看明文）→ 成功；
如果全是 `SSL` / `Connection closed` → 被钉扎了，换安卓抓（见文末）。

---

## 工具

| 工具 | 作用 | 说明 |
|---|---|---|
| **Fiddler Classic** | 抓包/解密 | **免费**，够用 |
| 或 Charles | 抓包/解密 | 30 天试用 |
| **Proxifier** | 强制指定进程走代理 | **必需**，31 天试用 |
| 任务管理器 | 找 `WeChatAppEx.exe` 路径 | 系统自带 |

---

## 第 1 步：抓包工具装好并信任根证书

### Fiddler Classic（免费路线）

1. 下载安装 Fiddler Classic。
2. **Tools → Options → HTTPS**：
   - 勾选 `Capture HTTPS CONNECTs`
   - 勾选 `Decrypt HTTPS traffic`
   - 点 **Actions → Trust Root Certificate** → 一路 Yes
3. **Tools → Options → Connections**：确认监听端口（默认 `8888`），勾选
   `Allow remote computers to connect`（同机抓包其实用不到，勾了无妨）。
4. 验证证书落在正确位置：运行 `certmgr.msc` → **受信任的根证书颁发机构 → 证书**，
   应该能看到 `DO_NOT_TRUST_FiddlerRoot`。

### Charles 路线

1. 装好 Charles → **Help → SSL Proxying → Install Charles Root Certificate**
   → 存储位置选「**当前用户**」→ 导出成 `.cer` → 双击导入到
   **受信任的根证书颁发机构**。
2. **Proxy → SSL Proxying Settings → Add**：Host `*`，Port `443`。
3. 监听端口默认 `8888`。

---

## 第 2 步：Proxifier 强制 WeChatAppEx.exe 走代理

### 2.1 找到小程序进程路径

1. PC 微信里**先打开任意一个小程序**。
2. 任务管理器（`Ctrl+Shift+Esc`）→ 进程页 → 找到 **`WeChatAppEx`** 进程组。
3. 展开 → 右键任一 `WeChatAppEx` 进程 → **「打开文件所在的位置」**。
4. 复制资源管理器地址栏里的完整目录，记下 `WeChatAppEx.exe` 的完整路径。

### 2.2 Proxifier 加代理服务器

**Profile → Proxy Servers → Add**
- Address：`127.0.0.1`
- Port：`8888`（与你抓包工具一致）
- Protocol：**HTTPS**（用 Burp 时选 HTTP，Charles/Fiddler 选 HTTPS 均可，报错就换另一个）

### 2.3 Proxifier 加规则

**Profile → Proxification Rules → Add**
- Name：`WeChat MiniProgram`
- Applications：**Browse** → 粘贴 2.1 里的路径 → 选中 `WeChatAppEx.exe`
- Target hosts / ports：保持 `Any`
- Action：选 2.2 建的代理
- ⚠️ **把这条规则拖到 `Default` 规则的上方**（优先级更高）

### 2.4 两个必改的细节

- **Profile → Name Resolution** → 勾选 **`Resolve hostnames through proxy`**
  （不勾会出现 DNS 解析问题、抓不到）
- **关掉系统代理**：Windows 搜索「Internet 选项」→ 连接 → 局域网设置 →
  确认「为 LAN 使用代理服务器」**未勾选**。系统代理会和 Proxifier 打架。

---

## 第 3 步：抓

1. **完全退出 PC 微信**（托盘右键退出，不是关窗口），再重新打开。
2. 打开那个小程序 → 进「儿童分时预约」页 → **切换日期 / 下拉刷新**。
3. 看 Proxifier 主窗口，应该出现 `WeChatAppEx.exe` 的流量记录。
4. 切到 Fiddler/Charles，找到那个**返回号源列表**的请求
   （按域名或 `appoint`/`order`/`reserve`/`subscribe` 等关键字过滤）。
5. 右键 → **Copy → Copy as cURL**。

---

## 抓不到？按这个顺序排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 完全没流量 | 规则没生效 | 确认规则在 Default **上方**、Application 指向 `WeChatAppEx.exe` |
| 没有流量 | 微信走了 QUIC/HTTP3（UDP 443） | 见下方「关于 QUIC」 |
| 有 tunnel/443 但无明文 | 证书没装到**受信任的根** | `certmgr.msc` 里检查位置 |
| 全 `Connection closed` | **小程序做了证书钉扎** | 换安卓抓，或改用 APP 抓 |
| 一开代理微信就报网络异常 | 系统代理冲突 | 关掉系统代理，只留 Proxifier |

### 关于 QUIC（很常见的坑）

微信新版可能用 QUIC（HTTP/3，走 **UDP 443**），而 HTTP 代理只管 TCP。
抓不到时，用一条命令临时挡掉 UDP 443（**管理员** PowerShell / CMD）：

```
netsh advfirewall firewall add rule name="block-quic-443" dir=out protocol=udp remoteport=443 action=block
```

抓完删除：

```
netsh advfirewall firewall delete rule name="block-quic-443"
```

---

## 第 4 步：抓到之后

把复制出来的 cURL **直接粘贴发我**即可；或自己放到电脑上跑：

```bash
cd D:\nas-tools-backup\vaccine_monitor
python curl2config.py curl.txt
python monitor.py --once
```

---

## 如果小程序被钉扎 / 干脆没有小程序

按优先级：

1. **回 APP 抓**（`抓包指引_iPhone免电脑.md` / `抓包指引_iOS.md`）。
2. **用安卓抓微信小程序**：手机微信打开小程序 + Charles 代理，安卓侧绕过
   钉扎手段成熟。PC 上也可以用安卓模拟器装微信。
3. 走 APP 自带的「接种通知提醒」，不折腾抓包。

---

## 提醒

- 抓包时**别同时开着系统代理**，两者只能留一个。
- 微信每次更新后 `WeChatAppEx.exe` 路径可能变，抓不到就先回第 2.1 步重找路径。
- 抓完记得删掉 Proxifier 规则 / 关掉抓包工具，否则微信会一直走代理变慢。
