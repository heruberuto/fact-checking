import json
import sqlite3

UPDATE = 'UPDATE documents SET lines=? WHERE rowid=?'
with open("wiki-pages/wiki-001.jsonl") as jsonl:
    conn = sqlite3.connect('fever_cs.db')
    cur = conn.cursor()
    try:
        cur.execute('ALTER TABLE documents ADD COLUMN lines TEXT NULL;')
    except sqlite3.OperationalError:
        print("Column already exists.")

    values = []
    i = 1
    for line in jsonl:
        article = json.loads(line)
        sentences = "\n".join(f"{k}\t{v}" for k, v in zip(range(len(article["sentences"])), article["sentences"]))
        cur.execute(UPDATE, (sentences, i))
        i += 1
    conn.commit()
    conn.close()
