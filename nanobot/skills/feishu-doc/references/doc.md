# 云文档 (Doc)

飞书云文档 API，列出、读取、搜索云文档内容。

## API 函数

### list_files

获取云文档文件列表。

```python
from feishu_api import list_files

files = list_files(parent_node="", page_size=20)
# files -> [{name, token, type, url, ...}]
# type: "docx" / "sheet" / "bitable" / "folder" / "mindnote"
```

**CLI**:
```bash
python3 scripts/feishu_api.py doc list --limit 20
python3 scripts/feishu_api.py doc list --parent-node fldcnXXX
```

### read_doc

读取云文档内容，返回 Markdown 格式纯文本。

```python
from feishu_api import read_doc

content = read_doc("doxcnXXX")  # document_id
print(content)  # Markdown 文本
```

**CLI**:
```bash
python3 scripts/feishu_api.py doc read --document-id doxcnXXX
```

### search_docs

搜索云文档。

```python
from feishu_api import search_docs

items = search_docs("季度报告", page_size=10)
# items -> [{docs_token, docs_type, url, ...}]
```

**CLI**:
```bash
python3 scripts/feishu_api.py doc search --keyword "季度报告" --limit 10
```

## 文档类型

| token 前缀 | 类型 |
|------------|------|
| `doxcn` | 旧版文档 (doc) |
| `docx` | 新版文档 (docx) |
| `shtcn` | 电子表格 (sheet) |
| `bascn` | 多维表格 (bitable) |

## 从 URL 提取 Token

```
https://xxx.feishu.cn/docx/{doc_token}     → 新版文档
https://xxx.feishu.cn/wiki/{node_token}     → 知识库页面（需先 wiki_get_node 获取 obj_token）
```

## Block 类型参考

| block_type | 名称 | 可编辑 |
|------------|------|--------|
| 1 | Page（文档根节点） | 否 |
| 2 | Text（纯文本段落） | 是 |
| 3-11 | Heading1-9（标题） | 是 |
| 12 | Bullet（无序列表项） | 是 |
| 13 | Ordered（有序列表项） | 是 |
| 14 | Code（代码块） | 是 |
| 15 | Quote（引用块） | 是 |
| 17 | Todo（任务/复选框） | 是 |
| 22 | Divider（分割线） | 否 |
| 27 | Image（图片） | 部分 |
| 31 | Table（表格） | 部分（只读，无法通过 API 创建） |

## 常见错误

| 错误 | 正确做法 |
|------|----------|
| 用 wiki URL 中的 token 直接调用 doc API | 必须先 `wiki_get_node()` 获取 `obj_token`，再用 `obj_token` 调用 |
| 并发写入同一文档 | 飞书文档不支持并发写入，需串行操作 |
| Markdown 中包含表格 | 表格无法通过 Markdown 转 Block 创建 |
| 应用无法访问已有文档 | 需将应用添加为文档协作者 |

## 所需权限

- `drive:drive:readonly` — 查看云空间文件
- `docx:document:readonly` — 查看文档内容
- `docx:document` — 读写文档
- `docs:doc:search` — 搜索文档
