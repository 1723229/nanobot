---
name: feishu-wiki
description: 飞书知识库 — 知识空间列表、节点管理、搜索
metadata:
  requires:
    - type: binary
      name: python3
---

# 飞书知识库 (Wiki)

飞书知识库 API，管理知识空间、节点和内容搜索。

## 使用流程

1. 根据下方 API 函数说明确认所需操作
2. 通过 `exec` 工具调用脚本执行

## API 函数

### wiki_list_spaces

获取知识空间列表。

```
python3 scripts/feishu_wiki.py spaces
```

### wiki_list_nodes

获取知识空间节点列表。

```
python3 scripts/feishu_wiki.py nodes --space-id xxx
python3 scripts/feishu_wiki.py nodes --space-id xxx --parent-node wikcnXXX
```

返回: items -> [{node_token, obj_token, obj_type, title, has_child, ...}]

### wiki_search

搜索知识库内容。

```
python3 scripts/feishu_wiki.py search --keyword "开发规范"
python3 scripts/feishu_wiki.py search --keyword "开发规范" --space-id xxx
```

### 其他函数（通过脚本 Python API 调用）

- `wiki_get_space(space_id)` — 获取知识空间详情
- `wiki_get_node(space_id, node_token)` — 获取节点信息
- `wiki_create_node(space_id, obj_type, parent_node_token, title, obj_token)` — 创建节点或移入文档

## obj_type 对象类型

| 值 | 说明 |
|----|------|
| doc | 旧版文档 |
| docx | 新版文档 |
| sheet | 电子表格 |
| bitable | 多维表格 |
| mindnote | 思维导图 |
| file | 文件 |

## Wiki-Doc 工作流（关键）

知识库页面的内容读写必须通过 doc API：

1. `wiki_get_node(space_id, node_token)` → 获取 `obj_token`
2. 用 `obj_token` 作为 `document_id` 调用 feishu-doc 的 `read_doc`

**不要用 `node_token` 或 URL 中的 token 直接调用 doc API，必须用 `wiki_get_node()` 返回的 `obj_token`。**

## 常见错误

| 错误 | 正确做法 |
|------|----------|
| 用 wiki URL 中的 token 直接调用 doc API | 必须先 `wiki_get_node()` 获取 `obj_token` |
| 列出空间返回空但实际有内容 | 机器人未被添加为空间成员 |
| 混淆 `node_token` 和 `obj_token` | `node_token` 是知识库节点标识，`obj_token` 是实际文档标识 |

## 知识库访问设置

机器人需要被添加为知识空间成员：知识空间 → 设置 → 成员管理 → 添加机器人。

## 所需权限

- `wiki:wiki:readonly` — 查看知识库
- `wiki:wiki` — 知识库完整权限

## 凭据

自动读取 `~/.hiperone/config.json` 或环境变量 `NANOBOT_CHANNELS__FEISHU__APP_ID` / `NANOBOT_CHANNELS__FEISHU__APP_SECRET`，无需手动配置。
