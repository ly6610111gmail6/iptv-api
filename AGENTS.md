# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.
## 项目概述

IPTV-API 是一个 IPTV 直播源自动更新平台，自动采集、筛选、测速并生成 M3U/TXT 格式的直播源文件，支持定时更新、RTMP 推流、GUI 界面和 Docker 部署。

- **语言**: Python 3.13
- **包管理**: pipenv (`Pipfile`)
- **许可证**: AGPL-3.0

## 常用命令

```bash
# 安装依赖
pipenv install --dev

# CLI 更新模式（采集 → 测速 → 生成结果，单次运行或定时循环）
pipenv run dev

# 启动 Flask Web 服务（提供结果访问接口，含 RTMP 推流）
pipenv run service

# GUI 桌面应用
pipenv run ui

# Docker 构建（多架构: amd64/arm64/arm v7）
pipenv run docker_build

# GUI 打包
pipenv run tkinter_build
```

## 核心架构

### 主流程（main.py → UpdateSource 类）

`main.py` 的 `UpdateSource` 类是整个系统的编排器，执行 5 个阶段：

1. **准备阶段** (`_prepare_channel_data`): 加载白名单/黑名单，从模板文件（`config/demo.txt`）解析频道结构，合并本地源、HLS 源和历史缓存
2. **订阅源获取** (`visit_page`): 并发拉取订阅源列表和 EPG 数据
3. **聚合器启动** (`_start_aggregator`): 启动 `ResultAggregator`（`utils/aggregator.py`），负责实时排序和增量写入结果文件
4. **测速阶段** (`_run_speed_test`): 使用 `asyncio.Semaphore` 控制并发数（`speed_test_limit`），对每个接口测速（延迟/速率/分辨率/帧率），结果通过 `on_task_complete` 回调实时推送给聚合器
5. **完成**: 保存缓存、写入最终结果

### 核心模块关系

```
main.py (UpdateSource - 编排器)
├── utils/config.py       → ConfigManager: INI 配置 + 环境变量覆盖
├── utils/channel.py      → 频道数据处理、测速编排、结果写入
│   ├── utils/speed.py    → HTTP 测速 (aiohttp)、m3u8 解析、FFmpeg 探测
│   ├── utils/alias.py    → 频道别名匹配
│   └── utils/ffmpeg/     → FFmpeg 调用（分辨率/编码信息）
├── utils/aggregator.py   → ResultAggregator: 实时排序 + 增量写盘
├── updates/subscribe/    → 订阅源抓取（requests + BeautifulSoup）
├── updates/epg/          → EPG 节目单抓取
└── utils/i18n.py         → 国际化 (zh_CN / en, locales/*.json)

service/app.py            → Flask Web 服务（独立进程）
service/rtmp.py           → RTMP/HLS 推流管理
tkinter_ui/               → GUI 桌面应用（独立进程）
```

### 数据流

```
模板文件(demo.txt) + 本地源(local.txt) + HLS视频 + 历史缓存
    → 频道分类结构: CategoryChannelData = dict[category, dict[name, list[ChannelData]]]
    → 订阅源/EPG 抓取补充
    → 并发测速 (speed.py)
    → ResultAggregator 实时排序写入输出文件
    → output/{result.txt, ipv4/, ipv6/, hls*, m3u}
```

### 配置系统

- `config/config.ini` — 默认配置（180+ 行，含中英文注释）
- `config/user_config.ini` — 用户覆盖配置（可选，优先级高于默认）
- 环境变量覆盖 — 所有 `[section]_key` 格式的环境变量均可用
- 核心配置：`open_update`, `open_subscribe`, `open_speed_test`, `speed_test_limit`, `urls_limit`, `open_rtmp` 等

### 类型定义

关键类型位于 `utils/types.py`:
- `ChannelData` — 单个频道接口（url, host, origin, ipv_type, resolution, speed, delay...）
- `CategoryChannelData` — `dict[category, dict[name, list[ChannelData]]]`
- `OriginType` — `Literal["hls", "local", "whitelist", "subscribe"]`
- `TestResult` — 测速结果（speed, delay, resolution, video_codec...）
- `WhitelistMaps` — 白名单数据结构

### 路径常量

所有路径定义在 `utils/constants.py`，输出结构：
- `output/result.txt` — 主结果文件
- `output/ipv4/result.txt`, `output/ipv6/result.txt` — 按协议分类
- `output/hls.txt` — RTMP 推流结果
- `output/data/cache.gz` — 历史缓存（pickle + gzip）
- `output/data/frozen.gz` — 冻结/封禁 URL 记录
- `output/log/` — 各类日志

## 注意事项

- 项目没有自动化测试，修改前确保理解调用链
- `utils/config.py` 的 `ConfigManager` 通过 `__getattr__` 委托到 `configparser.ConfigParser`，所有配置项以 `@property` 形式暴露（50+ 个属性）
- 测速缓存（`speed.py` 的 `cache` 全局变量）按 Host 或 URL 聚合测速结果，调用 `clear_cache()` 重置
- Docker 镜像内置 Nginx + RTMP 模块编译，入口脚本根据 `open_rtmp` 配置决定是否启动推流
- GitHub Actions 环境下 `open_rtmp` 强制为 False（见 `config.py:243`）