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
        # Fallback to any language
        for lang, entries in collection.items():
            for entry in entries:
                if entry.get("url"):
                    return entry["url"], lang, entry.get("ext", "")
    return None, None, None


def extract_youtube(url: str, progress=None) -> Source:
    if progress:
        progress(f"[YouTube] Connecting to video: {url}")

    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:
        err_msg = f"yt-dlp unavailable: {exc}"
        if progress:
            progress(f"[YouTube ERROR] {err_msg}")
        return Source(
            url=url,
            domain=urlparse(url).netloc,
            source_type="youtube",
            error=err_msg,
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
            "no_warnings": True,
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        source.url = info.get("webpage_url") or url
        source.title = info.get("title") or "YouTube video"
        source.author = info.get("uploader") or info.get("channel") or "Unknown Creator"
        source.published_date = info.get("upload_date")
        duration_sec = info.get("duration") or 0
        dur_mins = round(duration_sec / 60, 1) if duration_sec else 0
        description = info.get("description") or ""

        if progress:
            progress(f"[YouTube] Video Found: '{source.title}' | Creator: '{source.author}' | Duration: ~{dur_mins} mins")

        caption_url, caption_lang, caption_ext = choose_caption_url(info)
        transcript = ""

        if caption_url:
            if progress:
                progress(f"[YouTube] Downloading subtitles & spoken transcript (Language: {caption_lang}, Format: {caption_ext})...")
            try:
                r = requests.get(caption_url, timeout=20, headers={"User-Agent": USER_AGENT})
                r.raise_for_status()
                transcript = extract_vtt_text(r.text)
                word_count = len(re.findall(r'\b\w+\b', transcript))
                if progress:
                    progress(f"[YouTube SUCCESS] Extracted {word_count:,} words of spoken video transcript from '{source.title}'!")
            except Exception as cap_err:
                if progress:
                    progress(f"[YouTube WARNING] Could not download caption stream: {cap_err}")
                transcript = ""
        else:
            if progress:
                progress(f"[YouTube INFO] No closed captions available for '{source.title}'. Using video title and description.")

        source.metadata["caption_languages"] = list(
            (info.get("subtitles") or info.get("automatic_captions") or {}).keys()
        )
        source.metadata["caption_language_used"] = caption_lang
        source.metadata["duration"] = duration_sec
        source.metadata["channel"] = source.author
        source.metadata["caption_format"] = caption_ext

        source.content = (
            f"TITLE: {source.title}\n"
            f"CHANNEL: {source.author or ''}\n"
            f"UPLOAD DATE: {source.published_date or ''}\n"
            f"DURATION: {dur_mins} mins\n"
            f"DESCRIPTION:\n{description}\n"
        ).strip()

        if transcript:
            source.content += f"\n\nSPOKEN TRANSCRIPT/CAPTIONS:\n{transcript}"

        source.excerpt = source.content[:1200]
        source.fetched_ok = True

    except Exception as exc:
        source.error = str(exc)
        if progress:
            progress(f"[YouTube ERROR] Failed to extract video info: {exc}")

    return source


def extract_webpage(url: str, progress=None) -> Source:
    if progress:
        progress(f"[Web] Fetching article: {url}")
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

        word_count = len(re.findall(r'\b\w+\b', source.content))
        if progress and source.fetched_ok:
            progress(f"[Web SUCCESS] Extracted {word_count:,} words from '{source.title}'")

        if not source.content:
            source.error = "No readable article text was extracted."
            if progress:
                progress(f"[Web WARNING] No readable text found at {url}")

    except Exception as exc:
        source.error = str(exc)
        if progress:
            progress(f"[Web ERROR] Failed to fetch {url}: {exc}")

    return source


def collect_sources(urls, progress=None):
    sources = []
    total = len(urls)

    for i, url in enumerate(urls, start=1):
        if progress:
            progress(f"[Source {i}/{total}] Processing: {url}")
        if is_youtube(url):
            source = extract_youtube(url, progress=progress)
        else:
            source = extract_webpage(url, progress=progress)
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
    ]


def run_expanded_research(topic: str, mode: str = "free", api_key: str = "", progress=None):
    queries = build_search_queries(topic)
    all_results = []
    errors = []

    for query in queries:
        if progress:
            progress(f"Searching: '{query}'")

        if mode == "tavily":
            results, err = tavily_search(query, api_key=api_key)
        else:
            results, err = ddgs_search(query)

        if err:
            errors.append(f"{query}: {err}")
        else:
            for item in results:
                item["query"] = query
                all_results.append(item)

    seen = set()
    deduped = []
    for item in all_results:
        url = item.get("url") or item.get("link")
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(item)

    return deduped, errors


def enrich_search_results(results, progress=None, max_pages=6):
    enriched = []
    candidates = results[:max_pages]
    total = len(candidates)

    for i, item in enumerate(candidates, start=1):
        url = item.get("url") or item.get("link")
        if not url:
            continue
        if progress:
            progress(f"Reading search result {i}/{total}...")
        try:
            r = requests.get(
                url,
                timeout=12,
                headers={"User-Agent": USER_AGENT},
                allow_redirects=True,
            )
            r.raise_for_status()
            text = trafilatura.extract(r.text, include_links=True)
            if text:
                item["extracted_content"] = text
                item["fetched_ok"] = True
            else:
                item["fetched_ok"] = False
        except Exception as exc:
            item["error"] = str(exc)
            item["fetched_ok"] = False
        enriched.append(item)

    return enriched


def make_evidence_from_sources(sources, web_results):
    evidence_list = []

    for s in sources:
        if not s.fetched_ok:
            continue
        evidence_list.append(
            Evidence(
                claim=f"Primary source from {s.domain}: {s.title}",
                source_urls=[s.url] if s.url else [],
                supporting_text=[s.excerpt or s.content[:300]],
                confidence="high",
                source_kind=s.source_type,
            )
        )

    for r in web_results:
        if not r.get("fetched_ok"):
            continue
        evidence_list.append(
            Evidence(
                claim=f"Search result for '{r.get('query')}': {r.get('title')}",
                source_urls=[r.get("url")] if r.get("url") else [],
                supporting_text=[(r.get("extracted_content") or r.get("body") or "")[:300]],
                confidence="medium",
                source_kind="web",
            )
        )

    return evidence_list
