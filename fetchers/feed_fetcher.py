from fetchers import rss_fetcher, html_fetcher, social_fetcher
from datetime import datetime, timezone
import requests
from email.utils import parsedate_to_datetime
from parsers.rss_parser import parse_rss_items
from parsers.whitehouse_parser import parse_whitehouse_html
from parsers.iran_mfa_parser import parse_iran_mfa_html
from parsers.link_listing_parser import parse_link_listing
from parsers.presidency_app_parser import parse_truth_social_archive
from parsers.centcom_parser import parse_centcom_listing
from parsers.tr_mfa_parser import parse_listing as parse_tr_mfa_listing
from parsers.iran_mfa_new_parser import parse_listing as parse_iran_mfa_new_listing

FEED_META_KEYS = (
    "official_class",
    "official_country",
    "official_red_alert",
    "source_class",
    "source_country",
    "source_family",
    "stale_minutes",
    "region_tags",
    "verification_group",
    "access_risk",
    "notes",
)

def _pub_date_sort_key(pub_date: str) -> float:
    raw = str(pub_date or '').strip()
    if not raw:
        return 0.0

    # RFC822 / RSS
    try:
        dt = parsedate_to_datetime(raw)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
    except Exception:
        pass

    # ISO / atom benzeri formatlar
    try:
        iso = raw.replace('Z', '+00:00')
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        pass

    return 0.0


def fetch_feed_items(feed: dict):
    kind = (feed.get("kind") or feed.get("source_kind") or "rss").strip()
    url = feed["url"]

    if kind in ("news", "rss"):
        xml_text = rss_fetcher.fetch(url)
        items = parse_rss_items(xml_text)

    elif kind == "rss_social":
        xml_text = social_fetcher.fetch(feed)
        items = parse_rss_items(xml_text) if xml_text else []

    elif kind == "official_html":
        html = html_fetcher.fetch(url)
        if "whitehouse.gov" in url:
            items = parse_whitehouse_html(html, url)
        elif "en.mfa.gov.ir" in url:
            items = parse_iran_mfa_html(html, url)
        else:
            items = parse_link_listing(html, url)

    elif kind == "listing_html":
        parser_name = feed.get("parser")

        if parser_name == "tr_mfa_parser":
            html = html_fetcher.fetch(url)
            items = parse_tr_mfa_listing(html, feed.get("name", "TR MFA Açıklamalar"))

        elif parser_name == "iran_mfa_new_parser":
            html_parts = []
            try:
                response = requests.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                    timeout=25,
                    stream=True,
                )
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
                    if chunk:
                        html_parts.append(chunk)
                    if sum(len(x) for x in html_parts) > 600000:
                        break
                html = "".join(html_parts)
            except Exception:
                html = "".join(html_parts)

            items = parse_iran_mfa_new_listing(html, feed.get("name", "Iran MFA Official EN")) if html else []

        elif parser_name == "presidency_truth_social_archive":
            html = html_fetcher.fetch(url)
            items = parse_truth_social_archive(html, url)

        elif "centcom.mil" in url.lower() or "centcom" in str(feed.get("name", "")).lower():
            html, resolved_url = html_fetcher.fetch_centcom_listing(url)
            items = parse_centcom_listing(html, resolved_url)

        else:
            html = html_fetcher.fetch(url)
            items = parse_link_listing(html, url)

    else:
        items = []

    for item in items:
        item["source_name"] = feed["name"]
        item["source_kind"] = kind
        for key in FEED_META_KEYS:
            if key not in item and key in feed:
                item[key] = feed.get(key)

    items = sorted(
        items,
        key=lambda x: _pub_date_sort_key(x.get("pub_date", "")),
        reverse=True,
    )
    return items[:20]
