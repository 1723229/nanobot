---
name: feishu-drive
description: 飞书云空间/文件管理 — 文件夹创建、上传/下载、权限管理
metadata:
  requires:
    - type: binary
      name: python3
---

# 飞书云空间/文件管理 (Drive)

飞书云空间 API，管理文件夹、上传下载文件和文档权限。

## 使用流程

1. 根据下方 API 函数说明确认所需操作
2. 通过 `exec` 工具调用脚本执行

## API 函数

### drive_create_folder

创建文件夹。

```
python3 scripts/feishu_drive.py mkdir --name "新文件夹" --folder-token fldcnXXX
```

### drive_upload_file

上传文件到云空间（< 20MB）。

```
python3 scripts/feishu_drive.py upload --file /path/to/file.pdf --parent-node fldcnXXX
```

### drive_download_file

下载文件。

```
python3 scripts/feishu_drive.py download --file-token boxcnXXX --save-path /tmp/output.pdf
```

### 其他函数（通过脚本 Python API 调用）

- `drive_move_file(file_token, dst_folder_token)` — 移动文件
- `drive_copy_file(file_token, dst_folder_token, name)` — 复制文件
- `drive_delete_file(file_token)` — 删除文件
- `drive_add_permission(token, member_type, member_id, perm, token_type)` — 添加文档权限

## 文件类型参考

| 类型 | 说明 |
|------|------|
| `doc` | 旧版文档 |
| `docx` | 新版文档 |
| `sheet` | 电子表格 |
| `bitable` | 多维表格 |
| `folder` | 文件夹 |
| `file` | 上传的文件 |

## 权限级别参考

| 权限值 | 说明 |
|--------|------|
| `view` | 仅查看 |
| `edit` | 可编辑 |
| `full_access` | 完全访问（可管理权限） |

## 常见错误

| 错误 | 正确做法 |
|------|----------|
| 机器人不指定 folder_token 创建文件夹 | 机器人没有「我的空间」，必须指定已共享的 folder_token |
| 文件不在机器人可访问范围内 | 需先将文件/文件夹共享给机器人应用 |
| 权限 token_type 与文件类型不匹配 | `token_type` 必须与目标文件类型一致 |

## 所需权限

- `drive:drive` — 云空间完整权限
- `drive:drive:readonly` — 只读权限
- `drive:file:upload` — 上传文件
- `drive:file:download` — 下载文件
- `drive:permission` — 管理文档权限

## 凭据

自动读取 `~/.hiperone/config.json` 或环境变量 `NANOBOT_CHANNELS__FEISHU__APP_ID` / `NANOBOT_CHANNELS__FEISHU__APP_SECRET`，无需手动配置。
