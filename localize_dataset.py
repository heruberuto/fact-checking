import json
import os
import sys
import urllib

import requests
from slugify import slugify

SOURCE_LANGUAGE, TARGET_LANGUAGE, WIKI_MAX_TITLES = "en", "cs", 50


def fetch_localizations(titles):
    path = "cache/{}-{}-{}.json".format(SOURCE_LANGUAGE, slugify("|".join(titles)), TARGET_LANGUAGE)
    if not os.path.exists(path):
        with requests.get(compose_address(titles)) as response:
            try:
                with open(path, 'w') as cache:
                    print(response.text, file=cache)
            except OSError:
                print("name too long, cache skipped: {}".format(path), file=sys.stderr)
            return json.loads(response.text)
    else:
        with open(path, 'r') as cache:
            return json.load(cache)


def compose_address(titles):
    titles = [urllib.parse.quote(title) for title in titles]
    return "https://{}.wikipedia.org/w/api.php?action=query&titles={}&prop=langlinks&format=json&lllang={}" \
        .format(SOURCE_LANGUAGE, "|".join(titles), TARGET_LANGUAGE)


def parse_title(stanford_title):
    stanford_char_mapping = {
        "-LRB-": "(",
        "-RRB-": ")",
        "-COLON-": ":",
        "_": " "
    }
    for key, val in stanford_char_mapping.items():
        stanford_title = stanford_title.replace(key, val)
    return stanford_title


def load(mapping):
    responses = []
    buffer = []
    for k in mapping.keys():
        buffer.append(k)
        if len(buffer) == 10:
            responses.append(fetch_localizations(buffer))
            buffer = []
    with open('dump.json', 'w') as f:
        json.dump(responses, f)

    return


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Invalid number of arguments. 1 expected.")
        exit(1)
    with open(sys.argv[1], "r") as f:
        mapping = {}
        for line in f:
            data_point = json.loads(line)
            for sufficient_evidence in data_point['evidence']:
                for article in sufficient_evidence:
                    if article[2] is not None:
                        mapping[parse_title(article[2])] = None
        load(mapping)

        print(compose_address(mapping))
