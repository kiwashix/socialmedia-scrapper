from parsers.bungie import BungieParser
from parsers.reddit import RedditParser
from parsers.twitter import TwitterParser
from parsers.youtube import YouTubeParser
from parsers.steam import SteamParser
from parsers.gaming_news import GamingNewsParser
from parsers.official_site import OfficialSiteParser

ALL_PARSERS = [
    BungieParser,
    RedditParser,
    TwitterParser,
    YouTubeParser,
    SteamParser,
    GamingNewsParser,
    OfficialSiteParser,
]

__all__ = ALL_PARSERS
