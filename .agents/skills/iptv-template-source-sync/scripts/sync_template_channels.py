"""将 IPTV 订阅源中的新增频道追加到模板文件。

@author ly
@date 2026/06/10 20:00
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from collections import OrderedDict
from pathlib import Path


GENRE_SUFFIX = ",#genre#"
DEFAULT_EXCLUDE_GROUPS = ("进QQ群",)
URL_PATTERN = re.compile(r"^(https?|rtmp|rtsp)://", re.IGNORECASE)
GROUP_PATTERN = re.compile(r'group-title="([^"]*)"')
DEFAULT_DOWNLOAD_PATH = Path("sub/online_source.txt")


def configure_text_output() -> None:
    """配置控制台输出编码，避免 Windows GBK 环境打印 emoji 失败。

    @author ly
    @date 2026/06/13 22:22
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            # 技能会输出模板分类名，分类名前缀可能包含 emoji，需要 UTF-8 才能稳定打印。
            stream.reconfigure(encoding="utf-8")


def normalize_group_name(name: str) -> str:
    """归一化分组名，便于匹配带 emoji 前缀的模板分类。

    Args:
        name: 原始分组名。

    Returns:
        去除常见装饰符后的分组名。

    @author ly
    @date 2026/06/10 20:00
    """
    return re.sub(r"^[^\w\u4e00-\u9fff]+", "", name).strip()


def read_text(path: Path) -> str:
    """读取 UTF-8 文本，兼容带 BOM 的源文件。

    Args:
        path: 文件路径。

    Returns:
        文件内容。

    @author ly
    @date 2026/06/10 20:00
    """
    return path.read_text(encoding="utf-8-sig")


def parse_headers(raw_headers: list[str]) -> dict[str, str]:
    """解析命令行传入的 HTTP 请求头。

    Args:
        raw_headers: 形如 ``名称: 值`` 的请求头列表。

    Returns:
        请求头字典。

    @author ly
    @date 2026/06/13 22:11
    """
    headers: dict[str, str] = {}
    for raw_header in raw_headers:
        if ":" not in raw_header:
            raise ValueError(f"请求头格式错误，应为 '名称: 值': {raw_header}")
        name, value = raw_header.split(":", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            raise ValueError(f"请求头名称不能为空: {raw_header}")
        headers[name] = value
    return headers


def download_source(source_url: str, download_to: Path, headers: dict[str, str], timeout: int) -> Path:
    """下载在线源到本地文件。

    Args:
        source_url: 在线源地址。
        download_to: 下载保存路径。
        headers: HTTP 请求头。
        timeout: 下载超时时间，单位秒。

    Returns:
        下载后的本地文件路径。

    @author ly
    @date 2026/06/13 22:11
    """
    download_to.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(source_url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        # 直接保存原始字节，避免下载阶段错误改动源文件编码。
        download_to.write_bytes(response.read())
    print(f"已下载在线源: {source_url}")
    print(f"保存到本地: {download_to}")
    return download_to


def parse_template(text: str) -> tuple[list[str], OrderedDict[str, list[str]], set[str]]:
    """解析模板文件中的分类和频道名。

    Args:
        text: 模板文件内容。

    Returns:
        原始行、分类频道映射、全量频道名集合。

    @author ly
    @date 2026/06/10 20:00
    """
    lines = text.splitlines()
    categories: OrderedDict[str, list[str]] = OrderedDict()
    all_names: set[str] = set()
    current_group: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith(GENRE_SUFFIX):
            current_group = line[: -len(GENRE_SUFFIX)]
            categories.setdefault(current_group, [])
            continue
        if current_group is None:
            continue
        categories[current_group].append(line)
        all_names.add(line)

    return lines, categories, all_names


def parse_m3u_source(text: str) -> OrderedDict[str, list[str]]:
    """解析 M3U 源文件，按 group-title 收集唯一频道名。

    Args:
        text: M3U 源文件内容。

    Returns:
        源分组到频道名列表的映射。

    @author ly
    @date 2026/06/10 20:00
    """
    groups: OrderedDict[str, list[str]] = OrderedDict()
    last_extinf: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("#EXTINF:"):
            last_extinf = line
            continue
        if not last_extinf or not URL_PATTERN.match(line):
            continue

        group_match = GROUP_PATTERN.search(last_extinf)
        comma_index = last_extinf.rfind(",")
        group_name = group_match.group(1).strip() if group_match else ""
        channel_name = last_extinf[comma_index + 1 :].strip() if comma_index >= 0 else ""

        if group_name and channel_name:
            groups.setdefault(group_name, [])
            # 同一个源里同名频道可能有多条 URL，只需要在模板里出现一次。
            if channel_name not in groups[group_name]:
                groups[group_name].append(channel_name)

        last_extinf = None

    return groups


def find_template_group(source_group: str, template_groups: list[str]) -> str | None:
    """为源分组寻找对应的模板分组。

    Args:
        source_group: 源文件中的分组名。
        template_groups: 模板已有分组列表。

    Returns:
        匹配到的模板分组名，未匹配则返回 None。

    @author ly
    @date 2026/06/10 20:00
    """
    normalized_source = normalize_group_name(source_group)
    for template_group in template_groups:
        normalized_template = normalize_group_name(template_group)
        if normalized_source == normalized_template:
            return template_group
    for template_group in template_groups:
        normalized_template = normalize_group_name(template_group)
        # 兼容模板分类带 emoji 或额外前缀的情况。
        if normalized_source in normalized_template or normalized_template in normalized_source:
            return template_group
    return None


def collect_new_channels(
    source_groups: OrderedDict[str, list[str]],
    template_groups: OrderedDict[str, list[str]],
    existing_names: set[str],
    exclude_groups: set[str],
    new_group_mode: str,
) -> OrderedDict[str, list[str]]:
    """计算需要追加到模板的新增频道。

    Args:
        source_groups: 源文件分组频道。
        template_groups: 模板已有分组频道。
        existing_names: 模板已有频道名集合。
        exclude_groups: 需要忽略的源分组。
        new_group_mode: 未知分组处理模式。

    Returns:
        模板分组到新增频道名列表的映射。

    @author ly
    @date 2026/06/10 20:00
    """
    additions: OrderedDict[str, list[str]] = OrderedDict()
    template_group_names = list(template_groups.keys())
    seen = set(existing_names)

    for source_group, channel_names in source_groups.items():
        if source_group in exclude_groups:
            continue

        template_group = find_template_group(source_group, template_group_names)
        if template_group is None:
            if new_group_mode == "skip":
                continue
            if new_group_mode == "error":
                raise ValueError(f"模板中不存在源分组: {source_group}")
            template_group = source_group
            template_group_names.append(template_group)

        for channel_name in channel_names:
            if channel_name in seen:
                continue
            additions.setdefault(template_group, [])
            additions[template_group].append(channel_name)
            seen.add(channel_name)

    return additions


def apply_additions(template_text: str, additions: OrderedDict[str, list[str]]) -> str:
    """把新增频道追加到对应模板分组末尾。

    Args:
        template_text: 原模板内容。
        additions: 待追加频道。

    Returns:
        更新后的模板内容。

    @author ly
    @date 2026/06/10 20:00
    """
    lines = template_text.splitlines()
    existing_headers = {line.strip()[: -len(GENRE_SUFFIX)] for line in lines if line.strip().endswith(GENRE_SUFFIX)}
    result: list[str] = []
    current_group: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if line.endswith(GENRE_SUFFIX):
            if current_group in additions:
                result.extend(additions[current_group])
            current_group = line[: -len(GENRE_SUFFIX)]
        result.append(raw_line)

    if current_group in additions:
        result.extend(additions[current_group])

    for group_name, channel_names in additions.items():
        if group_name in existing_headers:
            continue
        if result and result[-1].strip():
            result.append("")
        result.append(f"{group_name}{GENRE_SUFFIX}")
        result.extend(channel_names)

    return "\n".join(result) + "\n"


def print_summary(additions: OrderedDict[str, list[str]], dry_run: bool) -> None:
    """输出本次同步摘要。

    Args:
        additions: 待追加频道。
        dry_run: 是否仅预览。

    @author ly
    @date 2026/06/10 20:00
    """
    total = sum(len(names) for names in additions.values())
    action = "将新增" if dry_run else "已新增"
    print(f"{action}频道数: {total}")
    for group_name, channel_names in additions.items():
        print(f"[{group_name}] {len(channel_names)}")
        for channel_name in channel_names:
            print(f"  {channel_name}")


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    Returns:
        参数解析器。

    @author ly
    @date 2026/06/13 22:11
    """
    parser = argparse.ArgumentParser(description="将 IPTV 源文件中的新增频道追加到模板")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source", help="本地源文件路径，例如 sub/1.txt")
    source_group.add_argument("--source-url", help="在线源地址，脚本会先下载到本地再合并")
    parser.add_argument("--header", action="append", default=[], help="在线源请求头，格式为 '名称: 值'，可重复传入")
    parser.add_argument("--download-to", default=str(DEFAULT_DOWNLOAD_PATH), help="在线源下载保存路径")
    parser.add_argument("--timeout", type=int, default=30, help="在线源下载超时时间，单位秒")
    parser.add_argument("--template", default="config/user_demo.txt", help="模板文件路径")
    parser.add_argument("--exclude-group", action="append", default=list(DEFAULT_EXCLUDE_GROUPS), help="排除的源分组，可重复传入")
    parser.add_argument("--new-group-mode", choices=("append", "skip", "error"), default="append", help="未知分组处理方式")
    parser.add_argument("--dry-run", action="store_true", help="只预览新增内容，不写入模板")
    return parser


def main() -> int:
    """执行模板同步。

    Returns:
        进程退出码。

    @author ly
    @date 2026/06/13 22:11
    """
    configure_text_output()
    args = build_parser().parse_args()
    template_path = Path(args.template)
    source_path = Path(args.source) if args.source else None

    if args.source_url:
        try:
            source_path = download_source(
                source_url=args.source_url,
                download_to=Path(args.download_to),
                headers=parse_headers(args.header),
                timeout=args.timeout,
            )
        except (OSError, ValueError, urllib.error.URLError) as exc:
            print(f"下载在线源失败: {exc}", file=sys.stderr)
            return 2

    if source_path is None or not source_path.exists():
        print(f"源文件不存在: {source_path}", file=sys.stderr)
        return 2
    if not template_path.exists():
        print(f"模板文件不存在: {template_path}", file=sys.stderr)
        return 2

    template_text = read_text(template_path)
    source_text = read_text(source_path)
    _, template_groups, existing_names = parse_template(template_text)
    source_groups = parse_m3u_source(source_text)
    additions = collect_new_channels(
        source_groups=source_groups,
        template_groups=template_groups,
        existing_names=existing_names,
        exclude_groups=set(args.exclude_group),
        new_group_mode=args.new_group_mode,
    )

    print_summary(additions, args.dry_run)
    if args.dry_run or not additions:
        return 0

    template_path.write_text(apply_additions(template_text, additions), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
