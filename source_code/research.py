import re
from urllib.parse import urlparse, urljoin
from datetime import datetime

import requests
import trafilatura
from bs4 import BeautifulSoup

from models import Source, Evidence


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140 Safari/537.36"
)


def normalize_urls(text: str):
    urls = []
    for raw in re.split(r"[\n,]+", text):
        url = raw.strip()
        if not url:
            continue
        if not re.match(r"^https?://", url, re.I):
            url = "https://" + url
        urls.append(url)
    return list(dict.fromkeys(urls))


def is_youtube(url: str):
    host = urlparse(url).netloc.lower()
    return "youtube.com" in host or "youtu.be" in host


def extract_vtt_text(vtt_text: str):
    lines = []
    for line in vtt_text.splitlines():
        line = line.strip()
        if not line or line.upper() == "WEBVTT":
            continue
        if "-->" in line:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        clean = re.sub(r"<[^>]+>", "", line)
        clean = re.sub(r"&(?:amp|lt|gt|quot);", " ", clean)
        if clean:
            lines.append(clean)
    # de-duplicate consecutive caption lines
    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)
    return " ".join(deduped)


def choose_caption_url(info):
    preferred = ["en", "en-US", "en-GB", "English"]
    subtitle_sets = [
        info.get("subtitles") or {},
        info.get("automatic_captions") or {},
    ]
    for collection in subtitle_sets:
        for lang in preferred:
            entries = collection.get(lang) or []
            for entry in entries:
                if entry.get("url") and entry.get("ext") in {"vtt", "srv3", "srv2", "json3"}:
                    return entry["url"], lang, entry.get("ext")
            for entry in entries:
                if entry.get("url"):
                    return entry["url"], lang, entry.get("ext", "")
        # Fallback to any language.
        for lang, entries in collection.items():
            for entry in entries:
                if entry.get("url"):
                    return entry["url"], lang, entry.get("ext", "")
    return None, None, None


def extract_youtube(url: str) -> Source:
    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:
        return Source(
            url=url,
            domain=urlparse(url).netloc,
            source_type="youtube",
            error=f"yt-dlp unavailable: {exc}",
        )

    source = Source(
        url=url,
        domain=urlparse(url).netloc,
        source_type="youtube",
    )

    try:
        opts = {
            "quiet": True,
            "skip_download": True,
            "noplaylist": True,
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        source.url = info.get("webpage_url") or url
        source.title = info.get("title") or "YouTube video"
        source.author = info.get("uploader") or info.get("channel")
        source.published_date = info.get("upload_date")
        description = info.get("description") or ""

        caption_url, caption_lang, caption_ext = choose_caption_url(info)
        transcript = ""

        if caption_url:
            try:
                r = requests.get(caption_url, timeout=20, headers={"User-Agent": USER_AGENT})
                r.raise_for_status()
                transcript = extract_vtt_text(r.text)
            except Exception:
                transcript = ""

        source.metadata["caption_languages"] = list(
            (info.get("subtitles") or info.get("automatic_captions") or {}).keys()
        )
        source.metadata["caption_language_used"] = caption_lang
        source.metadata["duration"] = info.get("duration")
        source.metadata["channel"] = info.get("channel")
        source.metadata["caption_format"] = caption_ext

        source.content = (
            f"TITLE: {source.title}\n"
            f"CHANNEL: {source.author or ''}\n"
            f"UPLOAD DATE: {source.published_date or ''}\n"
            f"DESCRIPTION:\n{description}\n"
        ).strip()

        if transcript:
            source.content += f"\n\nTRANSCRIPT/CAPTIONS:\n{transcript}"

        source.excerpt = source.content[:1200]
        source.fetched_ok = True

    except Exception as exc:
        source.error = str(exc)

    return source


def extract_webpage(url: str) -> Source:
    parsed = urlparse(url)
    source = Source(
        url=url,
        domain=parsed.netloc,
        source_type="webpage",
    )
    try:
        response = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        )
        response.raise_for_status()

        final_url = response.url
        source.url = final_url
        source.domain = urlparse(final_url).netloc

        html = response.text
        extracted = trafilatura.extract(
            html,
            include_links=True,
            include_comments=False,
            include_tables=True,
        )

        if not extracted:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            extracted = soup.get_text("\n", strip=True)

        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        source.title = title or source.domain
        source.content = (extracted or "").strip()
        source.excerpt = source.content[:1200]
        source.fetched_ok = bool(source.content)
        source.metadata["http_status"] = response.status_code
        source.metadata["final_url"] = final_url

        if not source.content:
            source.error = "No readable article text was extracted."

    except Exception as exc:
        source.error = str(exc)

    return source


def collect_sources(urls, progress=None):
    sources = []
    total = len(urls)

    for i, url in enumerate(urls, start=1):
        if progress:
            progress(f"Reading source {i}/{total}: {url}")
        if is_youtube(url):
            source = extract_youtube(url)
        else:
            source = extract_webpage(url)
        sources.append(source)

    return sources


def ddgs_search(query: str, max_results=4):
    try:
        from ddgs import DDGS
    except Exception as exc:
        return [], f"ddgs unavailable: {exc}"

    try:
        with DDGS() as ddgs:
            results = list(
                ddgs.text(
                    query,
                    max_results=max_results,
                )
            )
        return results, None
    except Exception as exc:
        return [], str(exc)


def tavily_search(query: str, api_key: str, max_results=4):
    if not api_key:
        return [], "No Tavily API key configured."

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        results = client.search(
            query,
            max_results=max_results,
            include_raw_content=True,
        )
        return results or [], None
    except Exception as exc:
        return [], str(exc)


def build_search_queries(topic: str):
    topic = topic.strip()
    return [
        f"{topic} latest news",
        f"{topic} official announcement",
        f"{topic} release date details",
        f"{topic} interview production background",
        f"{topic} latest update",
    ]


def run_expanded_research(topic, mode="free", api_key="", progress=None, max_queries=5):
    all_results = []
    errors = []
    queries = build_search_queries(topic)[:max_queries]

    for idx, query in enumerate(queries, start=1):
        if mode == "sources":
            break

        if progress:
            progress(f"Web search {idx}/{len(queries)}: {query}")

        if mode == "tavily":
            results, error = tavily_search(query, api_key)
        else:
            results, error = ddgs_search(query)

        if error:
            errors.append(f"{query}: {error}")
            continue

        for item in results:
            url = item.get("href") or item.get("url") or ""
            all_results.append(
                {
                    "query": query,
                    "title": item.get("title", ""),
                    "url": url,
                    "content": item.get("body") or item.get("content") or "",
                    "raw_content": item.get("raw_content", ""),
                    "source": item.get("source", ""),
                }
            )

    deduped = {}
    for item in all_results:
        if item.get("url"):
            deduped[item["url"]] = item

    return list(deduped.values()), errors


def enrich_search_results(results, progress=None, max_pages=6):
    enriched = []
    seen = set()

    candidates = [
        r for r in results
        if r.get("url") and r["url"] not in seen
    ][:max_pages]

    for idx, result in enumerate(candidates, start=1):
        url = result["url"]
        seen.add(url)

        if progress:
            progress(f"Reading search result {idx}/{len(candidates)}...")

        source = extract_youtube(url) if is_youtube(url) else extract_webpage(url)

        if source.fetched_ok:
            enriched.append(
                {
                    **result,
                    "extracted_title": source.title,
                    "extracted_content": source.content[:12000],
                    "extracted_ok": True,
                }
            )
        else:
            enriched.append(
                {
                    **result,
                    "extracted_content": "",
                    "extracted_ok": False,
                    "extraction_error": source.error,
                }
            )

    return enriched


def make_evidence_from_sources(sources, web_results):
    evidence = []

    for source in sources:
        if not source.fetched_ok or not source.content:
            continue

        evidence.append(
            Evidence(
                claim=f"Source material from {source.title or source.domain}",
                source_urls=[source.url],
                supporting_text=[source.content[:5000]],
                confidence="source_material",
                source_kind=source.source_type,
            )
        )

    for result in web_results:
        content = (
            result.get("extracted_content")
            or result.get("raw_content")
            or result.get("content")
            or ""
        )
        if not content:
            continue

        evidence.append(
            Evidence(
                claim=result.get("title") or "Web research result",
                source_urls=[result.get("url", "")],
                supporting_text=[content[:5000]],
                confidence="web_search",
                source_kind="search_result",
            )
        )

    return evidence
