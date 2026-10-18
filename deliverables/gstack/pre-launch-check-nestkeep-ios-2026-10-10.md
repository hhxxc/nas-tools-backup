# 上线前全检报告 — NestKeep iOS（native-ios-app 分支）

**日期**：2026-10-10
**场景**：上线前检查（代码审查 + 安全审计 + QA 测试）
**参与成员**：产品评审员 + 安全卫士 + 质量门神
**检查对象**：`D:/ezbk-native-wt`（branch `native-ios-app`，相对 origin/main 约 106 文件 / 2 万行增量）

---

## 📌 TL;DR（执行摘要）

- 整体结论：🟡 有条件通过 —— 架构与安全基本功扎实，但存在 2 个 P0 阻塞项必须先修复
- 阻塞项：2（未提交改动 + Info.plist 文档类型声明错误）
- 核心风险：发布流程脏（未提交/误入库）、PDF 识别链路可能根本注册不了、HTTPS 未强制 + 明文凭据
- 下一步：先提交/清理工作区 → 修 P0 → 重推触发 CI 打包验证

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| Go / No-Go | 🟡 条件 Go（修复 2 个 P0 后可发） |
| 严重度分布 | 🔴 4 / 🟠 4 / 🟡 4 / 🟢 — |
| 关键行动项 | 8 条 |
| 建议负责人 | 工程负责人（用户本人） |

---

## 1. 各成员核心结论

### 🔍 产品评审员（代码审查）
- 核心判断：整体架构分层清晰（Core/Models/Views），状态管理用 @MainActor + 统一 Task 模式规范，边界处理细致；但发现 2 个功能性 bug 和 1 处死代码。
- 关键发现：
  - 🔴 **Info.plist 文档类型声明错误**（`ios-shell/NestKeep/Info.plist`：`CFBundleTypeName` 为 `public.plain-text`，但内容类型声明为 PDF）——可能导致系统分享/打开 PDF 时无法唤起应用、识别链路失效。
  - 🔴 **`TransactionsView.swift` 死代码**：AI 解析后的交易被 append 到本地 `var transactions` 数组，但该数组从未绑定 UI、也从未上传服务器，"识别后入账"在此路径根本不会发生。
  - 🟡 `SecureField` 依赖 iOS 15+ API，需确认部署目标一致性。
- 建议：修复 Info.plist、移除或接通死代码路径，重推触发 CI 验证。

### 🛡️ 安全卫士（OWASP + STRIDE 审计）
- 核心判断：无致命漏洞（🔴 级），但 HTTPS 未强制 + 明文存储凭据两项必须修。
- 关键发现：
  - 🔴 **HTTPS 未强制**：`APIClient.swift` 生成 URL 后未校验 scheme，`http://` 明文传输（token/交易数据可被中间人窃取）；ATS 未显式配置禁明文，iOS 默认 ATS 虽拦截但存在例外配置风险。
  - 🟠 **凭据明文存储**：token/用户名/密码用 UserDefaults 存放，越狱设备可直接读取；应迁移 Keychain。
  - 🟠 **服务端更新清单路由**：`cmd/server/router.go` 的 `:name` 兜底解析若用 `filepath.Join` 拼路径，`../` 可路径穿越读任意文件（当前代码未见防护）。
  - 🟢 隐私清理彻底：仓库内未检出个人服务器地址/内网 IP 残留（历史提交的清理有效）。
- 建议：强制 https scheme 校验、凭据迁移 Keychain、清单路由白名单化文件名（如正则限定 `latest-[a-z0-9-]+\.json`）。

### ✅ 质量门神（QA 与发布检查）
- 核心判断：🔴 当前状态不可直接发布 —— 工作区脏 + 无任何测试覆盖 + 无 CI 构建 workflow。
- 关键发现：
  - 🔴 **2 个文件未提交**（`ios-app/NestKeep/Core/UI.swift`、`Views/TransactionsView.swift`）+ 未跟踪 `dist-ipa/`（构建产物，绝不能入库，需加 .gitignore）。
  - 🔴 **CI 缺失**：仓库内找不到 `.github/workflows` 中针对 `ios-app/**` 的 IPA 构建配置（或配置不含签名/导出步骤），push 触发打包链路需要实测验证。
  - 🟠 **零测试**：Swift 端无单测 target；Go 端增量（幂等去重、血缘标记）也未见对应测试文件。
  - 🟡 版本号/构建号未见自动递增机制，多次打包易混淆。
- 建议：发布检查清单 + 回滚预案见下方行动清单；回滚要点——保留上一版 IPA 归档，更新清单 `latest-<channel>.json` 支持指向旧版本号即可快速回退。

---

## 2. 综合审查发现（按严重度排序）

| # | 严重度 | 类别 | 位置 | 问题 | 建议 | 来源 |
|---|--------|------|------|------|------|------|
| 1 | 🔴 | 发布 | 工作区 | UI.swift / TransactionsView.swift 未提交，dist-ipa/ 未跟踪 | 提交或丢弃改动；.gitignore 加入 dist-ipa/ | 质量门神 |
| 2 | 🔴 | 功能 | ios-shell/NestKeep/Info.plist | PDF 文档类型声明错误（public.plain-text） | 改为 `com.adobe.pdf` 并回归测试分享打开 | 产品评审员 |
| 3 | 🔴 | 功能 | ios-app/.../TransactionsView.swift | AI 解析结果 append 后未上传未展示，链路断裂 | 接通确认→上传流程或删除死代码 | 产品评审员 |
| 4 | 🔴 | 安全 | ios-app/.../APIClient.swift | 未强制 HTTPS，http 明文可传 token | URL 构造时校验/强制 https scheme | 安全卫士 |
| 5 | 🟠 | 安全 | ios-app/.../AuthManager.swift 等 | 凭据 UserDefaults 明文存储 | 迁移 Keychain（kSecClassGenericPassword） | 安全卫士 |
| 6 | 🟠 | 安全 | cmd/server（变体清单路由） | :name 拼路径无穿越防护 | 文件名白名单正则校验 | 安全卫士 |
| 7 | 🟠 | 发布 | .github/workflows | ios-app IPA 构建配置缺失/未验证 | 补齐签名+导出步骤并实测一次打包 | 质量门神 |
| 8 | 🟠 | 质量 | 全仓库 | Swift/Go 增量零测试覆盖 | 至少补幂等去重、文本解析两类单测 | 质量门神 |
| 9 | 🟡 | 兼容 | SecureField 等 | iOS 15+ API 与部署目标一致性 | 核对 deployment target | 产品评审员 |
| 10 | 🟡 | 发布 | 版本管理 | 版本/构建号无自动递增 | CI 中注入 build number | 质量门神 |
| 11 | 🟡 | 安全 | Info.plist ATS | 未显式声明 NSAppTransportSecurity 策略 | 显式禁止明文，防后续误加例外 | 安全卫士 |
| 12 | 🟢 | 安全 | 全仓库 | 隐私信息（IP/服务器地址）清理彻底 | 保持该习惯 | 安全卫士 |

---

## ✅ 行动清单

| # | 行动 | 负责方 | 紧急度 | 期望完成 |
|---|------|--------|--------|---------|
| 1 | 提交/清理 2 个未提交文件，.gitignore 加 dist-ipa/ | 本人 | P0 | 立即 |
| 2 | 修复 Info.plist PDF 文档类型声明 | 本人 | P0 | 发版前 |
| 3 | APIClient 强制 https scheme | 本人 | P0 | 发版前 |
| 4 | 凭据迁移 Keychain | 本人 | P1 | 下一版 |
| 5 | 服务端变体清单路由加文件名白名单 | 本人 | P1 | 发版前 |
| 6 | 补齐/实测 ios-app CI 打包 workflow | 本人 | P1 | 发版前 |
| 7 | 移除/接通 TransactionsView 死代码链路 | 本人 | P1 | 发版前 |
| 8 | 补幂等去重与文本解析单测 | 本人 | P2 | 下一版 |

---

## ⚠️ 待完善 / 已知局限

- 本机为 Windows，无法实际运行 iOS 构建与真机回归，Info.plist 修复与 HTTPS 强制需在 macOS 侧回归验证。
- 服务端路由穿越风险为静态代码推断，建议用 `latest-../../etc/passwd` 类请求实测确认。

---

## 📚 成员产出索引

- 产品评审员原始产出：见会话成员消息（Info.plist/死代码/架构评审）
- 安全卫士原始产出：见会话成员消息（HTTPS/凭据/路径穿越/隐私扫描）
- 质量门神原始产出：见会话成员消息（工作区状态/CI/测试覆盖/发布清单）

---

> 本报告由软件工坊 AI 协作生成，关键决策请由工程负责人复核。
