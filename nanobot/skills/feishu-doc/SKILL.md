---
name: feishu-doc
description: 飞书云文档 — 文件列表、读取文档内容、搜索文档
metadata:
  requires:
    - type: binary
      name: python3
---

# 飞书云文档 (Doc)

飞书云文档 API，列出、读取、搜索云文档内容。

## 使用流程

1. 根据下方 API 函数说明确认所需操作
2. 通过 `exec` 工具调用脚本执行

## API 函数

### list_files

获取云文档文件列表。

```
python3 scripts/feishu_doc.py list --limit 20
python3 scripts/feishu_doc.py list --parent-node fldcnXXX
```

返回: [{name, token, type, url, ...}]，type: "docx" / "sheet" / "bitable" / "folder" / "mindnote"

### read_doc

读取云文档内容，返回 Markdown 格式纯文本。

```
python3 scripts/feishu_doc.py read --document-id doxcnXXX
```

### search_docs

搜索云文档。

```
python3 scripts/feishu_doc.py search --keyword "季度报告" --limit 10
```

返回: [{docs_token, docs_type, url, ...}]

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

## 常见错误

| 错误 | 正确做法 |
|------|----------|
| 用 wiki URL 中的 token 直接调用 doc API | 必须先 `wiki_get_node()` 获取 `obj_token`，再用 `obj_token` 调用 |
| 并发写入同一文档 | 飞书文档不支持并发写入，需串行操作 |
| 应用无法访问已有文档 | 需将应用添加为文档协作者 |

## 所需权限

- `drive:drive:readonly` — 查看云空间文件
- `docx:document:readonly` — 查看文档内容
- `docx:document` — 读写文档
- `docs:doc:search` — 搜索文档

## 凭据

自动读取 `~/.hiperone/config.json` 或环境变量 `NANOBOT_CHANNELS__FEISHU__APP_ID` / `NANOBOT_CHANNELS__FEISHU__APP_SECRET`，无需手动配置。
