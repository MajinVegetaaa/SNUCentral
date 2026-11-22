"""CLI: python -m snu_central.generation "How do I drop a course?"  |  --models lists what the provider offers."""

import argparse
import sys

from ..config import load_config
from ..retrieval import load_retriever
from . import Answer, answer_stream
from .citations import resolve
from .providers import LLMUnavailable, get_provider


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?")
    ap.add_argument("--models", action="store_true", help="list models the provider currently offers")
    a = ap.parse_args()
    cfg = load_config()
    if a.models:
        try:
            p = get_provider(cfg)
            have = p.available_models()
            print("\n".join(have) or "(could not list models)")
            print("\nconfigured:", [cfg["llm"]["model"], *cfg["llm"].get("fallback_models", [])])
            print("usable now:", p.candidates())
        except LLMUnavailable as e:
            sys.exit(f"error: {e}")
        return
    if not a.query:
        ap.error("query required")
    ret = load_retriever(cfg)
    final = None
    for item in answer_stream(a.query, ret, cfg):
        if isinstance(item, Answer):
            final = item
        else:
            print(item, end="", flush=True)
    print("\n")
    if final.corrected_from:
        print(f'(showing results for "{final.query}", corrected from "{final.corrected_from}")')
    if final.status == "answered":
        print("--- resolved citations ---")
        print(resolve(final.text, final.results))
        print(f"\nmodel={final.model}  latency={final.latency_s}s  valid={final.citation.valid} "
              f"invalid={final.citation.invalid} uncited_sentences={final.citation.uncited_sentences}")
    else:
        print(f"[{final.status}] {final.reason}")
        for i, (c, s) in enumerate(final.results, 1):
            print(f"  [{i}] {s:.2f} {c['document_name']} p.{c['page_number']} | {c['section'][:50]}")


if __name__ == "__main__":
    main()
