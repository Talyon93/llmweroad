"""Build (or refresh) the Chroma index for both chunking strategies."""

from casavaiano.rag.retriever import default_retriever


def main() -> None:
    for strategy in ("headings", "fixed"):
        retriever = default_retriever(strategy)
        rebuilt = retriever.ensure_index()
        count = retriever._collection.count()
        print(f"{strategy:9} {count:3} chunks  {'rebuilt' if rebuilt else 'up to date'}")


if __name__ == "__main__":
    main()
