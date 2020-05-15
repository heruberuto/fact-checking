# -*- coding: utf-8 -*-
import hashlib
import json
import os
import sys
import urllib

import requests
from slugify import slugify
from google.cloud import translate_v3  # TODO: pip install google-cloud-translate

GOOGLE_CLIENT = translate_v3.TranslationServiceClient()

SOURCE_FILE, SOURCE_LANGUAGE, TARGET_FILE, TARGET_LANGUAGE = sys.stdin, "en", sys.stdout, "cs"
GOOGLE_PATH, GOOGLE_BUFFER_SIZE = GOOGLE_CLIENT.location_path("supple-century-275511", "us-central1"), 200
WIKI_PATH, WIKI_BUFFER_SIZE = "https://{}.wikipedia.org/w/api.php?action=query&titles={}&prop=langlinks&format=json&lllang={}", 10


def fetch_google_response(buffer):
    path = "cache/_gtranslate_" + hashlib.md5("".join(buffer).encode('utf-8')).hexdigest() + ".json"
    if not os.path.exists(path):
        response = GOOGLE_CLIENT.translate_text(parent=GOOGLE_PATH, contents=buffer, mime_type="text/plain",
                                                source_language_code=SOURCE_LANGUAGE,
                                                target_language_code=TARGET_LANGUAGE)
        result = [translation.translated_text for translation in response.translations]
        with open(path, 'w') as cache:
            json.dump(result, cache)
        return result
    else:
        with open(path, 'r') as cache:
            return json.load(cache)


def google_translate(data_points):
    buffer = []
    for i in range(len(data_points)):
        buffer.append(data_points[i]["claim"])
        if len(buffer) == GOOGLE_BUFFER_SIZE or i == len(data_points) - 1:
            translations = fetch_google_response(buffer)
            for j in range(len(buffer)):
                data_points[i - j]["claim"] = translations[-j - 1]
                data_points[i - j]["claim_" + SOURCE_LANGUAGE] = buffer[-j - 1]
            buffer = []


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
    return WIKI_PATH.format(SOURCE_LANGUAGE, "|".join(titles), TARGET_LANGUAGE)


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
        if len(buffer) == WIKI_BUFFER_SIZE:
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
    print(f"Of {i} wiki articles: {i - j} preserved, {j} lost, of which {k} due to normalization", file=sys.stderr)


TOSSED = KEPT = 0


def localize_evidence(evidence_set_set, mapping):
    global TOSSED, KEPT
    result = []
    for evidence_set in evidence_set_set:
        ev_ = []
        for article in evidence_set:
            title = parse_title(article[2])
            if title is not None and title in mapping and mapping[title] is not None:
                article[2] = mapping[title]
                article.append(title)
                ev_.append(article)
            else:
                break
        if len(evidence_set) == len(ev_):
            result.append(ev_)
            KEPT += 1
        else:
            TOSSED += 1
    return result


if __name__ == "__main__":
    if len(sys.argv) > 1:
        SOURCE_FILE = open(sys.argv[1], "r")
    if len(sys.argv) > 2:
        SOURCE_LANGUAGE = sys.argv[2]
    if len(sys.argv) > 3:
        TARGET_FILE = open(sys.argv[3], "w", encoding='utf-8')
    if len(sys.argv) > 4:
        TARGET_LANGUAGE = sys.argv[4]

    mapping = {}
    data_points = []
    for line in SOURCE_FILE:
        data_point = json.loads(line)
        data_points.append(data_point)
        for sufficient_evidence in data_point['evidence']:
            for article in sufficient_evidence:
                if article[2] is not None:
                    mapping[parse_title(article[2])] = None
    load(mapping)
    result = []
    aborted = not_verifiable = 0
    with open('aux_lost_points.jsonl', 'w') as lost, open('aux_mapping.json', 'w') as map_file:
        to_save = []
        for data_point in data_points:
            evs = localize_evidence(data_point['evidence'], mapping)
            if len(evs) > 0 or data_point["verifiable"] == "NOT VERIFIABLE":
                if data_point["verifiable"] == "NOT VERIFIABLE": not_verifiable += 1
                data_point['evidence'] = evs
                result.append(data_point)
            else:
                print(json.dumps(data_point), file=lost)
                aborted += 1
        json.dump(mapping, map_file)

    google_translate(result)
    TARGET_FILE.writelines(json.dumps(data_point, ensure_ascii=False) + "\n" for data_point in result)
    SOURCE_FILE.close(), TARGET_FILE.close()
    print(
        f"Of {len(data_points)} data points, {len(result)} survived the localization (of which {not_verifiable} was not verifiable), {aborted} didn't")
    print(f"{TOSSED} evidences tossed, {KEPT} kept")
