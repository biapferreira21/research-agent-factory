"""BM25 com IDF positiva, sem modelos ou chamadas externas."""
from collections import Counter
import math
import re
import unicodedata


def tokenize(text):
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return re.findall(r"\w+", "".join(c for c in normalized if not unicodedata.combining(c)))


def rank(query, documents, *, limit=8):
    if not 1 <= limit <= 50:
        raise ValueError("limit deve estar entre 1 e 50")
    counts = [Counter(tokenize(text)) for text in documents]
    if not counts:
        return []
    average = sum(sum(c.values()) for c in counts) / len(counts) or 1
    terms = set(tokenize(query))
    frequencies = {term: sum(term in c for c in counts) for term in terms}
    scored = []
    for index, counter in enumerate(counts):
        length = sum(counter.values())
        score = 0.0
        for term in terms:
            tf = counter[term]
            idf = math.log(1 + (len(counts) - frequencies[term] + .5) / (frequencies[term] + .5))
            score += idf * tf * 2.5 / (tf + 1.5 * (.25 + .75 * length / average))
        if score > 0:
            scored.append((index, score))
    return sorted(scored, key=lambda pair: (-pair[1], pair[0]))[:limit]
