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
    confidence: Any = "high"
    source_kind: str = "web"
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    evidence_text: Optional[str] = None

    def __post_init__(self):
        if self.source_url and not self.source_urls:
            self.source_urls = [self.source_url]
        if self.evidence_text and not self.supporting_text:
            self.supporting_text = [self.evidence_text]

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
    content_plan: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
