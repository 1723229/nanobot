# 知识库 (Wiki)

飞书知识库 API，管理知识空间、节点和内容搜索。

## API 函数

### wiki_list_spaces

获取知识空间列表。

```python
from feishu_api import wiki_list_spaces

data = wiki_list_spaces(page_size=50)
# data["items"] -> [{space_id, name, description, visibility, ...}]
```

**CLI**:
```bash
python3 scripts/feishu_api.py wiki spaces
```

### wiki_get_space

获取知识空间详情。

```python
from feishu_api import wiki_get_space

data = wiki_get_space("space_id_xxx")
# data["space"] -> {space_id, name, description, ...}
```

### wiki_list_nodes

获取知识空间节点列表。

```python
from feishu_api import wiki_list_nodes

data = wiki_list_nodes(
    space_id="space_id_xxx",
    parent_node_token="",        # 空字符串获取根节点
    page_size=50,
)
# data["items"] -> [{node_token, obj_token, obj_type, title, has_child, ...}]
```

**CLI**:
```bash
python3 scripts/feishu_api.py wiki nodes --space-id xxx
python3 scripts/feishu_api.py wiki nodes --space-id xxx --parent-node wikcnXXX
```

### wiki_get_node

获取节点信息。

```python
from feishu_api import wiki_get_node

data = wiki_get_node("space_id_xxx", "node_token_xxx")
# data["node"] -> {node_token, obj_token, obj_type, title, ...}
```

### wiki_create_node

创建知识库节点（或将已有文档移入知识库）。

```python
from feishu_api import wiki_create_node

# 创建新节点
data = wiki_create_node("space_id", "docx", parent_node_token="wikcnXXX", title="新文档")

# 移入已有文档
data = wiki_create_node("space_id", "docx", obj_token="doxcnXXX")
```

### wiki_search

搜索知识库内容。

```python
from feishu_api import wiki_search

data = wiki_search("开发规范", space_id="space_id_xxx")
# data["items"] -> [{title, node_token, space_id, ...}]
```

**CLI**:
```bash
python3 scripts/feishu_api.py wiki search --keyword "开发规范"
python3 scripts/feishu_api.py wiki search --keyword "开发规范" --space-id xxx
```

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

```python
# 1. 获取节点详情 → 拿到 obj_token
node_data = wiki_get_node("space_id", "node_token")
obj_token = node_data["node"]["obj_token"]

# 2. 用 obj_token 作为 document_id 读取文档
content = read_doc(obj_token)
```

**不要用 `node_token` 或 URL 中的 token 直接调用 doc API，必须用 `wiki_get_node()` 返回的 `obj_token`。**

## 常见错误

| 错误 | 正确做法 |
|------|----------|
| 用 wiki URL 中的 token 直接调用 doc API | 必须先 `wiki_get_node()` 获取 `obj_token` |
| 列出空间返回空但实际有内容 | 机器人未被添加为空间成员 |
| 混淆 `node_token` 和 `obj_token` | `node_token` 是知识库节点标识，`obj_token` 是实际文档标识 |
| 创建节点时忘记指定 `obj_type` | 需要传 `"docx"` 等类型 |

## 知识库访问设置

机器人需要被添加为知识空间成员：知识空间 → 设置 → 成员管理 → 添加机器人。

## 所需权限

- `wiki:wiki:readonly` — 查看知识库
- `wiki:wiki` — 知识库完整权限
