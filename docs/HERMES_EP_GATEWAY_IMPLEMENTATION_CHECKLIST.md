# Hermes 对照 ep-gateway 实施清单

## 1. 文档目的

本文档用于回答四个问题：

1. `Hermes` 里与“自学习 / 自进化 / Skill 创建与演化”有关的代码到底是什么。
2. `ep-gateway` 当前已经具备哪些可承接这些能力的基础设施。
3. 在“非侵入式集成”前提下，哪些能力值得借鉴，哪些暂时不该迁移。
4. 后续应如何按“先新增文件，再薄接线”的方式落地。

本文档基于以下两个仓库的源码核对：

- Hermes：`D:\github\hermes-agent`
- ep-gateway：`D:\github\ep-gateway`

## 2. 先说结论

### 2.1 Hermes 真正值得迁移的，不是 RL，而是运行时学习闭环

Hermes 日常 Agent 运行时的“自学习”，核心不是模型训练，也不是强化学习，而是下面这条闭环：

1. Prompt 明确区分 `memory`、`session recall`、`skill`
2. Agent 通过专用工具写入 `memory` 或 `skill`
3. 主任务完成后，后台 reviewer 对本轮执行做复盘
4. reviewer 决定是否新建 skill、patch skill、补充记忆
5. 后续任务再通过 `skill` / `memory` / `session_search` 复用这些经验

### 2.2 Hermes 的 RL / Atropos 是独立子系统，不是日常自学习主线

Hermes 仓库里确实有 RL 训练子系统，但它和日常 Agent 运行并不是一套机制：

- RL 相关代码在 `environments/` 和 `tools/rl_training_tool.py`
- RL 配置是独立 toolset
- RL 环境中反而显式关闭了普通运行时 `memory` / `session_search`

所以：

- `Hermes 有 RL` 这件事成立
- `Hermes 日常 Agent 自学习依赖 RL` 这件事不成立

### 2.3 对 ep-gateway 来说，V1 最值得借鉴的是 4 件事

建议优先借鉴：

1. `skill_manage`
2. 后台 `SkillReview`
3. `session_search`
4. 更清晰的 `memory / session recall / skill` 边界

不建议 V1 优先迁移：

1. RL / Atropos 训练平台
2. Hermes 全局 `~/.hermes/skills` 模式
3. 自动直接修改 builtin skill

## 3. Hermes 与本项目的关键差异

## 3.1 Hermes 运行时学习主线

Hermes 已形成完整的运行时学习链路：

- Prompt 层持续提醒模型何时沉淀 skill、何时 patch skill
- `skill_manage` 提供受控写入口
- `memory` tool 允许 agent 显式维护 curated memory
- `session_search` 允许跨会话召回历史 transcript
- 主任务结束后可触发后台 review

对应核心能力：

- Skill 不是静态文档，而是可演化资产
- 运行时经验可以落盘
- 后续任务可以主动检索并复用经验

## 3.2 ep-gateway 当前主线

`ep-gateway` 当前已有的基础设施其实很强，但更偏“系统管理型”，不是“Agent 运行时显式学习型”：

- `ContextBuilder` 负责上下文装配
- `AgentLoop` 负责工具注册、主循环、后台任务调度
- `AgentHook` 提供生命周期扩展点
- `MemoryStore + Consolidator + Dream` 负责长期记忆沉淀
- `SessionManager` 负责会话持久化
- `OpenViking` 负责语义记忆召回
- `SkillsLoader` 负责 builtin / workspace skill 扫描和摘要注入

当前缺口主要在：

- 缺少一等公民的 `skills_list`
- 缺少一等公民的 `skill_view`
- 缺少受控写入口 `skill_manage`
- 缺少任务后后台 `SkillReview`
- 缺少独立 transcript recall 工具
- 缺少 generated skill 存储层和事件审计

## 4. 非侵入式集成原则

这是本次设计的硬约束。

### 4.1 总原则

必须遵守以下方式：

1. 优先新增文件承载新逻辑
2. 现有文件只做薄接线
3. 不在老文件里堆大量新函数
4. 不重构现有主循环、记忆系统、会话系统
5. 新能力必须可开关、可回退、可审计

### 4.2 禁止事项

以下做法不建议采用：

- 大幅改写 `nanobot/agent/runner.py`
- 大幅改写 `nanobot/agent/hook.py`
- 大幅改写 `nanobot/agent/memory.py`
- 大幅改写 `nanobot/session/manager.py`
- 把 `SkillReview` 逻辑直接塞进 `Dream`
- 把 `skill_manage` 直接做成通用文件写工具的变体
- 让 Agent 自动修改 repo 内 builtin skills

### 4.3 推荐方式

推荐采用下面的开发顺序：

1. 新增模块
2. 在新模块内把核心逻辑写完整
3. 再在现有入口文件做最小接线
4. 最后补模板、配置和 Web/API 接口

## 5. 现有代码里允许动的接入点

下面这些文件可以改，但只能做薄接线。

### 5.1 `nanobot/agent/context.py`

允许改动：

- 把 skill 提示从“用 `read_file` 去读”调整为“优先用 `skills_list` / `skill_view`”
- 注入新的 skill 使用规则

不建议改动：

- 上下文拼装总体流程
- Memory / OpenViking 现有注入逻辑

### 5.2 `nanobot/agent/loop.py`

允许改动：

- 注册新工具
- 在主回复结束后调用 `_schedule_background(...)` 挂载 `SkillReview`
- 注入一个很薄的 review 触发点

不建议改动：

- 主循环结构
- 工具执行机制
- Session 保存机制
- Consolidator / Dream 调度主线

### 5.3 `nanobot/config/schema.py`

允许改动：

- 新增 `SkillsConfig`
- 增加 generated skill / review / guard 的配置项

不建议改动：

- 现有 providers / tools / dream 结构

### 5.4 `nanobot/templates/agent/skills_section.md`

允许改动：

- 改写提示词，引导模型使用新 skill 工具

### 5.5 `nanobot/web/server.py`

允许改动：

- Skill 上传下载接口改为复用新的校验 / 存储逻辑
- 增加 generated skill 的只读展示或治理接口

不建议改动：

- Web 主路由结构
- 聊天主链路

### 5.6 `nanobot/agent/skills.py`

允许改动：

- 保持为 skill 目录聚合入口
- 小幅扩展为 source-aware catalog

不建议改动：

- 在这个文件里塞入写入、审计、review、guard 全部逻辑

## 6. 现有文件改动级别建议

| 文件 | 改动级别 | 允许内容 | 禁止内容 |
| --- | --- | --- | --- |
| `nanobot/agent/context.py` | 低 | 模板替换、调用新 catalog | 改造上下文主流程 |
| `nanobot/agent/loop.py` | 低 | 工具注册、review 调度 | 改 Agent 主循环 |
| `nanobot/agent/skills.py` | 中低 | catalog 聚合扩展 | 塞入完整 skill 生命周期 |
| `nanobot/config/schema.py` | 低 | 新配置模型 | 重排现有配置体系 |
| `nanobot/templates/agent/skills_section.md` | 低 | prompt 文案更新 | 无 |
| `nanobot/web/server.py` | 低 | 调用新校验模块 | 重写 Web skill 路由框架 |
| `nanobot/agent/hook.py` | 极低 | 如确有必要仅加薄上下文字段 | 大改 Hook 协议 |
| `nanobot/agent/memory.py` | 极低 | 尽量不改 | 把 skill 逻辑硬塞进去 |
| `nanobot/session/manager.py` | 极低 | 尽量不改 | 为 session_search 大改存储结构 |

## 7. 新增文件优先矩阵

以下能力应尽量全部落在新文件中。

| 新文件 | 责任 | 是否 V1 必需 |
| --- | --- | --- |
| `nanobot/agent/tools/skills.py` | `skills_list` / `skill_view` / `skill_manage` 工具暴露 | 是 |
| `nanobot/agent/skill_store.py` | generated skill 写入、patch、审计、manifest | 是 |
| `nanobot/agent/skill_review.py` | 任务后异步复盘，决定 create / patch / ignore | 是 |
| `nanobot/agent/skill_guard.py` | skill 静态扫描与风险拦截 | V1.5 |
| `nanobot/agent/tools/session_search.py` | 跨会话检索历史 transcript | V1.5 |
| `nanobot/session/search_index.py` | session 索引或 SQLite/FTS 封装 | V1.5 |
| `nanobot/agent/skill_dream.py` | 离线扫描历史，挖掘可复用流程 | V2 |
| `nanobot/templates/agent/skill_review.md` | reviewer 提示词模板 | 是 |

## 8. 推荐目标架构

## 8.1 组件划分

建议新增 5 个核心组件：

1. `SkillCatalog`
2. `SkillStore`
3. `SkillToolset`
4. `SkillReviewService`
5. `SessionSearchService`

其中：

- `SkillCatalog` 负责读路径
- `SkillStore` 负责写路径
- `SkillToolset` 负责给模型暴露工具
- `SkillReviewService` 负责后台进化
- `SessionSearchService` 负责 transcript recall

## 8.2 与现有系统的边界

建议明确三类知识边界：

### 8.2.1 Curated Memory

承载内容：

- 用户长期偏好
- 稳定事实
- 持久规则

继续由当前 `MemoryStore / Dream / OpenViking` 体系负责。

### 8.2.2 Session Recall

承载内容：

- 过去某次对话里具体怎么做过
- 某个历史任务的执行片段
- 与当前查询相关的历史 transcript

由新增 `session_search` 负责，不混进 `MEMORY.md`。

### 8.2.3 Skill

承载内容：

- 可复用工作流
- 推荐命令和步骤
- 常见坑和验证方法
- 特定任务套路

由 `SkillCatalog + SkillStore + SkillReview` 负责。

## 9. Hermes 对照到 ep-gateway 的映射

| Hermes 能力 | Hermes 形态 | ep-gateway 现状 | 推荐落地方式 |
| --- | --- | --- | --- |
| Skill 发现 | `skills_list` / metadata | 只有 summary 注入 | 新增 `skills_list` |
| Skill 查看 | `skill_view` | 依赖 `read_file` | 新增 `skill_view` |
| Skill 写入 | `skill_manage` | 没有 | 新增 `skill_manage + SkillStore` |
| Skill 后台进化 | review agent | 没有 | 新增 `SkillReviewService` |
| 跨会话召回 | `session_search` | 只有 session JSONL 持久化 | 新增 `session_search` |
| 长期记忆编排 | `MemoryManager` | `MemoryStore + Dream + OpenViking` | V2 再统一编排 |
| RL 训练 | RL toolset | 没有 | 暂不做 |

## 10. 分阶段开发计划

## 10.1 Phase 0：冻结边界和接线规则

目标：

- 把“非侵入式集成”变成开发约束，而不是口头要求

工作项：

- [ ] 明确 generated skill 目录固定为 `<workspace>/.agent-state/skills/`
- [ ] 明确 builtin / workspace curated / generated 三层来源
- [ ] 明确 V1 禁止自动修改 builtin / curated
- [ ] 明确 review 失败不得影响主回复
- [ ] 明确 session_search 不改写 `SessionManager` 存储格式

交付物：

- 本文档
- 配置草案
- 目录草案

## 10.2 Phase 1：把 Skill 变成一等公民读取对象

目标：

- 不再依赖模型自己猜路径用 `read_file` 读取 skill

新增文件：

- `nanobot/agent/tools/skills.py`

薄接线文件：

- `nanobot/agent/skills.py`
- `nanobot/agent/context.py`
- `nanobot/agent/loop.py`
- `nanobot/templates/agent/skills_section.md`

工作项：

- [ ] 在 `nanobot/agent/skills.py` 中扩展出 `SkillCatalog`
- [ ] Skill 来源扩展为 builtin / workspace curated / generated
- [ ] 暴露 `skills_list`
- [ ] 暴露 `skill_view`
- [ ] 在 `skills_section.md` 中改为引导模型优先使用 skill 工具
- [ ] 在 `loop.py` 中注册 skill 工具

验收标准：

- [ ] Agent 可列出 skill
- [ ] Agent 可读取 `SKILL.md`
- [ ] Agent 可识别 skill `source` 与 `mutable`

## 10.3 Phase 2：引入 generated SkillStore

目标：

- 提供受控、可审计的 skill 写入口

新增文件：

- `nanobot/agent/skill_store.py`

薄接线文件：

- `nanobot/agent/tools/skills.py`
- `nanobot/agent/skills.py`

工作项：

- [ ] 建立 `<workspace>/.agent-state/skills/`
- [ ] 增加 `manifest.json`
- [ ] 增加 `skill-events.jsonl`
- [ ] 实现 `create`
- [ ] 实现 `edit`
- [ ] 实现 `patch`
- [ ] 实现 `delete`
- [ ] 实现 `write_file`
- [ ] 实现 `remove_file`
- [ ] 限制 supporting file 只能在 `references/` `templates/` `scripts/` `assets/`
- [ ] 做 frontmatter 校验
- [ ] 做路径 containment 校验
- [ ] 做原子写入

策略约束：

- [ ] V1 只允许自动改 generated skill
- [ ] builtin / curated 只能 clone overlay 后再 patch

验收标准：

- [ ] Agent 可以创建 generated skill
- [ ] Agent 可以 patch generated skill
- [ ] 非法路径被拒绝
- [ ] builtin / curated 不会被直接自动修改

## 10.4 Phase 3：上线后台 SkillReview

目标：

- 建立 Hermes 风格运行时 skill 自进化闭环

新增文件：

- `nanobot/agent/skill_review.py`
- `nanobot/templates/agent/skill_review.md`

薄接线文件：

- `nanobot/agent/loop.py`
- `nanobot/config/schema.py`

工作项：

- [ ] 定义 review 输入对象
- [ ] 收集本轮 user message / assistant response / tool calls / tool results summary / used skills
- [ ] 定义 review 触发条件
- [ ] 主回复结束后通过 `_schedule_background(...)` 异步 review
- [ ] review 结果只允许 `create` / `patch` / `clone-then-patch` / `ignore`
- [ ] 将变更写入 `skill-events.jsonl`
- [ ] review 全流程可配置关闭

验收标准：

- [ ] 主回复不被 review 阻塞
- [ ] 复杂任务后可自动创建或 patch generated skill
- [ ] review 失败不影响主任务

## 10.5 Phase 4：补齐 session_search

目标：

- 补上 Hermes `session_search` 对应能力

新增文件：

- `nanobot/agent/tools/session_search.py`
- `nanobot/session/search_index.py`

尽量不改文件：

- `nanobot/session/manager.py`

工作项：

- [ ] 直接复用现有 session JSONL 数据
- [ ] 先实现 recent / keyword search
- [ ] 再视情况补 SQLite/FTS
- [ ] 支持命中 session 的 focused summary
- [ ] 默认排除当前 session

验收标准：

- [ ] Agent 可主动检索历史会话
- [ ] 无需把大量旧对话硬塞入 `MEMORY.md`

## 10.6 Phase 5：安全与治理

目标：

- 让 skill 自进化能力可上线、可审计

新增文件：

- `nanobot/agent/skill_guard.py`

薄接线文件：

- `nanobot/web/server.py`
- `nanobot/agent/skill_store.py`

工作项：

- [ ] Skill 静态扫描
- [ ] Web zip 上传路径校验
- [ ] zip-slip 拦截
- [ ] 文件大小限制
- [ ] supporting file 类型限制
- [ ] 完整事件日志

验收标准：

- [ ] 自动 skill 变更可审计
- [ ] 危险 skill 可阻断或标记

## 10.7 Phase 6：离线 SkillDream

目标：

- 从历史中挖掘在线 review 漏掉的可复用工作流

新增文件：

- `nanobot/agent/skill_dream.py`

原则：

- 不并入当前 `Dream`
- 独立调度、独立配置、独立日志

工作项：

- [ ] 扫描未处理历史
- [ ] 识别重复工作流
- [ ] 通过 `skill_manage` 生成 skill
- [ ] 记录 dream cursor

## 11. 配置设计建议

建议在 `nanobot/config/schema.py` 增加独立配置：

```python
class SkillsConfig(Base):
    enabled: bool = True
    generated_dir: str = ".agent-state/skills"
    review_enabled: bool = False
    review_mode: Literal["off", "suggest", "auto_patch", "auto_create"] = "auto_patch"
    review_trigger_iterations: int = 8
    review_min_tool_calls: int = 5
    review_model_override: str | None = None
    allow_create: bool = True
    allow_patch: bool = True
    allow_delete: bool = False
    guard_enabled: bool = True
    notify_user_on_change: bool = True
    session_search_enabled: bool = False
    dream_enabled: bool = False
```

推荐默认值：

- `enabled = true`
- `review_enabled = false`
- `allow_delete = false`
- `session_search_enabled = false`
- `dream_enabled = false`

也就是先把读能力和受控写能力做好，再灰度打开自动 review。

## 12. 代码开发方式建议

## 12.1 推荐开发顺序

1. 先写 `SkillCatalog`
2. 再写 `SkillToolset`
3. 再写 `SkillStore`
4. 再挂 `skill_manage`
5. 再接后台 `SkillReview`
6. 再补 `session_search`
7. 最后补 `skill_guard` 和 `skill_dream`

## 12.2 每一步都遵循这个模式

1. 新增文件完成主体逻辑
2. 写单元测试
3. 在现有文件接一根很薄的线
4. 开关默认保守关闭
5. 做日志和审计

## 12.3 不要采用的实现方式

- 不要先改 `loop.py` 再慢慢补模块
- 不要把复杂逻辑放到 `context.py`
- 不要让 `web/server.py` 自己做 SkillStore 逻辑
- 不要让 `memory.py` 同时承担 skill 生命周期职责

## 13. 测试清单

## 13.1 单元测试

- [ ] skill 名称校验
- [ ] frontmatter 校验
- [ ] supporting file 路径白名单
- [ ] patch 匹配行为
- [ ] manifest 更新
- [ ] generated overlay 逻辑

## 13.2 集成测试

- [ ] builtin / curated / generated 三层优先级
- [ ] `skills_list`
- [ ] `skill_view`
- [ ] `skill_manage(create)`
- [ ] `skill_manage(patch)`
- [ ] review 异步创建 skill
- [ ] review 异步 patch skill

## 13.3 安全测试

- [ ] path traversal 拒绝
- [ ] zip-slip 拒绝
- [ ] 超大文件拒绝
- [ ] 危险脚本拦截
- [ ] 禁止自动直接修改 builtin skill

## 13.4 回归测试

- [ ] 现有 `read_file` 仍可工作
- [ ] 现有 `Dream` 不受影响
- [ ] 现有 `SessionManager` 不受影响
- [ ] 现有 `OpenViking` 不受影响

## 14. 最终建议

如果只看“最值得借鉴、且最适合非侵入式落地”的部分，推荐固定成这一条路线：

1. Skill 工具化
2. generated SkillStore
3. 后台 SkillReview
4. session_search
5. 后续再考虑 SkillDream 和统一编排

对 `ep-gateway` 来说，真正高回报、低侵入、可快速见效的，不是直接追 Hermes 的 RL 平台，而是把 Hermes 的运行时学习闭环拆成一组新模块，再通过 `context.py`、`loop.py`、`schema.py`、`skills_section.md` 做最小接线。

这条路线最符合你当前要求：

- 新增文件优先
- 老代码薄接线
- 不大量魔改现有核心
- 可分阶段灰度上线
- 失败时容易回退
