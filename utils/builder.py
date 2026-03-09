from utils.maps import PARSER_MAP

def build_parsers(config):

    parsers = []

    for category, sources in config['sources'].items():
        for source in sources:
            parser_class = PARSER_MAP.get(source['type'])

            if not parser_class:
                continue

            parsers.append(parser_class(source))

    return parsers