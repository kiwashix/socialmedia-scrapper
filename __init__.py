from parsers.reddit import RedditParser
from parsers.twitter import TwitterParser
from parsers.youtube import YouTubeParser
from parsers.steam import SteamParser
from parsers.rss import RSSParser

ALL_PARSERS = [
    RedditParser,
    TwitterParser,
    YouTubeParser,
    SteamParser,
    RSSParser,
]

__all__ = ALL_PARSERS
