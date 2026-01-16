import os
import re
from collections import defaultdict
from typing import List, Pattern, Dict, Any

import utils.constants as constants
from utils.tools import get_real_path, resource_path
from utils.types import WhitelistMaps


def load_whitelist_maps(path: str = constants.whitelist_path) -> WhitelistMaps:
    """
    Load whitelist maps from the given path.
    Returns two dictionaries:
      - exact: channel_name -> list of exact whitelist entries
      - keywords: channel_name -> list of keyword whitelist entries
    The special key "" (empty string) is used for global entries.
    """

    exact = defaultdict(list)
    keywords = defaultdict(list)
    in_keyword_section = False

    real_path = get_real_path(resource_path(path))
    if not os.path.exists(real_path):
        return exact, keywords

    with open(real_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            s = line.strip()
            if not s or s.startswith("#"):
                continue

            if re.match(r"^\[.*\]$", s):
                in_keyword_section = s.upper() == "[KEYWORDS]"
                continue

            if "," in s:
                name, value = map(str.strip, s.split(",", 1))
                key = name or ""
            else:
                key = ""
                value = s

            if not value:
                continue

            if in_keyword_section:
                if value not in keywords[key]:
                    keywords[key].append(value)
            else:
                if value not in exact[key]:
                    exact[key].append(value)

    return exact, keywords


def is_url_whitelisted(data_map: WhitelistMaps, url: str, channel_name: str | None = None) -> bool:
    """
    Check if the given URL is whitelisted for the specified channel.
    If channel_name is None, only global whitelist entries are considered.
    1. Exact match (channel-specific)
    2. Exact match (global)
    3. Keyword match (channel-specific)
    4. Keyword match (global)
    5. If none match, return False
    """
    if not url or not data_map:
        return False

    exact_map, keyword_map = data_map
    channel_key = channel_name or ""

    def check_exact_for(key):
        for candidate in exact_map.get(key, []):
            if not candidate:
                continue
            c = candidate.strip()
            if c == url:
                return True
        return False

    if check_exact_for(channel_key) or check_exact_for(""):
        return True

    for kw in keyword_map.get(channel_key, []) + keyword_map.get("", []):
        if not kw:
            continue
        if kw in url:
            return True

    return False


def get_whitelist_url(data_map: WhitelistMaps, channel_name: str | None = None) -> List[str]:
    """
    Get the list of whitelisted URLs for the specified channel.
    If channel_name is None, only global whitelist entries are considered.
    """
    exact_map, _ = data_map
    channel_key = channel_name or ""
    whitelist_urls = set()

    for candidate in exact_map.get(channel_key, []) + exact_map.get("", []):
        c = candidate.strip()
        if c:
            whitelist_urls.add(c)

    return list(whitelist_urls)


def get_whitelist_total_count(data_map: WhitelistMaps) -> int:
    """
    Get the total count of unique whitelist entries across all channels.
    """
    exact_map, keyword_map = data_map
    unique_entries = set()

    for entries in exact_map.values():
        for entry in entries:
            unique_entries.add(entry.strip())

    for entries in keyword_map.values():
        for entry in entries:
            unique_entries.add(entry.strip())

    return len(unique_entries)


def get_section_entries(path: str = constants.whitelist_path, section: str = "WHITELIST",
                        pattern: Pattern[str] = None) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Get URLs from a specific section in the whitelist file.
    Returns a tuple: (inside_section_list, outside_section_list).
    Each item in the list is either a string URL or a dictionary with 'url' and 'headers' keys.
    """
    real_path = get_real_path(resource_path(path))
    if not os.path.exists(real_path):
        return [], []

    inside: List[Dict[str, Any]] = []
    outside: List[Dict[str, Any]] = []
    in_section = False
    header_re = re.compile(r"^\[.*\]$")

    with open(real_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            s = line.strip()
            if not s:
                continue

            if header_re.match(s):
                in_section = s.upper() == f"[{section.upper()}]"
                continue

            if s.startswith("#"):
                continue

            # 解析行内容，支持 "url,header1:value1,header2:value2" 格式
            parts = s.split(",")
            if not parts:
                continue
                
            # 第一个部分是 URL
            url = parts[0].strip()
            if not url:
                continue
                
            # 如果有更多部分，解析为请求头
            headers = None
            if len(parts) > 1:
                headers = {}
                for part in parts[1:]:
                    part = part.strip()
                    if not part:
                        continue
                        
                    # 解析 "header:value" 格式
                    header_parts = part.split(":", 1)
                    if len(header_parts) == 2:
                        header_name = header_parts[0].strip()
                        header_value = header_parts[1].strip()
                        if header_name:
                            headers[header_name] = header_value
            
            # 创建结果项
            item = {"url": url}
            if headers:
                item["headers"] = headers
            
            # 根据模式匹配决定是否添加
            target = inside if in_section else outside
            if pattern:
                match = pattern.search(url)
                if match:
                    target.append(item)
            else:
                target.append(item)

    return inside, outside