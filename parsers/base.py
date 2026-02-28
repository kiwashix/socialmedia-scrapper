"""
parsers/base.py – Base classes for all parsers.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NewsItem:
    """Represents a single news item from any source."""
    source: str = ""
    source_key: str = ""
    item_id: str = ""
    title: str = ""
    url: str = ""
    body: str = ""
    published: str = ""
    author: str = ""
    media_urls: List[str] = field(default_factory=list)
    score: int = 0
    tags: List[str] = field(default_factory=list)


class BaseParser:
    """Base class for all news parsers."""
    
    SOURCE_NAME: str = "Unknown"
    SOURCE_KEY: str = "unknown"
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def fetch(self) -> List[NewsItem]:
        """Fetch news items. Must be implemented by subclasses."""
        raise NotImplementedError
