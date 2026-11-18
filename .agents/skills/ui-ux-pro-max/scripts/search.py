#!/usr/bin/env python3
"""
UI/UX Pro Max - Offline Local Design Intelligence Search Tool
Implements in-memory BM25 search over local design guidelines and tokens.
Uses Python standard library only - zero external dependencies and zero network calls.
"""

import os
import sys
import json
import math
import re
import argparse
from typing import List, Dict, Any, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.abspath(os.path.join(HERE, "..", "data", "design_rules.json"))


def tokenize(text: str) -> List[str]:
    """Tokenize and normalize text into lowercase alphanumeric words."""
    if not text:
        return []
    return [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", text)]


def load_dataset() -> List[Dict[str, Any]]:
    """Load design database from local disk."""
    if not os.path.isfile(DATA_PATH):
        sys.stderr.write(f"Error: Design rules file not found at {DATA_PATH}\n")
        return []
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("entries", [])
    except Exception as e:
        sys.stderr.write(f"Error reading {DATA_PATH}: {e}\n")
        return []


class BM25Index:
    """Lightweight in-memory BM25 indexer."""
    def __init__(self, docs: List[Dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs = docs
        self.doc_len: List[int] = []
        self.doc_tokens: List[List[str]] = []
        self.df: Dict[str, int] = {}
        self.avg_doc_len = 0.0
        self._build_index()

    def _extract_doc_text(self, d: Dict[str, Any]) -> str:
        parts = [
            d.get("title", ""),
            d.get("category", ""),
            " ".join(d.get("tags", [])),
            d.get("description", "")
        ]
        if "rules" in d:
            parts.extend(d["rules"])
        if "tokens" in d:
            parts.extend([f"{k} {v}" for k, v in d["tokens"].items()])
        if "palette" in d:
            parts.append(json.dumps(d["palette"]))
        return " ".join(parts)

    def _build_index(self):
        total_len = 0
        for doc in self.docs:
            text = self._extract_doc_text(doc)
            tokens = tokenize(text)
            self.doc_tokens.append(tokens)
            l = len(tokens)
            self.doc_len.append(l)
            total_len += l
            seen = set(tokens)
            for t in seen:
                self.df[t] = self.df.get(t, 0) + 1

        n = len(self.docs)
        self.avg_doc_len = (total_len / n) if n > 0 else 0.0

    def search(self, query: str, category: str = None, top_k: int = 5) -> List[Tuple[float, Dict[str, Any]]]:
        q_tokens = tokenize(query)
        if not q_tokens:
            return []

        n = len(self.docs)
        scores: List[Tuple[float, Dict[str, Any]]] = []

        for idx, doc in enumerate(self.docs):
            if category and doc.get("category", "").lower() != category.lower():
                continue

            doc_tokens = self.doc_tokens[idx]
            d_len = self.doc_len[idx]
            tf_map: Dict[str, int] = {}
            for t in doc_tokens:
                tf_map[t] = tf_map.get(t, 0) + 1

            score = 0.0
            for qt in q_tokens:
                if qt not in tf_map:
                    continue
                tf = tf_map[qt]
                df = self.df.get(qt, 0)
                # BM25 IDF with smoothing
                idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
                # BM25 TF component
                num = tf * (self.k1 + 1.0)
                denom = tf + self.k1 * (1.0 - self.b + self.b * (d_len / (self.avg_doc_len or 1.0)))
                score += idf * (num / denom)

            if score > 0.0:
                scores.append((score, doc))

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[:top_k]


def main():
    parser = argparse.ArgumentParser(description="UI/UX Pro Max Local Design Search")
    parser.add_argument("query", type=str, help="Search terms (e.g. 'dashboard', 'palette', 'table')")
    parser.add_argument("--category", "-c", type=str, default=None, help="Filter by category (styles, palettes, typography, stack, components)")
    parser.add_argument("--limit", "-n", type=int, default=3, help="Max results to display")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()
    entries = load_dataset()
    if not entries:
        print("No design entries available.")
        sys.exit(1)

    index = BM25Index(entries)
    results = index.search(args.query, category=args.category, top_k=args.limit)

    if args.json:
        formatted = [{"score": round(score, 3), "entry": doc} for score, doc in results]
        print(json.dumps(formatted, indent=2))
        return

    if not results:
        print(f"No design rules found matching '{args.query}'.")
        return

    print(f"\nFound {len(results)} relevant design rule(s) for query: '{args.query}'\n" + "=" * 60)
    for score, doc in results:
        print(f"[{doc.get('category', 'general').upper()}] {doc.get('title')} (BM25: {score:.2f})")
        print(f"Description: {doc.get('description', '')}")
        if "tokens" in doc:
            print("Tokens:")
            for k, v in doc["tokens"].items():
                print(f"  • {k}: {v}")
        if "rules" in doc:
            print("Key Guidelines:")
            for r in doc["rules"][:3]:
                print(f"  • {r}")
        print("-" * 60)


if __name__ == "__main__":
    main()
