from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict, Any


@dataclass
class Source:
    url: str
    title: str = ""
    domain: str = ""
    source_type: str = "webpage"
    published_date: Optional[str] = None
    author: Optional[str] = None
    content: str = ""
    excerpt: str = ""
    fetched_ok: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class Evidence:
    claim: str
    source_urls: List[str] = field(default_factory=list)
    supporting_text: List[str] = field(default_factory=list)
    confidence: str = "unknown"
    source_kind: str = "web"

    def to_dict(self):
        return asdict(self)


@dataclass
class ResearchBrief:
    topic: str
    summary: str = ""
    key_facts: List[str] = field(default_factory=list)
    timeline: List[str] = field(default_factory=list)
    people: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
