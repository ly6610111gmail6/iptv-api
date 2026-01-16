import re

import requests
from bs4 import BeautifulSoup

headers = {
    "Accept": "*/*",
    "Connection": "keep-alive",
    "Accept-Language": "zh-CN,zh;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
}


def get_requests(url, data=None, proxy=None, timeout=30, custom_headers=None):
    """
    Get the response by requests
    """
    proxies = {"http": proxy} if proxy is not None else None
    response = None
    try:
        with requests.Session() as session:
            # 使用默认请求头和自定义请求头的合并
            request_headers = headers.copy()
            if custom_headers:
                request_headers.update(custom_headers)
                
            if data:
                response = session.post(
                    url, headers=request_headers, data=data, proxies=proxies, timeout=timeout
                )
            else:
                response = session.get(url, headers=request_headers, proxies=proxies, timeout=timeout)
    except requests.RequestException as e:
        raise e

    if response is None:
        raise requests.RequestException(f"No response from {url}")

    text = re.sub(r"<!--.*?-->", "", response.text or "", flags=re.DOTALL)
    if not text.strip():
        raise requests.RequestException(f"Empty response from {url}")

    return response


def get_soup_requests(url, data=None, proxy=None, timeout=30, custom_headers=None):
    """
    Get the soup by requests
    """
    response = get_requests(url, data, proxy, timeout, custom_headers)
    source = re.sub(r"<!--.*?-->", "", response.text or "", flags=re.DOTALL)
    soup = BeautifulSoup(source, "html.parser")
    return soup