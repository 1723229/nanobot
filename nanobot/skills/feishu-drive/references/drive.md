# 云空间 / 文件管理 (Drive)

飞书云空间 API，管理文件夹、上传下载文件和文档权限。

## API 函数

### drive_create_folder

创建文件夹。

```python
from feishu_api import drive_create_folder

data = drive_create_folder("新文件夹", folder_token="fldcnXXX")
# data -> {token, url}
```

**CLI**:
```bash
python3 scripts/feishu_api.py drive mkdir --name "新文件夹" --folder-token fldcnXXX
```

### drive_upload_file

上传文件到云空间（< 20MB 文件使用 upload_all）。

```python
from feishu_api import drive_upload_file

data = drive_upload_file("/path/to/file.pdf", parent_node="fldcnXXX")
# data -> {file_token}
```

**CLI**:
```bash
python3 scripts/feishu_api.py drive upload --file /path/to/file.pdf --parent-node fldcnXXX
```

### drive_download_file

下载文件。

```python
from feishu_api import drive_download_file

path = drive_download_file("boxcnXXX", "/tmp/output.pdf")
```

**CLI**:
```bash
python3 scripts/feishu_api.py drive download --file-token boxcnXXX --save-path /tmp/output.pdf
```

### drive_move_file

移动文件。

```python
from feishu_api import drive_move_file

drive_move_file("boxcnXXX", dst_folder_token="fldcnYYY")
```

### drive_copy_file

复制文件。

```python
from feishu_api import drive_copy_file

data = drive_copy_file("boxcnXXX", dst_folder_token="fldcnYYY", name="副本")
```

### drive_delete_file

删除文件。

```python
from feishu_api import drive_delete_file

drive_delete_file("boxcnXXX")
```

### drive_add_permission

添加文档权限。

```python
from feishu_api import drive_add_permission

drive_add_permission(
    token="doxcnXXX",
    member_type="user",          # user / chat / department
    member_id="ou_xxx",
    perm="view",                 # view / edit / full_access
    token_type="docx",           # doc / sheet / bitable / folder / docx
)
```

## 文件类型参考

| 类型 | 说明 |
|------|------|
| `doc` | 旧版文档 |
| `docx` | 新版文档 |
| `sheet` | 电子表格 |
| `bitable` | 多维表格 |
| `folder` | 文件夹 |
| `file` | 上传的文件 |
| `mindnote` | 思维导图 |

## 权限级别参考

| 权限值 | 说明 |
|--------|------|
| `view` | 仅查看 |
| `edit` | 可编辑 |
| `full_access` | 完全访问（可管理权限） |

## 常见错误

| 错误 | 正确做法 |
|------|----------|
| 机器人不指定 folder_token 创建文件夹 | 机器人没有「我的空间」，必须指定已共享给机器人的 folder_token |
| move/delete 时 type 参数搞错 | type 必须与文件实际类型一致 |
| 文件不在机器人可访问范围内 | 需先将文件/文件夹共享给机器人应用 |
| 权限 token_type 与文件实际类型不匹配 | `token_type` 必须与目标文件类型一致（docx/sheet/bitable 等） |

## 所需权限

- `drive:drive` — 云空间完整权限
- `drive:drive:readonly` — 只读权限
- `drive:file:upload` — 上传文件
- `drive:file:download` — 下载文件
- `drive:permission` — 管理文档权限
