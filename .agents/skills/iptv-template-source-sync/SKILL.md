---
name: iptv-template-source-sync
description: Use when merging IPTV M3U or TXT source channel names into an IPTV-API template file, especially when the user gives a source path and asks to add only missing channels without deleting existing template entries.
---

# IPTV 模板源同步

用于把订阅源文件中的频道名合并到 `config/user_demo.txt` 这类模板文件中。默认只追加模板里不存在的频道，不删除、不重排已有内容。

## 适用场景

- 用户给出 `sub/1.txt`、M3U、TXT 等源路径，要求检查模板中有没有新的频道。
- 用户要求“新增缺失频道”“不要删除”“同步到模板”。
- 源文件是 `#EXTINF ... group-title="分类",频道名` 加 URL 的 M3U 格式。

## 快速使用

先 dry-run 看新增清单：

```powershell
python .agents/skills/iptv-template-source-sync/scripts/sync_template_channels.py --source sub/1.txt --template config/user_demo.txt --dry-run
```

确认后写入模板：

```powershell
python .agents/skills/iptv-template-source-sync/scripts/sync_template_channels.py --source sub/1.txt --template config/user_demo.txt
```

## 参数

- `--source`: 源文件路径，必填，可指定任意 M3U/TXT 源。
- `--template`: 模板文件路径，默认 `config/user_demo.txt`。
- `--exclude-group`: 排除源分组，默认排除 `进QQ群`；可重复传入多个。
- `--new-group-mode`: 源分组在模板中不存在时的处理方式，默认 `append`。
  - `append`: 在文件末尾新增分组。
  - `skip`: 跳过未知分组。
  - `error`: 遇到未知分组直接报错。
- `--dry-run`: 只输出将新增的频道，不写文件。

## 工作规则

1. 频道名完全相同即视为已存在，避免重复新增。
2. 分类匹配会兼容模板里的 emoji 前缀，例如源分组 `央视频道` 可匹配 `☘️央视频道,#genre#`。
3. 新频道追加到对应分类末尾，保持模板已有顺序。
4. 操作前后用 `git diff -- config/user_demo.txt` 复核，确认没有删除或重排。
