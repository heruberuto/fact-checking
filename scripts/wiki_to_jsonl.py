import json
import os
import re
import sys
from xml.etree import ElementTree

import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
import xmltodict as xmltodict
from wikiextractor.WikiExtractor import Extractor

article, reading, e = "", False, Extractor(None, None, None, [])
COMMON_ABBREVIATIONS = {"např.": "například", "atd.": "atd", }


def is_article_beginning(line):
    return line == "  <page>\n"


def is_article_ending(line):
    return line.startswith("==") or line.startswith("&lt;!-") or "</text>" in line


def cleanhtml(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, ' ', raw_html)
    return ' '.join(cleantext.split())


def cleantext(text):
    result = text + "\n"
    while text != result:
        text = result
        result.replace("\n\n", "\n")
        result.replace("\t", " ")
        result.replace("  ", " ")
    return result


with open("/local/fever-common/data/cswiki-20200520-pages-articles.xml") as file, \
        open("wiki-pages/wiki-001.jsonl", "w") as out:
    st = nltk.CoreNLPParser()
    for line in file:
        if not reading and is_article_beginning(line):
            article, reading = line, True
        elif reading and is_article_ending(line):
            try:
                et = xmltodict.parse(article + "</text></revision></page>")
                sentences = sent_tokenize(cleanhtml(e.wiki2text(et["page"]["revision"]["text"]["#text"])), "czech")
                sentences = [" ".join(word_tokenize(sentence, language="czech")) for sentence in sentences]

                print(sentences)
                print(json.dumps({"id": et["page"]["title"], "text": " ".join(sentences), "sentences": sentences}, ensure_ascii=False),
                      file=out)
            except:
                print(article, file=sys.stderr)
            reading = False
        else:
            article += line
