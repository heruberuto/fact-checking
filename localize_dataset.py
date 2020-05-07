# -*- coding: utf-8 -*-

import json
import os
import sys
import urllib

import requests
from slugify import slugify

SOURCE_LANGUAGE, TARGET_LANGUAGE, BUFFER_SIZE = "en", "cs", 10


def file_infix(titles):
    result = slugify("|".join(titles))
    if len(result) >= 244:
        return result[:242] + ".."
    return result


def fetch_localizations(titles):
    path = "cache/{}-{}-{}.json".format(SOURCE_LANGUAGE, file_infix(titles), TARGET_LANGUAGE)
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
    if stanford_title is None: return None
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
        if len(buffer) == BUFFER_SIZE:
            responses.append(fetch_localizations(buffer))
            buffer = []
    k = 0
    for response in responses:
        query = response["query"]
        # denormalize = {}
        # if "normalized" in query:
        #    for normalized in query["normalized"]:
        for page in query["pages"].values():
            if "langlinks" in page:
                if page["title"] not in mapping:
                    k += 1
                    print("Weird, title absent: " + page["title"], file=sys.stderr)
                mapping[page["title"]] = page["langlinks"][0]["*"]

    with open('dump_responses.json', 'w') as f, open('dump_mapping.json', 'w') as g:
        json.dump(responses, f)
        json.dump(mapping, g)

    i = j = 0
    for val in mapping.values():
        if val is None:
            j += 1
        i += 1
    print(f"Of {i} articles: {i - j} preserved, {j} lost, of which {k} due to normalization", file=sys.stderr)


def localize_evidence(evidences, mapping):
    result = []
    for ev in evidences:
        ev_ = []
        for article in ev:
            title = parse_title(article[2])
            if title is not None and title in mapping and mapping[title] is not None:
                article[2] = mapping[title]
                article.append(title)
                ev_.append(article)
            else:
                break
        if len(ev) == len(ev_):
            result.append(ev_)
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Invalid number of arguments. >=1 expected.")
        exit(1)
    if len(sys.argv) > 2:
        SOURCE_LANGUAGE = sys.argv[2]
    if len(sys.argv) > 3:
        TARGET_LANGUAGE = sys.argv[3]

    with open(sys.argv[1], "r") as f:
        mapping = {}
        data_points = []
        for line in f:
            data_point = json.loads(line)
            data_points.append(data_point)
            for sufficient_evidence in data_point['evidence']:
                for article in sufficient_evidence:
                    if article[2] is not None:
                        mapping[parse_title(article[2])] = None
        load(mapping)
        result = []
        aborted = not_verifiable = 0
        with open('cs.jsonl', 'w') as saved, open('lost.jsonl', 'w') as lost, open('mapping.json', 'w') as map_file:
            for data_point in data_points:
                evs = localize_evidence(data_point['evidence'], mapping)
                if len(evs) > 0 or data_point["verifiable"] == "NOT VERIFIABLE":
                    if data_point["verifiable"] == "NOT VERIFIABLE": not_verifiable += 1
                    data_point['evidence'] = evs
                    result.append(data_point)
                    print(json.dumps(data_point), file=saved)
                else:
                    print(json.dumps(data_point), file=lost)
                    aborted += 1
            json.dump(mapping, map_file)
        print(f"Of {len(data_points)} data points, {len(result)} survived the localization (of which {not_verifiable} was not verifiable), {aborted} didn't")
