# 面向 ep-gateway 的 Hermes Skill 自进化架构设计

## 1. 背景

本文档用于说明，如何把 Hermes 中最有价值的“自学习、自进化、Skill 创建与 Skill 修补”机制，迁移并适配到 `ep-gateway`。

目标不是机械照搬 Hermes 的实现细节，而是抽取其真正有效的机制，并结合 `ep-gateway` 现有架构落地一套可运行、可扩展、可审计的 Skill 进化体系。

本文档基于以下两个仓库的对照分析：

- Hermes：`D:\github\hermes-agent`
- ep-gateway：`D:\github\ep-gateway`

## 2. 结论摘要

Hermes 的“自学习”本质上不是模型训练，也不是强化学习。它的核心是一个运行时的程序性记忆闭环，主要由三部分组成：

1. Prompt 指导
   告诉模型什么时候应该把经验沉淀成 Skill，什么时候应该修补已有 Skill。
2. 可写的 Skill 管理工具
   通过专用工具创建、修改、补丁和维护 Skill 目录及配套文件。
3. 后台复盘 Review
   在主任务完成后，后台回放本轮对话，判断是否值得新建或修补 Skill。

`ep-gateway` 已经具备很好的基础设施，因此并不需要重写主架构：

- 有上下文构建层：`nanobot/agent/context.py`
- 有 Hook 生命周期：`nanobot/agent/hook.py`
- 有后台任务调度：`nanobot/agent/loop.py`
- 有 Dream 两阶段记忆处理：`nanobot/agent/memory.py`

因此，最合理的方向不是重做 Agent，而是：

- 保留现有主循环
- 增加一等公民的 Skill 工具面
- 增加受控可写的 SkillStore
- 增加在线后台 SkillReview
- 后续增加离线批处理 SkillDream

## 3. 文档范围

本文档覆盖以下内容：

- Skill 的发现、加载、创建、修补
- Skill 的目录设计和存储模型
- 在线后台 Review 机制
- 离线历史挖掘机制
- 安全边界和审计设计
- 配置设计
- 分阶段开发计划
- 测试策略

本文档不覆盖以下内容：

- Hermes Hub/Registry 的完整复刻
- 跨机器共享 Skill 云同步
- 模型微调或训练
- 强化学习或权重更新

## 4. Hermes 与 ep-gateway 现状对比

### 4.1 Hermes 当前能力

Hermes 已经形成了较完整的 Skill 生命周期体系：

- Prompt 中持续提醒模型：
  - 复杂任务后应沉淀 Skill
  - Skill 过时后应及时 patch
- 存在显式 `skill_manage` 工具：
  - `create`
  - `edit`
  - `patch`
  - `delete`
  - `write_file`
  - `remove_file`
- 存在后台 review agent：
  - 在任务完成后异步复盘
  - 根据本轮经验决定是否新建或修补 Skill
- Skills 使用渐进式加载：
  - 先看 metadata
  - 需要时再加载完整 `SKILL.md`
  - 需要时再加载 supporting files
- 存在 skill 安全扫描
- 存在 bundled skill 同步与 manifest

Hermes 中关键参考实现文件：

- `agent/prompt_builder.py`
- `run_agent.py`
- `tools/skill_manager_tool.py`
- `tools/skills_tool.py`
- `tools/skills_guard.py`
- `tools/skills_sync.py`

### 4.2 ep-gateway 当前能力

`ep-gateway` 目前已经有较轻量的 Skill 系统：

- `nanobot/agent/skills.py`
  - 技能扫描
  - frontmatter 解析
  - summary 构建
- `nanobot/agent/context.py`
  - 把 Skill summary 注入系统提示词
- `nanobot/templates/agent/skills_section.md`
  - 告诉模型需要时通过 `read_file` 去读 `SKILL.md`
- Web 侧支持 Skill 上传与下载
- 内置一个 `skill-creator` Skill，用于人工指导模型设计 Skill

ep-gateway 当前的关键文件：

- `nanobot/agent/skills.py`
- `nanobot/agent/context.py`
- `nanobot/templates/agent/skills_section.md`
- `nanobot/agent/loop.py`
- `nanobot/agent/hook.py`
- `nanobot/agent/memory.py`
- `nanobot/web/server.py`

### 4.3 核心差异

真正的差异，不在 Skill 文件格式，而在 Skill 生命周期。

Hermes 把 Skill 当成“可写的程序性记忆”。

ep-gateway 目前主要把 Skill 当成“模型可以按需读取的静态文件”。

换句话说：

- ep-gateway 已经有 Skill 文件系统
- 但还没有 Skill 自进化系统

## 5. 设计目标

### 5.1 功能目标

- 允许 Agent 创建新的可复用 Skill
- 允许 Agent 在真实执行后修补失效 Skill
- 支持 Skill 的 supporting files：
  - `references/`
  - `templates/`
  - `scripts/`
  - `assets/`
- 支持渐进式加载，避免上下文膨胀
- 区分人工维护 Skill 与 Agent 自动生成 Skill
- 支持任务完成后的异步后台 Review
- 后续支持基于历史记录的离线 Skill 挖掘

### 5.2 安全目标

- 自动写入永远不能越出 workspace
- V1 不允许自动修改 repo 内置 builtin skills
- 必须校验 frontmatter、目录结构、文件路径
- 必须防止 path traversal 和 zip-slip
- 应支持 Skill 静态扫描
- 必须保留 Skill 变更审计日志

### 5.3 产品目标

- 让 Agent 在重复任务中显著减少重复探索
- 让成功经验可以被稳定复用
- 保持人工 Skill 的权威性
- 支持灰度开关与分阶段上线

## 6. 非目标

- 不允许 Agent 用“Skill 进化”的名义任意改 repo
- V1 不允许自动直接修改 builtin Skill
- 不把现有 Dream 逻辑强行塞进 Skill 逻辑
- 不追求一次性复刻 Hermes 的全部能力

## 7. 设计原则

### 7.1 Skill 是程序性记忆

Skill 应承载的是：

- 如何完成一类任务
- 应该用哪些工具
- 哪些命令或步骤最有效
- 哪些坑容易踩
- 如何验证执行结果

Skill 不应该承载：

- 原始任务日志
- 冗长的对话摘要
- 瞬时状态
- 应该写进 `MEMORY.md` 的长期偏好

### 7.2 是运行时进化，不是模型训练

系统能力提升来自：

- 执行中发现有效流程
- 将流程沉淀为 Skill
- 在后续执行中读取并复用
- 在遇到偏差时补丁 Skill

不是来自：

- 修改模型权重
- 用对话训练模型

### 7.3 受控写入面

Skill 的自动演化不能依赖通用文件写入工具。

必须通过专门的 `skill_manage` 工具来完成，因为只有这样才能统一收敛：

- 路径校验
- frontmatter 校验
- 权限边界
- 支持文件白名单
- 审计与事件记录

### 7.4 区分人工所有权与自动所有权

人工维护 Skill 和自动生成 Skill 不应该共享同一套写策略。

V1 建议：

- builtin skills：只读
- workspace curated skills：只读
- generated skills：允许自动 create/edit/patch/delete

## 8. 目标架构总览

建议新增或改造五个核心组件：

1. `SkillCatalog`
2. `SkillStore`
3. `SkillToolset`
4. `SkillReviewService`
5. `SkillDream`（后续阶段）

### 8.1 总体流程

1. Agent 收到用户请求
2. 系统提示词中注入 Skill summary 与 Skill 使用规则
3. Agent 使用 `skills_list` / `skill_view` 按需读取 Skill
4. Agent 正常完成任务
5. 用户主回复完成后，后台异步启动 SkillReview
6. Review 判断是否应：
   - 新建 Skill
   - 修补 Skill
   - 忽略
7. 通过 `skill_manage` 执行受控落盘
8. 写入 Skill 事件日志
9. 后续周期性运行 `SkillDream`，从历史记录里挖掘遗漏的可复用流程

## 9. Skill 存储模型

### 9.1 目录分层

建议采用三层 Skill 存储模型：

```text
nanobot/skills/                  # repo 内置技能，builtin，只读
<workspace>/skills/              # 工作区人工维护技能，curated，只读
<workspace>/.agent-state/skills/     # Agent 自动生成与演化技能，generated，可写
```

建议优先级：

1. workspace curated
2. generated
3. builtin

设计原因：

- curated 技能应优先于自动生成技能
- generated 技能不应直接覆盖 repo 内置内容
- builtin 技能提供稳定兜底

### 9.2 generated Skill 目录结构

```text
<workspace>/.agent-state/skills/
  manifest.json
  skill-events.jsonl
  my-skill/
    SKILL.md
    references/
    templates/
    scripts/
    assets/
```

V1 说明：
- 当前 `SkillsLoader` 只支持 `<workspace>/.agent-state/skills/<skill-name>/SKILL.md` 这一层级。
- 暂不引入 `category-name/my-skill/` 这样的二级目录，避免改动现有扫描逻辑。
- 如后续确实需要分类，建议优先通过 `manifest.json` 增加 `category` 字段，而不是先改目录结构。

### 9.3 Manifest

建议文件：

- `<workspace>/.agent-state/skills/manifest.json`

建议字段：

- `name`
- `root_dir`
- `source`
- `origin_skill`
- `created_by`
- `created_at`
- `updated_at`
- `origin_hash`
- `current_hash`
- `status`
- `last_used_at`
- `last_reviewed_at`
- `review_count`

### 9.4 Skill 事件日志

建议文件：

- `<workspace>/.agent-state/skills/skill-events.jsonl`

建议字段：

- `timestamp`
- `session_key`
- `action`
- `skill_name`
- `source`
- `reason`
- `tool_calls`
- `result`

## 10. 核心组件设计

### 10.1 SkillCatalog

建议文件：

- `nanobot/agent/skills.py`

职责：

- 扫描所有 Skill 来源
- 解析 metadata
- 处理优先级覆盖
- 提供 Skill 列表、Skill 详情和 Skill supporting files 访问
- 判断某个 Skill 是否可变更

建议接口：

```python
class SkillCatalog:
    def list_skills(self, include_unavailable: bool = True) -> list[SkillEntry]: ...
    def get_skill(self, name: str) -> SkillEntry | None: ...
    def load_skill_body(self, name: str) -> str | None: ...
    def load_skill_file(self, name: str, relative_path: str) -> str | bytes | None: ...
    def get_always_skills(self) -> list[str]: ...
    def is_mutable(self, name: str) -> bool: ...
    def resolve_mutation_target(self, name: str) -> MutationTarget: ...
```

V1 需要补一个硬约束：

- `get_always_skills()` 默认只允许返回 `builtin` 和 `workspace curated`
- `generated` skill 默认不得进入 always-skills
- 如未来确实需要 generated 常驻，只能走人工提升或显式白名单，不允许 reviewer 自动写入 `always: true`

建议 `SkillEntry` 字段：

- `name`
- `description`
- `path`
- `source`
- `available`
- `mutable`
- `platforms`
- `requirements`
- `metadata`
- `supporting_files`

### 10.2 SkillStore

建议文件：

- `nanobot/agent/skill_store.py`

职责：

- 所有 Skill 持久化写入的统一入口
- 执行路径校验、frontmatter 校验、文件大小限制、原子写入和 manifest 更新

建议职责范围：

- `create_skill`
- `edit_skill`
- `patch_skill`
- `delete_skill`
- `write_file`
- `remove_file`

V1 写策略：

- `create`：允许，写入 generated dir
- `edit`：仅允许 generated skill
- `patch`：仅允许 generated skill
- `delete`：仅允许 generated skill
- builtin / curated：不允许直接自动修改

建议对 builtin / curated Skill 的处理策略：

- 当 Reviewer 判断需要修补这类 Skill 时，不直接改原 Skill
- 先复制成 generated overlay，再对 overlay 进行 patch

建议接口：

```python
class SkillStore:
    def create_skill(self, name: str, content: str, category: str | None = None) -> SkillResult: ...
    def edit_skill(self, name: str, content: str) -> SkillResult: ...
    def patch_skill(self, name: str, old_text: str, new_text: str, file_path: str | None = None, replace_all: bool = False) -> SkillResult: ...
    def delete_skill(self, name: str) -> SkillResult: ...
    def write_file(self, name: str, file_path: str, file_content: str) -> SkillResult: ...
    def remove_file(self, name: str, file_path: str) -> SkillResult: ...
```

必须校验的内容：

- Skill name 合法
- category 合法
- `SKILL.md` frontmatter 合法
- 必须存在 `name` 和 `description`
- body 不能为空
- 内容大小不超限
- supporting file 路径只能在白名单目录下
- 不允许 `..`
- 不允许绝对 supporting file 路径

### 10.3 SkillToolset

建议文件：

- `nanobot/agent/tools/skills.py`

职责：

- 向模型暴露一等公民的 Skill 读写工具

建议新增三个工具：

- `skills_list`
- `skill_view`
- `skill_manage`

#### `skills_list`

作用：

- 返回 token 友好的 Skill metadata，而不是整份 Skill 内容

建议返回字段：

- `name`
- `description`
- `source`
- `available`
- `mutable`
- `path`
- `supporting_files`

#### `skill_view`

作用：

- 读取完整 `SKILL.md`
- 或读取某个 supporting file

建议参数：

- `name`
- `file_path` 可选

行为：

- `file_path` 为空时，读取 `SKILL.md`
- `file_path` 有值时，只允许读取：
  - `references/...`
  - `templates/...`
  - `scripts/...`
  - `assets/...`

#### `skill_manage`

作用：

- 执行所有受控 Skill 变更

建议动作：

- `create`
- `edit`
- `patch`
- `delete`
- `write_file`
- `remove_file`

它应成为 Skill 自进化唯一合法的自动写入入口。

### 10.4 SkillReviewService

建议文件：

- `nanobot/agent/skill_review.py`

职责：

- 在主回复结束后，后台复盘本轮执行
- 判断是否有值得沉淀为 Skill 的程序性经验
- 判断是否需要修补已有 Skill
- 调用 `skill_manage` 落盘

这部分是 Hermes 最值得迁移的能力。

建议输入：

- 用户输入
- assistant 消息
- 工具调用列表
- 工具结果摘要
- 已加载 Skill
- 实际使用 Skill
- session key

建议输出：

- review 结果对象
- 事件日志
- 可选的用户通知

### 10.5 SkillDream

建议文件：

- `nanobot/agent/skill_dream.py`

职责：

- 周期性扫描 `memory/history.jsonl`
- 从跨会话历史中挖掘重复出现的工作流
- 通过 `skill_manage` 创建 generated skill

这是 `ep-gateway` 相比 Hermes 更容易做强的一点，因为你已经有 `Dream`。

建议职责：

- 扫描未处理历史
- 识别重复流程
- 生成可复用步骤摘要
- 写入 generated skill

建议阶段：

- 不进入 V1
- 在线 review 稳定后再做

## 11. 与现有运行时的集成位置

### 11.1 ContextBuilder 集成

当前文件：

- `nanobot/agent/context.py`

当前状态：

- 注入 Memory
- 注入 always skills
- 注入 skill summary
- 提示模型“如果需要就用 `read_file` 去读 Skill”

建议改造：

- 保留 summary 注入
- 改成显式的 Skill tool 使用指引

建议加入的系统提示词规则：

- 回复前先查看可用 Skill
- 若某 Skill 明显匹配，应先用 `skill_view`
- 若已加载 Skill 存在错误、缺步骤或过期，应使用 `skill_manage` patch
- 复杂任务完成后，应考虑保存 Skill

这对应 Hermes 的 Prompt 思路，但应适配 `ep-gateway` 的现有 ContextBuilder 架构。

### 11.2 Tool 注册

当前文件：

- `nanobot/agent/loop.py`

建议改造：

- 在 `_register_default_tools()` 中注册：
  - `skills_list`
  - `skill_view`
  - `skill_manage`

注意：

- 保留通用 `read_file`
- Skill 相关流程优先走专用 Skill 工具

### 11.3 Hook 生命周期

当前文件：

- `nanobot/agent/hook.py`

当前优势：

- 生命周期 Hook 已经很清晰
- 可在不污染主执行器的前提下扩展行为

建议改造：

- 通过 Hook 或 loop-level post-run service 收集本轮 Skill 使用信息
- 不建议把 Review 逻辑直接塞进 Runner 内核

### 11.4 后台任务调度

当前文件：

- `nanobot/agent/loop.py`

当前优势：

- 已有 `_schedule_background(...)`

建议改造：

- 在主回复完成后，使用现有后台调度机制异步运行 `SkillReviewService.review_turn(...)`

这比直接照抄 Hermes 的线程方式更适合当前代码结构。

### 11.5 Memory / Dream 集成

当前文件：

- `nanobot/agent/memory.py`

当前优势：

- `Dream` 已经是一个稳定的两阶段后台处理器

建议：

- V1 不把 Skill 逻辑塞进现有 Dream
- Skill 先做独立在线 review
- 稳定后再增加独立 `SkillDream`

## 12. 在线 SkillReview 工作流

### 12.1 生命周期

建议流程：

1. 用户发起请求
2. Agent 正常执行主任务
3. 主回复先返回给用户
4. 后台调度 SkillReview
5. Reviewer 复盘本轮执行
6. Reviewer 做出以下之一：
   - 不做任何事
   - 新建 generated skill
   - patch generated skill
   - 复制原 Skill 为 overlay 后 patch
7. 写入 Skill 事件日志

### 12.2 触发策略

建议 V1 的触发条件：

- 配置开关开启
- 工具调用轮次或次数达到阈值
- 或满足以下任一：
  - 使用过 Skill
  - 存在失败后重试成功
  - 用户纠正了做法
  - 本轮明显发现了非平凡工作流

推荐默认配置：

- `review_enabled = false`
- `review_trigger_iterations = 8`
- `review_min_tool_calls = 5`

### 12.3 Review 判断规则

Reviewer 应重点判断：

1. 本轮是否产出了可复用的工作流
2. 是否存在明显试错和经验修正
3. 用户是否给出了值得程序化沉淀的方法偏好
4. 已加载 Skill 是否存在缺步骤、错误或过期
5. 这些内容是否能在未来显著减少重复探索

Reviewer 应跳过：

- 一次性简单任务
- 很小的机械改动
- 临时环境状态
- 更适合写入 `MEMORY.md` 的长期事实

### 12.4 Create / Patch 规则

适合新建 Skill 的情况：

- 当前没有现有 Skill 覆盖这类工作流
- 工作流具有复用价值
- 工作流步骤稳定、可执行、可验证

适合 patch Skill 的情况：

- 已存在 generated skill 被实际使用过
- 执行中发现 Skill 缺步骤
- 发现 OS/环境差异导致旧 Skill 失效
- 命令示例错误
- 缺失关键坑点说明

适合 clone 后 patch 的情况：

- 匹配的最佳 Skill 来自 builtin 或 curated
- 又不希望自动改原始 Skill

## 13. 离线 SkillDream 工作流

这部分建议放到二期或三期。

建议流程：

1. 周期性调度 `SkillDream`
2. 读取未处理 `history.jsonl`
3. Phase 1：分析重复流程与常见问题
4. Phase 2：通过 `skill_manage` 生成或补丁 Skill
5. 更新 manifest 和审计日志

好处：

- 补齐在线 review 漏掉的场景
- 能跨会话观察重复任务
- 能把经常重复处理的问题转成 Skill

风险：

- 精度低于在线即时 review
- 更需要保守的创建阈值

## 14. Prompt 设计原则

Prompt 只负责引导，不负责保证。

### 14.1 应包含的提示

系统提示词应明确告诉模型：

- Skill 是程序性记忆
- 回答前先检查可用 Skill
- Skill 明显匹配时先 `skill_view`
- 已使用的 Skill 若发现问题，应及时 patch
- 复杂或反复试错任务完成后，应考虑保存 Skill

### 14.2 重要约束

Prompt 本身不构成能力闭环。

真正提供系统保证的是：

- `skill_manage`
- Review 触发机制
- 存储与写入边界
- 数据校验
- 审计日志

没有这些，模型只是“被建议去做”，不是真正“具备了 Skill 自进化能力”。

## 15. 安全设计

### 15.1 存储边界

V1 必须将自动写入严格限制在：

- `<workspace>/.agent-state/skills/`

禁止自动写入：

- repo builtin skill 目录
- workspace 其他任意目录
- 用户 home 的其他路径

### 15.2 路径校验

所有 Skill 写入必须：

- 先做路径 resolve
- 校验最终路径仍在 generated skill 根目录下
- 拒绝 `..`
- 拒绝绝对 supporting file 路径
- 仅允许以下 supporting file 子目录：
  - `references`
  - `templates`
  - `scripts`
  - `assets`

### 15.3 Skill 静态扫描

建议文件：

- `nanobot/agent/skill_guard.py`

建议扫描类型：

- secret exfiltration
- prompt injection
- 危险 shell 命令
- 破坏性文件系统操作
- 凭据读取与上送
- 隐藏指令

建议策略：

- builtin：默认信任
- curated upload：扫描后警告或阻断
- generated：扫描后允许或警告，严重情况阻断

### 15.4 Web 上传加固

当前 `nanobot/web/server.py` 中的 Skill 上传逻辑需要增强。

必须增加：

- zip-slip 检测
- resolve 后路径 containment 校验
- layout 合法性校验
- 大小限制

### 15.5 审计能力

每一次自动 Skill 变更都必须留痕。

这是后续进行以下工作的基础：

- 问题排查
- 人工回滚
- 策略优化
- 安全审计

## 16. 配置设计

建议在 `nanobot/config/schema.py` 中新增 `SkillsConfig`：

```python
class SkillsConfig(Base):
    enabled: bool = True
    generated_dir: str = ".agent-state/skills"
    review_enabled: bool = False
    review_mode: Literal["off", "suggest", "auto_patch", "auto_create"] = "auto_patch"
    review_trigger_iterations: int = 8
    review_min_tool_calls: int = 5
    review_max_iterations: int = 6
    review_model_override: str | None = None
    allow_create: bool = True
    allow_patch: bool = True
    allow_delete: bool = False
    guard_enabled: bool = True
    notify_user_on_change: bool = True
    dream_enabled: bool = False
    dream_interval_h: int = 24


class AgentDefaults(Base):
    ...
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
```

推荐默认值：

- Skill tools 开启
- 自动 review 默认关闭
- delete 默认关闭
- guard 默认开启

## 17. 数据模型建议

### 17.1 generated Skill frontmatter

V1 约束：
- `ep-gateway` 当前 frontmatter 解析器只稳定支持扁平 key-value。
- 不应在 generated `SKILL.md` frontmatter 中使用嵌套 YAML。
- richer metadata 应写入 `manifest.json`，或放在单行 `metadata: {...}` JSON 字段里。
- generated skill 不允许写入 `always: true`，避免自动进入 always-skills。

建议格式：

```yaml
---
name: feishu-approval-retry
description: 处理飞书审批接口重试与常见权限失败场景
version: 0.1.0
source: generated
created_by: agent
created_at: 2026-04-10T12:34:56+08:00
updated_at: 2026-04-10T12:34:56+08:00
origin_skill: feishu-approval
review_policy: auto_patch
metadata: {"nanobot":{"tags":["feishu","approval","retry"],"requires_tools":["exec","read_file"],"confidence":"medium","last_review_session":"cli:direct"}}
---
```

不建议在 V1 中使用的格式：

```yaml
---
name: bad-example
description: 这个例子在 V1 中不兼容
metadata:
  nanobot:
    tags: [a, b]
---
```

### 17.2 Review 结果对象

建议结构：

```json
{
  "success": true,
  "action": "patch",
  "skill_name": "feishu-approval-retry",
  "reason": "执行中发现 403 与权限不匹配场景缺少重试和鉴权说明",
  "source": "generated",
  "overlay_created": false
}
```

## 18. 详细开发计划

### 阶段一：把 Skill 升级为一等公民运行时对象

目标：

- 从“Skill 是文件”升级为“Skill 是显式能力对象”

涉及文件：

- 修改 `nanobot/agent/skills.py`
- 新增 `nanobot/agent/tools/skills.py`
- 修改 `nanobot/templates/agent/skills_section.md`
- 修改 `nanobot/agent/loop.py`

交付项：

- `skills_list`
- `skill_view`
- source-aware SkillCatalog
- 基于专用工具的渐进式加载
- 更新后的 Skill 系统提示词

验收标准：

- 模型不再依赖手写路径定位 Skill
- Skill 的 `source` 和 `mutable` 可见
- builtin / curated / generated 的优先级生效

### 阶段二：引入受控 Skill 写入能力

目标：

- 提供安全、受控、可审计的 Skill 变更入口

涉及文件：

- 新增 `nanobot/agent/skill_store.py`
- 修改 `nanobot/agent/tools/skills.py`
- 修改 `nanobot/agent/skills.py`

交付项：

- `skill_manage`
- `create/edit/patch/delete/write_file/remove_file`
- 原子写入
- frontmatter 校验
- generated-only 变更策略
- manifest 更新

验收标准：

- generated Skill 可以安全创建和 patch
- builtin / curated 不会被直接自动修改
- 非法路径和非法内容会被拒绝

### 阶段三：上线在线后台 SkillReview

目标：

- 建立 Hermes 风格的运行时 Skill 自进化闭环

涉及文件：

- 新增 `nanobot/agent/skill_review.py`
- 修改 `nanobot/agent/loop.py`
- 修改 `nanobot/config/schema.py`
- 新增 `nanobot/templates/agent/skill_review.md`

交付项：

- 可配置 Review 触发器
- 主回复之后的后台复盘
- 自动 create / patch Skill
- 事件日志记录

验收标准：

- 复杂任务后可以异步创建或 patch generated Skill
- 用户主回复不会被 Review 阻塞
- Review 可通过配置关闭

### 阶段四：安全与 Web 加固

目标：

- 让 Skill 自进化能力具备可上线的安全边界

涉及文件：

- 新增 `nanobot/agent/skill_guard.py`
- 修改 `nanobot/web/server.py`
- 修改 `nanobot/agent/skill_store.py`

交付项：

- Skill 静态扫描
- Skill zip 上传路径校验
- 文件大小限制
- 更完整的日志

验收标准：

- zip-slip 被阻断
- 危险 generated Skill 被警告或阻断
- 所有自动写入都能追踪

### 阶段五：离线 SkillDream

目标：

- 从历史记录里挖掘在线 Review 漏掉的 Skill 机会

涉及文件：

- 新增 `nanobot/agent/skill_dream.py`
- 修改调度与配置接线
- 视情况增加两阶段 Prompt 模板

交付项：

- 周期性历史分析
- 从重复流程生成 Skill
- dream cursor / 状态追踪

验收标准：

- 即使在线 Review 未触发，历史中的重复工作流也能被识别并沉淀为 Skill

## 19. 测试计划

### 19.1 单元测试

必须覆盖：

- Skill name 校验
- category 校验
- frontmatter 解析与校验
- supporting file 路径校验
- patch 匹配规则
- generated overlay 解析逻辑
- manifest 更新逻辑
- mutability 策略

### 19.2 集成测试

必须覆盖：

- builtin / curated / generated 三类 Skill 扫描与优先级
- `skill_view` 读取 `SKILL.md` 和 supporting file
- `skill_manage(create)` 正常路径
- `skill_manage(patch)` 的唯一匹配、多重匹配、匹配失败
- clone-to-generated 再 patch
- 后台 Review 自动创建 Skill
- 后台 Review 自动 patch Skill

### 19.3 安全测试

必须覆盖：

- path traversal 拒绝
- zip-slip 拒绝
- 超大文件拒绝
- 危险脚本模式识别
- 禁止直接自动修改 builtin Skill

### 19.4 回归测试

必须覆盖：

- 现有 skill summary 提示流程仍可工作
- 通用 `read_file` 能力不受影响
- 现有 Memory 和 Dream 能力不被破坏

## 20. 迁移策略

### 20.1 推荐 rollout 顺序

1. 先加 Skill 专用工具
2. 再加 generated SkillStore
3. 再加手动可调用的 `skill_manage`
4. 然后加后台 SkillReview
5. 再补安全加固
6. 最后加离线 SkillDream

### 20.2 为什么这样排

这条路径能以最低风险构建最小可用闭环：

- Skill tools 先把 Skill 从静态文件变为显式运行时对象
- SkillStore 再提供安全写入面
- SkillReview 再补齐 Hermes 的关键能力
- SkillDream 等在线能力稳定后再做

## 21. 风险与缓解

### 21.1 风险：生成大量低质量 Skill

缓解策略：

- 保守的 Review 阈值
- generated-only 写入策略
- Skill 事件日志可审计
- 可先用 `suggest` 模式灰度

### 21.2 风险：Skill 漂移和冲突

缓解策略：

- curated Skill 保持权威
- 自动 patch 仅作用于 generated
- 对 builtin / curated 采用 overlay 策略
- 记录 `origin_skill`

### 21.3 风险：自动生成内容不安全

缓解策略：

- `skill_manage` 受控写入
- 路径约束
- 静态扫描
- 审计日志

### 21.4 风险：首版复杂度过高

缓解策略：

- 分阶段上线
- V1 不做 registry sync
- V1 不做 SkillDream
- 先把在线闭环做稳定

## 22. 为什么不应直接照抄 Hermes

Hermes 的机制很有价值，但结构不应直接照搬。

原因：

- `ep-gateway` 已有 `AgentHook`、`ContextBuilder`、后台任务调度
- `ep-gateway` 已有独立的 `Dream` 记忆管线
- `ep-gateway` 更偏 workspace 作用域，而不是 Hermes 的全局 home 目录模式
- repo 内置 Skill 不适合被自动写入直接污染

因此正确策略是：

- 迁移机制
- 不迁移其内部结构组织方式

## 23. V1 完成定义

V1 达标的条件：

- Agent 拥有 `skills_list`、`skill_view`、`skill_manage`
- generated Skill 存储在 `<workspace>/.agent-state/skills/`
- Skill 写入有完整校验和边界限制
- 在线后台 Review 能创建或 patch generated Skill
- builtin / curated Skill 不会被直接自动修改
- 所有自动变更可审计
- 全部能力可通过配置开关关闭

## 24. 最终建议

Hermes 最值得迁移的不是 Skill 文件集合，也不是它的全局 Skill 目录。真正值得迁移的是它的闭环机制：

1. 在真实执行中发现可复用流程
2. 通过受控工具把流程写成 Skill
3. 在后续执行中根据反馈及时 patch
4. 在未来任务中复用

对 `ep-gateway` 来说，最合适的落地顺序是：

- 先做一等公民 Skill 工具
- 再做 generated SkillStore
- 再做后台 SkillReview
- 最后再做离线 SkillDream

这条路径和当前代码架构最匹配，收益最高，扰动最小，也最容易分阶段上线。
