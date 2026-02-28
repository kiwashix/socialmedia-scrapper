"""
parsers/__init__.py – Parser modules.
"""
from parsers.base import BaseParser, NewsItem
from parsers.bungie import BungieParser
from parsers.reddit import RedditParser
from parsers.twitter import TwitterParser
from parsers.youtube import YouTubeParser
from parsers.steam import SteamParser
from parsers.gaming_news import GamingNewsParser
from parsers.official_site import OfficialSiteParser

__all__ = [
    BungieParser,
    RedditParser,
    TwitterParser,
    YouTubeParser,
    SteamParser,
    GamingNewsParser,
    OfficialSiteParser,
]
