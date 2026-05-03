from dataclasses import dataclass

@dataclass
class NewsItem:
    title: str
    link: str
    pub_date: str
    description: str
    source_name: str
    source_kind: str
