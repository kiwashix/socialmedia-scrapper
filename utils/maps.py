from parsers.reddit import RedditParser
from parsers.steam import SteamParser
from parsers.twitter import TwitterParser
from parsers.youtube import YouTubeParser
from parsers.rss import RSSParser

PARSER_MAP = {
    'reddit': RedditParser,
    'rss': RSSParser,
    'youtube': YouTubeParser,
    'twitter': TwitterParser,
    'steam': SteamParser
}