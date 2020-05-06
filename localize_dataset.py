import json
import sys
import urllib

import requests

SOURCE_LANGUAGE, TARGET_LANGUAGE, WIKI_MAX_TITLES = "en", "cs", 50
title_buffer = set()

def flush_buffer():
    global title_buffer
    with requests.get(compose_address(title_buffer)) as response:
        print(response.text)
    title_buffer = set()


def compose_address(titles):
    titles = [urllib.parse.quote(title) for title in titles]
    return "https://{}.wikipedia.org/w/api.php?action=query&titles={}&prop=langlinks&format=json"\
        .format(SOURCE_LANGUAGE,"|".join(titles))

def parse_title(stanford_title):
    stanford_char_mapping = {
        "-LRB-": "(",
        "-RRB-": ")",
        "_": " "
    }
    for key, val in stanford_char_mapping.items():
        stanford_title = stanford_title.replace(key, val)
    return stanford_title


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Invalid number of arguments. 1 expected.")
        exit(1)
    with open(sys.argv[1], "r") as f:
        titles = set()
        for line in f:
            data_point = json.loads(line)
            for sufficient_evidence in data_point['evidence']:
                for article in sufficient_evidence:
                    if article[2] is not None:
                        title_buffer.add(parse_title(article[2]))
                        if len(title_buffer) == 50:
                            flush_buffer()

        print(compose_address(titles))
