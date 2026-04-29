---
name: lark-shared
version: 1.0.0
description: "飞书/Lark CLI 共享基础：应用配置初始化、认证登录（auth login）、身份切换（--as user/bot）、权限与 scope 管理、Permission denied 错误处理、安全规则。当用户需要第一次配置(`lark-cli config init`)、使用登录授权(`lark-cli auth login`)、遇到权限不足、切换 user/bot 身份、配置 scope、或首次使用 lark-cli 时触发。"
---

# lark-cli 共享规则

本技能指导你如何通过lark-cli操作飞书资源, 以及有哪些注意事项。

## 用户输出规则

- 不要把 `lark-cli ...` 命令、脚本内容、终端步骤直接发给用户。
- 需要调用 `lark-cli` 时，由代理在内部直接执行，把执行后返回的链接给到用户；不要要求用户自己执行命令。
- 如果流程里需要用户参与配置、登录、授权、打开控制台或查看文档，只返回可点击的链接、页面入口或简短说明。
- `config init`、`auth login`、scope 授权、权限修复、版本更新这类场景，优先给用户链接和下一步说明，不要直接给命令。
- 认证和初始化链路里，agent 只负责发起、提取链接、返回给用户；不要用 shell 超时包装、重试循环或阻塞式等待来驱动用户交互。
- 用户可见回复里禁止出现 `lark-cli` 命令、代码块里的 shell 步骤、或“请执行以下命令”这类表述。

## 统一授权入口

以后不要在 `exec` 里直接运行裸命令 `lark-cli config init --new` 或 `lark-cli auth login ...` 去“碰运气”拿链接；统一通过本 skill 的脚本入口发起，再从 JSON 里的 `auth_url` 返回给用户。

```bash
# 配置初始化：内部执行，返回 JSON，其中 auth_url 为用户点击的链接
python <skill_dir>/scripts/auth_link.py config-init --timeout 30

# 用户增量授权：内部执行，返回 JSON，其中 auth_url 为用户点击的链接
python <skill_dir>/scripts/auth_link.py login --scope "search:message" --timeout 30
python <skill_dir>/scripts/auth_link.py login --domain calendar --timeout 30
```

强制规则：

- 不要把上述命令原样发给用户。
- 不要再额外套 shell `timeout`、后台轮询、重试循环或 `2>&1` 去“逼出”链接。
- 通过 `exec` / shell 在内部调用脚本时，脚本参数统一显式带 `--timeout 30`；工具层超时也必须至少覆盖脚本超时，建议 `timeout >= 35`，禁止再用 `timeout: 10`。
- 只要脚本返回了 `auth_url`，就立刻把该链接发给用户，并等待用户完成授权。
- 如果脚本没返回 `auth_url`，再根据 `stderr` / `message` 判断是 CLI 未安装、配置损坏还是 scope 问题；不要退化成“让用户自己去终端执行命令”。

## 配置初始化

首次使用需运行 `lark-cli config init` 完成应用配置。

当你帮用户初始化配置时，必须走统一脚本入口：

```bash
# 内部发起配置
python <skill_dir>/scripts/auth_link.py config-init --timeout 30
```

只把 `auth_url` 和简短说明发给用户；不要把内部命令原样发给用户。

- 不要再额外套 shell `timeout`、重试循环或二次包装命令去“逼出”链接。
- 一旦从输出中拿到授权链接，就立即返回给用户，等待用户完成后再继续原始请求。

## 认证

### 身份类型

两种身份类型，通过 `--as` 切换：

| 身份 | 标识 | 获取方式 | 适用场景 |
|------|------|---------|---------|
| user 用户身份 | `--as user` | `lark-cli auth login` 等 | 访问用户自己的资源（日历、云空间等） |
| bot 应用身份 | `--as bot` | 自动，只需 appId + appSecret | 应用级操作,访问bot自己的资源 |

### 身份选择原则

输出的 `[identity: bot/user]` 代表当前身份。bot 与 user 表现差异很大，需确认身份符合目标需求：

- **Bot 看不到用户资源**：无法访问用户的日历、云空间文档、邮箱等个人资源。例如 `--as bot` 查日程返回 bot 自己的（空）日历
- **Bot 无法代表用户操作**：发消息以应用名义发送，创建文档归属 bot
- **Bot 权限**：只需在飞书开发者后台开通 scope，无需 `auth login`
- **User 权限**：后台开通 scope + 用户通过 `auth login` 授权，两层都要满足


### 权限不足处理

遇到权限相关错误时，**根据当前身份类型采取不同解决方案**。

错误响应中包含关键信息：
- `permission_violations`：列出缺失的 scope (N选1)
- `console_url`：飞书开发者后台的权限配置链接
- `hint`：建议的修复命令

#### Bot 身份（`--as bot`）

将错误中的 `console_url` 提供给用户，引导去后台开通 scope。**禁止**对 bot 执行 `auth login`。

#### User 身份（`--as user`）

```bash
python <skill_dir>/scripts/auth_link.py login --domain <domain> --timeout 30         # 按业务域授权
python <skill_dir>/scripts/auth_link.py login --scope "<missing_scope>" --timeout 30 # 按具体 scope 授权（推荐）
```

**规则**：auth login 必须指定范围（`--domain` 或 `--scope`）。多次 login 的 scope 会累积（增量授权）。统一使用脚本在内部发起非阻塞认证。

#### Agent 代理发起认证（推荐）

当你作为 AI agent 需要帮用户完成认证时，在内部执行脚本发起授权流程，并将 `auth_url` 发给用户：

```bash
# 内部发起授权（非阻塞）
python <skill_dir>/scripts/auth_link.py login --scope "calendar:calendar:readonly" --timeout 30
```

只把授权链接和简短说明发给用户；不要把内部命令原样发给用户。

- 不要把 `auth login` 包在 shell `timeout`、后台轮询、重试循环或阻塞等待模式里。
- 如果使用工具调用，需要把工具层超时设到至少 35 秒，避免在授权链接输出前被外层 10 秒超时截断。
- 返回授权链接后，等待用户完成授权，再重试原始业务命令。


## 更新检查

lark-cli 命令执行后，如果检测到新版本，JSON 输出中会包含 `_notice.update` 字段（含 `message`、`command` 等）。

**当你在输出中看到 `_notice.update` 时，完成用户当前请求后，主动提议帮用户更新**：

1. 告知用户当前版本和最新版本号
2. 提议执行更新（CLI 和 Skills 需要同时更新）：
   ```bash
   npm update -g @larksuite/cli && npx skills add larksuite/cli -g -y
   ```
3. 更新完成后提醒用户：**退出并重新打开 AI Agent**以加载最新 Skills

**规则**：不要静默忽略更新提示。即使当前任务与更新无关，也应在完成用户请求后补充告知。向用户说明“需要更新 CLI 和 Skills”即可；如果你要代用户执行更新，就在内部执行，不要把更新命令原样发给用户。

## 安全规则

- **禁止输出密钥**（appSecret、accessToken）到终端明文。
- **写入/删除操作前必须确认用户意图**。
- 用 `--dry-run` 预览危险请求。
