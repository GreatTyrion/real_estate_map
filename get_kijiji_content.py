import random
import time

import requests
from requests.exceptions import RequestException

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-CA,en-US;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

_session = requests.Session()
_session.headers.update(_DEFAULT_HEADERS)

REQUEST_TIMEOUT = 30


def _is_html_response(resp):
    ctype = (resp.headers.get("Content-Type") or "").lower()
    return ctype.find("html") > -1


def simple_get(url, retries=3):
    """
    GET `url` and return response body bytes if the response looks like HTML
    and status is OK. Returns None on failure after retries.
    """
    for attempt in range(retries):
        try:
            if attempt:
                time.sleep(random.uniform(1.5, 4.0))
            resp = _session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200 and _is_html_response(resp):
                return resp.content
            if resp.status_code == 429:
                time.sleep(random.uniform(8.0, 16.0))
                continue
            if resp.status_code in (403, 404):
                print(f"HTTP {resp.status_code} for {url}")
                return None
            print(f"HTTP {resp.status_code} for {url} (attempt {attempt + 1})")
        except RequestException as e:
            print(f"Request error for {url} (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                time.sleep(random.uniform(2.0, 5.0))
    return None
