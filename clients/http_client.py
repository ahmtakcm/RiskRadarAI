import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import settings


class HttpClient:
    def __init__(self):
        self.session = requests.Session()
        retries = Retry(
            total=settings.http_retry_total,
            connect=settings.http_retry_total,
            read=settings.http_retry_total,
            backoff_factor=settings.http_backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET", "POST"]),
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9,tr-TR;q=0.8,tr;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Connection": "keep-alive",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }

    def _build_headers(self, url: str, extra_headers: dict | None = None, feed_mode: bool = False) -> dict:
        headers = dict(self.default_headers)

        low = (url or "").lower()
        if "centcom.mil" in low:
            headers["Referer"] = "https://www.centcom.mil/"
            headers["Origin"] = "https://www.centcom.mil"
            headers["Accept-Language"] = "en-US,en;q=0.9"
            headers["Sec-Fetch-Site"] = "same-origin"

        if feed_mode:
            headers["Accept"] = "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8"
            headers["Sec-Fetch-Mode"] = "cors"
            headers["Sec-Fetch-Dest"] = "empty"
            headers["Sec-Fetch-User"] = "?0"

        if extra_headers:
            headers.update(extra_headers)

        return headers

    def get_response(self, url: str, extra_headers: dict | None = None, feed_mode: bool = False):
        headers = self._build_headers(url, extra_headers=extra_headers, feed_mode=feed_mode)
        response = self.session.get(
            url,
            headers=headers,
            timeout=settings.request_timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response

    def get_text(self, url: str, extra_headers: dict | None = None, feed_mode: bool = False) -> str:
        response = self.get_response(url, extra_headers=extra_headers, feed_mode=feed_mode)
        return response.text

    def post_form(self, url: str, data: dict, extra_headers: dict | None = None):
        response = self.session.post(
            url,
            data=data,
            headers=self._build_headers(url, extra_headers=extra_headers),
            timeout=settings.request_timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response


http_client = HttpClient()
