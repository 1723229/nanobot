# Skill工具对比：之前 vs 现在

## 📋 问题1: 这些新工具有什么用？

### 三个核心工具

#### 1️⃣ SkillsListTool (`skills_list`)

**功能**: 列出所有可用的skills及其元数据

**调用示例**:

```python
await skills_list()
# 或带过滤
await skills_list(category="dingtalk")
```

**返回内容**:

```json
{
  "success": true,
  "skills": [
    {
      "name": "dingtalk-skills",
      "description": "钉钉API集成指南",
      "source": "builtin",
      "mutable": false,
      "path": "/path/to/dingtalk-skills/SKILL.md",
      "supporting_files": {
        "references": ["api.md", "examples.md"],
        "templates": ["config.yaml"]
      }
    },
    {
      "name": "python-api-json-fetch",
      "description": "从API获取JSON数据并解析",
      "source": "workspace",
      "mutable": true,
      "path": "/path/to/python-api-json-fetch/SKILL.md",
      "supporting_files": null
    }
  ],
  "count": 2,
  "hint": "Use skill_view(name) to see full content..."
}
```

**用途**:

- ✅ 发现可用的skills
- ✅ 按前缀过滤（如只看dingtalk相关）
- ✅ 了解skill是builtin还是workspace（是否可编辑）
- ✅ 查看是否有支持文件（references/templates等）

---

#### 2️⃣ SkillViewTool (`skill_view`)

**功能**: 查看skill的完整内容或其支持文件

**调用示例**:

```python
# 查看主skill内容
await skill_view(name="dingtalk-skills")

# 查看支持文件
await skill_view(name="dingtalk-skills", file_path="references/api.md")
```

**返回内容（主skill）**:

```json
{
  "success": true,
  "name": "dingtalk-skills",
  "description": "钉钉API集成指南",
  "source": "builtin",
  "mutable": false,
  "skill_dir": "/path/to/skills/dingtalk-skills",
  "skill_file": "/path/to/skills/dingtalk-skills/SKILL.md",
  "content": "---\nname: dingtalk-skills\ndescription: ...\n---\n\n# 使用指南\n...",
  "linked_files": {
    "references": ["api.md", "examples.md"]
  },
  "usage_hint": "To view linked files, call skill_view(name, file_path)..."
}
```

**用途**:

- ✅ 读取skill的完整内容
- ✅ 访问references/templates/scripts/assets等支持文件
- ✅ 自动记录usage（usage_count和last_used）
- ✅ 获取完整的文件路径信息

---

#### 3️⃣ SkillManageTool (`skill_manage`)

**功能**: 创建、更新、删除skills（Agent的程序性记忆）

**支持的操作**:

**a. 创建skill**:

```python
await skill_manage(
    action="create",
    name="my-new-skill",
    content="""---
name: my-new-skill
description: 我的新skill
---

# 使用场景
当需要...时使用

# 步骤
1. ...
2. ...
"""
)
```

**b. 修补skill (推荐)**:

```python
await skill_manage(
    action="patch",
    name="existing-skill",
    old_string="旧的错误内容",
    new_string="新的正确内容"
)
```

**c. 完全重写skill**:

```python
await skill_manage(
    action="edit",
    name="existing-skill",
    content="完整的新内容..."
)
```

**d. 删除skill**:

```python
await skill_manage(
    action="delete",
    name="obsolete-skill"
)
```

**e. 写入支持文件**:

```python
await skill_manage(
    action="write_file",
    name="my-skill",
    file_path="references/api-doc.md",
    file_content="# API Documentation\n..."
)
```

**f. 删除支持文件**:

```python
await skill_manage(
    action="remove_file",
    name="my-skill",
    file_path="references/old-doc.md"
)
```

**用途**:

- ✅ Agent自己创建skills（通过trial-and-error学习）
- ✅ Agent修复过时或错误的skills
- ✅ Agent管理skill的支持文件
- ✅ 受权限控制（`allow_create`、`allow_patch`、`allow_delete`）
- ✅ 受安全扫描保护（SkillGuard）

---

## 🔄 问题2: 之前是怎么操作skill的？

### 之前的方式（无专用工具）

#### System Prompt中的Skills部分

**旧模板** (`skills_section.md` 在 220cd74b):

```markdown
# Skills

The following skills extend your capabilities. To use a skill, 
read its SKILL.md file using the read_file tool.

Unavailable skills need dependencies installed first — 
you can try installing them with apt/brew.

{{ skills_summary }}
```

#### Agent如何使用Skills（旧方式）

**流程**:

```
1. Agent在system prompt中看到skills列表（仅名称+描述）
   
2. Agent想要使用某个skill时，使用 read_file 工具：
   await read_file(path="~/.hiperone/workspace/skills/dingtalk-skills/SKILL.md")
   
3. 读取到skill内容后，按照内容执行

4. 如果需要其他文件：
   await read_file(path="~/.hiperone/workspace/skills/dingtalk-skills/references/api.md")
```

#### 旧方式的问题


| 问题             | 说明                          |
| -------------- | --------------------------- |
| ❌ **路径暴露**     | Agent需要知道完整文件路径             |
| ❌ **无元数据**     | 不知道skill是builtin还是workspace |
| ❌ **无usage跟踪** | 不知道哪些skills被频繁使用            |
| ❌ **无安全隔离**    | `read_file`可以读取任何文件         |
| ❌ **无结构化信息**   | 只能读纯文本，需要自己解析frontmatter    |
| ❌ **无法发现支持文件** | 不知道有哪些references/templates  |
| ❌ **无法创建/修改**  | Agent无法自己生成或更新skills        |


---

### 现在的方式（专用工具）

#### System Prompt中的Skills部分

**新模板** (`skills_section.md` 当前):

```markdown
# Skills

The following skills extend your capabilities. Always check available 
skills before answering — a skill may already solve the user's request. 
Use `skill_view(name)` to load a skill when it clearly matches, and use 
`skills_list()` to discover skills by category prefix.

After completing a complex task (5+ tool calls), fixing a tricky error 
through trial and error, or discovering a non-trivial workflow, save the 
approach as a skill via `skill_manage(action="create")` so you can reuse 
it next time. When using a skill and finding it outdated or wrong, patch 
it immediately with `skill_manage(action="patch")`.

Unavailable skills need dependencies installed first — 
you can try installing them with apt/brew.

{{ skills_summary }}
```

#### Agent如何使用Skills（新方式）

**流程**:

```
1. Agent在system prompt中看到skills列表（名称+描述）
   
2. Agent想要浏览skills：
   result = await skills_list()  # 列出所有
   result = await skills_list(category="dingtalk")  # 只看dingtalk相关
   
3. Agent想要使用某个skill：
   result = await skill_view(name="dingtalk-skills")
   # 自动返回完整内容+元数据
   
4. Agent想要查看支持文件：
   result = await skill_view(name="dingtalk-skills", file_path="references/api.md")
   
5. Agent完成复杂任务后，自动保存为skill：
   result = await skill_manage(action="create", name="new-skill", content="...")
   
6. Agent发现skill过时，自动修复：
   result = await skill_manage(action="patch", name="old-skill", 
                               old_string="旧内容", new_string="新内容")
```

#### 新方式的优势


| 优势            | 说明                                              |
| ------------- | ----------------------------------------------- |
| ✅ **路径抽象**    | Agent只需知道skill名称，不需要知道文件路径                      |
| ✅ **元数据丰富**   | 返回source、mutable、supporting_files等信息            |
| ✅ **Usage跟踪** | 自动记录usage_count和last_used                       |
| ✅ **安全隔离**    | 只能访问skills目录，受SkillGuard保护                      |
| ✅ **结构化返回**   | JSON格式，包含所有必要信息                                 |
| ✅ **支持文件发现**  | 自动列出references/templates/scripts/assets         |
| ✅ **自我进化**    | Agent可以自己创建、修改、删除skills                         |
| ✅ **权限控制**    | 通过`allow_create`/`allow_patch`/`allow_delete`控制 |


---

## 📊 完整对比表


| 维度           | 之前（无专用工具）                              | 现在（有专用工具）                             |
| ------------ | -------------------------------------- | ------------------------------------- |
| **Skills发现** | 只在system prompt中看到名称+描述                | `skills_list()` 动态列出，可过滤              |
| **Skills读取** | `read_file("~/.../SKILL.md")`          | `skill_view(name)` 抽象路径               |
| **支持文件**     | `read_file("~/.../references/api.md")` | `skill_view(name, file_path)`         |
| **元数据**      | ❌ 无                                    | ✅ source, mutable, supporting_files等  |
| **Usage跟踪**  | ❌ 无                                    | ✅ 自动记录usage_count                     |
| **Skills创建** | ❌ 无法创建                                 | ✅ `skill_manage(action="create")`     |
| **Skills修改** | ❌ 无法修改                                 | ✅ `skill_manage(action="patch/edit")` |
| **Skills删除** | ❌ 无法删除                                 | ✅ `skill_manage(action="delete")`     |
| **安全性**      | ⚠️ `read_file`可读任何文件                   | ✅ 限制在skills目录，SkillGuard扫描            |
| **权限控制**     | ❌ 无                                    | ✅ allow_create/patch/delete配置         |
| **自动进化**     | ❌ 不支持                                  | ✅ SkillReviewService自动生成              |
| **Audit日志**  | ❌ 无                                    | ✅ `.skill-events.jsonl`记录所有操作         |


---

## 🎯 你的日志示例分析

```
2026-04-17 13:22:04.470 | INFO | nanobot.agent.loop:before_execute_tools:109 
- Tool call: skill_view({"name": "dingtalk-skills"})
```

**这表示**:

- ✅ Agent正在使用新的`skill_view`工具
- ✅ Agent想要查看`dingtalk-skills`的内容
- ✅ 这是**标准用法**，符合新的skill访问模式

**返回内容**会包括:

```json
{
  "success": true,
  "name": "dingtalk-skills",
  "description": "钉钉开放平台API集成指南",
  "source": "builtin",
  "mutable": false,
  "skill_dir": "/path/to/nanobot/skills/dingtalk-skills",
  "skill_file": "/path/to/nanobot/skills/dingtalk-skills/SKILL.md",
  "content": "完整的SKILL.md内容...",
  "linked_files": {
    "references": [
      "error-codes.md",
      "field-rules.md",
      "global-reference.md",
      ...
    ]
  },
  "usage_hint": "To view linked files, call skill_view(name, file_path)..."
}
```

**与旧方式对比**:


| 旧方式                                           | 新方式                                    |
| --------------------------------------------- | -------------------------------------- |
| `read_file("~/.../dingtalk-skills/SKILL.md")` | `skill_view(name="dingtalk-skills")` ✅ |
| 只返回纯文本内容                                      | 返回结构化JSON+元数据 ✅                        |
| 不知道有supporting files                          | 自动列出linked_files ✅                     |
| 无usage跟踪                                      | 自动记录使用次数 ✅                             |


---

## 💡 总结

### 为什么要引入这些工具？

1. **抽象化**: Agent不需要知道文件系统路径
2. **结构化**: 返回JSON而非纯文本，包含元数据
3. **安全性**: 限制访问范围，防止路径遍历
4. **可追踪**: 记录usage，了解哪些skills有用
5. **自我进化**: Agent可以自己创建和改进skills
6. **权限控制**: 细粒度的操作权限管理
7. **审计**: 所有操作记录到`.skill-events.jsonl`

### 这是Skill Evolution的核心

这三个工具是整个Skill Evolution系统的基础：

- **SkillsListTool**: 发现
- **SkillViewTool**: 使用
- **SkillManageTool**: 进化

配合`SkillReviewService`（自动review对话并生成skills），构成了完整的skill自我进化循环：

```
用户对话 → 复杂任务完成 → SkillReviewService分析 
       → skill_manage创建新skill → 保存到workspace/skills/
       → 下次遇到类似任务 → skills_list发现 → skill_view使用
       → 发现过时 → skill_manage修复 → 持续进化
```

---

**你看到的日志**正是这个系统在工作的证据！Agent正在主动使用`skill_view`来访问dingtalk-skills的内容，这比之前用`read_file`更安全、更结构化、更智能。