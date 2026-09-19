from __future__ import annotations

import math
import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Callable

from src import Document, EmbeddingStore, FixedSizeChunker, RecursiveChunker


CORPUS_DIR = Path("data/chinh-sach-shopee")

BENCHMARKS = [
    {
        "query": "Nguoi mua co bao nhieu ngay de yeu cau tra hang hoan tien sau khi giao hang thanh cong?",
        "gold_doc_id": "shopee-dam-bao",
        "answer_contains": "15 ngay",
        "metadata_filter": {"audience": "buyer"},
    },
    {
        "query": "Khi Shopee dang xem xet yeu cau tra hang hoan tien thi bao lau co ket qua?",
        "gold_doc_id": "quy-trinh-tra-hang-hoan-tien",
        "answer_contains": "3-5 ngay lam viec",
        "metadata_filter": None,
    },
    {
        "query": "Sau khi duoc chap nhan tra hang va hoan tien nguoi mua phai gui hang trong bao lau?",
        "gold_doc_id": "quy-trinh-tra-hang-hoan-tien",
        "answer_contains": "6 ngay",
        "metadata_filter": None,
    },
    {
        "query": "Dieu kien bao hanh co ban tren Shopee gom nhung gi?",
        "gold_doc_id": "chinh-sach-bao-hanh-shopee",
        "answer_contains": "con thoi han bao hanh",
        "metadata_filter": None,
    },
    {
        "query": "Huy don do het hang hoac khong xac nhan dung han thi bi phi bao nhieu?",
        "gold_doc_id": "quy-dinh-nguoi-ban-shopee-mall",
        "answer_contains": "196.360 VND",
        "metadata_filter": {"audience": "seller"},
    },
]


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.lower()


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9.]+", normalize_text(text))


class LexicalEmbedder:
    """Small dependency-free embedder for benchmark runs.

    It is not a semantic model, but it gives meaningful local retrieval results
    for this lab corpus without requiring network access or API keys.
    """

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        self._backend_name = "lexical hash embedder"

    def __call__(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in tokenize(text):
            index = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % self.dim
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class HeadingChunker:
    """Split Markdown by headings, falling back to RecursiveChunker for long sections."""

    def __init__(self, chunk_size: int = 700) -> None:
        self.chunk_size = chunk_size
        self.fallback = RecursiveChunker(chunk_size=chunk_size)

    def chunk(self, text: str) -> list[str]:
        sections: list[str] = []
        current: list[str] = []

        for line in text.splitlines():
            if line.startswith("#") and current:
                sections.append("\n".join(current).strip())
                current = [line]
            else:
                current.append(line)

        if current:
            sections.append("\n".join(current).strip())

        chunks: list[str] = []
        for section in sections:
            if not section:
                continue
            if len(section) <= self.chunk_size:
                chunks.append(section)
                continue

            heading = section.splitlines()[0]
            body = "\n".join(section.splitlines()[1:]).strip()
            for piece in self.fallback.chunk(body):
                chunks.append(f"{heading}\n\n{piece}".strip())

        return chunks


def parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---\n"):
        return {}, raw

    _, frontmatter, content = raw.split("---", 2)
    metadata: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, content.strip()


def load_markdown_documents(corpus_dir: Path = CORPUS_DIR) -> list[tuple[Path, dict[str, str], str]]:
    docs = []
    for path in sorted(corpus_dir.glob("*.md")):
        metadata, content = parse_frontmatter(path.read_text(encoding="utf-8"))
        docs.append((path, metadata, content))
    return docs


def make_chunk_documents(chunker: object) -> list[Document]:
    documents: list[Document] = []
    for path, metadata, content in load_markdown_documents():
        doc_id = metadata.get("doc_id", path.stem)
        for index, chunk in enumerate(chunker.chunk(content)):
            chunk_metadata = dict(metadata)
            chunk_metadata["doc_id"] = doc_id
            chunk_metadata["chunk_index"] = str(index)
            chunk_metadata["source_file"] = str(path)
            documents.append(
                Document(
                    id=f"{doc_id}#{index}",
                    content=chunk,
                    metadata=chunk_metadata,
                )
            )
    return documents


def simple_agent_answer(context: str, query: str) -> str:
    query_tokens = set(tokenize(query))
    sentences = re.split(r"(?<=[.!?])\s+|\n+", context)
    ranked = sorted(
        (sentence.strip() for sentence in sentences if sentence.strip()),
        key=lambda sentence: len(query_tokens.intersection(tokenize(sentence))),
        reverse=True,
    )
    return " ".join(ranked[:2]) if ranked else "Khong tim thay cau tra loi trong ngu canh."


def evaluate_strategy(name: str, chunker: object, embedding_fn: Callable[[str], list[float]]) -> None:
    documents = make_chunk_documents(chunker)
    store = EmbeddingStore(collection_name=f"bench_{name}", embedding_fn=embedding_fn)
    store.add_documents(documents)

    print(f"\n=== Strategy: {name} ===")
    print(f"Chunks: {store.get_collection_size()}")

    total = 0
    for number, item in enumerate(BENCHMARKS, start=1):
        query = item["query"]
        metadata_filter = item["metadata_filter"]
        if metadata_filter:
            results = store.search_with_filter(query, top_k=3, metadata_filter=metadata_filter)
        else:
            results = store.search(query, top_k=3)

        context = "\n".join(result["content"] for result in results)
        gold_doc_id = item["gold_doc_id"]
        answer_contains = normalize_text(item["answer_contains"])
        doc_ranks = [result["metadata"].get("doc_id") for result in results]
        has_gold_doc = gold_doc_id in doc_ranks
        has_answer = answer_contains in normalize_text(context)
        score = 2 if has_answer and doc_ranks[:1] == [gold_doc_id] else 1 if has_answer or has_gold_doc else 0
        total += score

        print(f"\nQ{number}. {query}")
        print(f"Filter: {metadata_filter or '-'}")
        print(f"Gold: {gold_doc_id} | contains: {item['answer_contains']} | score: {score}/2")
        for rank, result in enumerate(results, start=1):
            metadata = result["metadata"]
            preview = " ".join(result["content"].split())[:180]
            print(
                f"  {rank}. score={result['score']:.3f} "
                f"doc={metadata.get('doc_id')} audience={metadata.get('audience')} "
                f"chunk={metadata.get('chunk_index')} :: {preview}"
            )
        print(f"Agent-style answer: {simple_agent_answer(context, query)}")

    print(f"\nTotal: {total}/10")


def print_filter_ab_test(chunker: object, embedding_fn: Callable[[str], list[float]]) -> None:
    documents = make_chunk_documents(chunker)
    store = EmbeddingStore(collection_name="bench_filter_ab", embedding_fn=embedding_fn)
    store.add_documents(documents)

    print("\n=== Metadata Filter A/B Test (heading strategy) ===")
    for item in BENCHMARKS:
        if not item["metadata_filter"]:
            continue
        query = item["query"]
        print(f"\nQuery: {query}")
        for label, metadata_filter in (("without_filter", None), ("with_filter", item["metadata_filter"])):
            results = (
                store.search_with_filter(query, top_k=3, metadata_filter=metadata_filter)
                if metadata_filter
                else store.search(query, top_k=3)
            )
            print(f"  {label}:")
            for rank, result in enumerate(results, start=1):
                metadata = result["metadata"]
                print(
                    f"    {rank}. score={result['score']:.3f} "
                    f"doc={metadata.get('doc_id')} audience={metadata.get('audience')}"
                )


def print_baseline_stats() -> None:
    sample_docs = load_markdown_documents()[:3]
    strategies = {
        "fixed_size": FixedSizeChunker(chunk_size=500, overlap=50),
        "recursive": RecursiveChunker(chunk_size=500),
        "heading": HeadingChunker(chunk_size=700),
    }
    print("=== Baseline Chunking Stats ===")
    for path, _metadata, content in sample_docs:
        print(f"\nDocument: {path.name}")
        for name, chunker in strategies.items():
            chunks = chunker.chunk(content)
            avg_length = sum(len(chunk) for chunk in chunks) / len(chunks) if chunks else 0
            print(f"  {name}: count={len(chunks)}, avg_length={avg_length:.1f}")


def main() -> None:
    embedding_fn = LexicalEmbedder()
    print(f"Corpus: {CORPUS_DIR}")
    print(f"Embedding: {embedding_fn._backend_name}")
    print_baseline_stats()
    evaluate_strategy("fixed_size", FixedSizeChunker(chunk_size=500, overlap=50), embedding_fn)
    evaluate_strategy("recursive", RecursiveChunker(chunk_size=500), embedding_fn)
    heading_chunker = HeadingChunker(chunk_size=700)
    evaluate_strategy("heading", heading_chunker, embedding_fn)
    print_filter_ab_test(heading_chunker, embedding_fn)


if __name__ == "__main__":
    main()
