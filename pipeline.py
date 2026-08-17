import json

from models import ResearchBrief
from research import (
    collect_sources,
    run_expanded_research,
    enrich_search_results,
    make_evidence_from_sources,
)
from llm import LlamaServer, SYSTEM_PROMPT, research_brief_prompt, script_prompt


def _emit(progress, message):
    if progress:
        progress(message)


def generate(
    urls,
    topic,
    research_mode,
    tavily_api_key,
    llama_url,
    progress=None,
    on_stream=None,
    target_words=700,
    target_minutes=5,
):
    _emit(progress, f"[1/5] Collecting and reading {len(urls)} source URL(s)...")
    sources = collect_sources(urls, progress=progress)
    ok_sources = sum(1 for s in sources if s.fetched_ok)
    _emit(progress, f"[Research] Successfully fetched {ok_sources}/{len(urls)} source links.")

    if research_mode == "sources":
        web_results = []
        search_errors = []
        _emit(progress, "[Research] Web search skipped (Supplied sources only mode).")
    else:
        _emit(progress, f"[2/5] Searching web for '{topic}' (Mode: {research_mode})...")
        search_results, search_errors = run_expanded_research(
            topic,
            mode=research_mode,
            api_key=tavily_api_key,
            progress=progress,
        )

        _emit(progress, f"[3/5] Reading content from {min(len(search_results), 6)} selected search result pages...")
        web_results = enrich_search_results(
            search_results,
            progress=progress,
            max_pages=6,
        )
        _emit(progress, f"[Research] Extracted readable articles from {len(web_results)} web pages.")

    _emit(progress, "Building evidence set and cross-referencing facts...")
    evidence = make_evidence_from_sources(sources, web_results)
    _emit(progress, f"[Evidence] Prepared {len(evidence)} evidence points.")

    llama = LlamaServer(llama_url)

    if not llama.health(timeout=2.0):
        raise RuntimeError(
            f"llama-server is not reachable at {llama_url}.\n\n"
            "Please ensure the local AI server is started."
        )

    # 4. Generate structured research brief
    _emit(progress, "[4/5] Generating compact research brief with local AI...")

    def on_brief_token(tok):
        if on_stream:
            on_stream("brief", tok)

    def on_brief_progress(msg):
        _emit(progress, f"[Brief] {msg}")

    brief_text = llama.chat(
        SYSTEM_PROMPT,
        research_brief_prompt(
            topic,
            [s.to_dict() for s in sources],
            web_results,
        ),
        temperature=0.15,
        max_tokens=3500,
        on_token=on_brief_token,
        on_progress=on_brief_progress,
    )

    try:
        start = brief_text.find("{")
        end = brief_text.rfind("}")
        brief_data = json.loads(brief_text[start:end + 1])
    except Exception:
        brief_data = {
            "summary": brief_text,
            "key_facts": [],
            "timeline": [],
            "people": [],
            "conflicts": [],
            "unknowns": [],
            "content_plan": [],
        }

    brief = ResearchBrief(
        topic=topic,
        summary=brief_data.get("summary", ""),
        key_facts=brief_data.get("key_facts", []),
        timeline=brief_data.get("timeline", []),
        people=brief_data.get("people", []),
        conflicts=brief_data.get("conflicts", []),
        unknowns=brief_data.get("unknowns", []),
        content_plan=brief_data.get("content_plan", []),
        sources=[s.to_dict() for s in sources],
        evidence=[e.to_dict() for e in evidence],
    )

    if search_errors:
        brief.unknowns.extend(
            [f"Search warning: {error}" for error in search_errors[:10]]
        )

    writing_brief = {
        "topic": brief.topic,
        "summary": brief.summary,
        "key_facts": brief.key_facts,
        "timeline": brief.timeline,
        "people": brief.people,
        "conflicts": brief.conflicts,
        "unknowns": brief.unknowns,
        "content_plan": brief.content_plan,
    }

    # Token headroom calculation: ~140 words/min, generous buffer to guarantee 100% complete ending
    max_script_tokens = max(3000, min(8192, int(target_words * 2.2)))

    # 5. Writing scripts
    _emit(progress, f"[5/5] Writing Version A: Documentary Script (~{target_minutes} mins / ~{target_words} words)...")

    def on_script_a_token(tok):
        if on_stream:
            on_stream("script_a", tok)

    def on_script_a_progress(msg):
        _emit(progress, f"[Documentary Script] {msg}")

    script_a = llama.chat(
        SYSTEM_PROMPT,
        script_prompt(writing_brief, "documentary", target_words=target_words, target_minutes=target_minutes),
        temperature=0.5,
        max_tokens=max_script_tokens,
        on_token=on_script_a_token,
        on_progress=on_script_a_progress,
    )

    _emit(progress, f"[5/5] Writing Version B: High-Retention YouTube Script (~{target_minutes} mins / ~{target_words} words)...")

    def on_script_b_token(tok):
        if on_stream:
            on_stream("script_b", tok)

    def on_script_b_progress(msg):
        _emit(progress, f"[YouTube Script] {msg}")

    script_b = llama.chat(
        SYSTEM_PROMPT,
        script_prompt(writing_brief, "youtube", target_words=target_words, target_minutes=target_minutes),
        temperature=0.65,
        max_tokens=max_script_tokens,
        on_token=on_script_b_token,
        on_progress=on_script_b_progress,
    )

    _emit(progress, "All research and script generation finished successfully.")

    return {
        "brief": brief.to_dict(),
        "web_results": web_results,
        "search_errors": search_errors,
        "script_a": script_a,
        "script_b": script_b,
        "target_words": target_words,
        "target_minutes": target_minutes,
    }
