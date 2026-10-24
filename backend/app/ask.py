"""Ask GitMore from the command line.

Usage (from the project root):
    python -m app.ask "How many weeks of parental leave do I get?"
    python -m app.ask "First question?" "Second question?" --role hr
"""

import argparse
import time

from langfuse import get_client

from app.embedding import get_model
from app.graph import ask_as
from app.retrieval.rank import get_reranker


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask GitMore a question.")
    parser.add_argument("questions", nargs="+")
    parser.add_argument("--role", default="all", help="role to ask as (permissions); default: all")
    args = parser.parse_args()

    get_model()      # load models before timing, so the times below are per question
    get_reranker()

    total_in = total_out = 0
    for question in args.questions:
        start = time.perf_counter()
        answer = ask_as(question, [args.role])
        seconds = time.perf_counter() - start
        total_in += answer.prompt_tokens
        total_out += answer.completion_tokens

        print(f"\nQ: {question}\n")
        print(answer.text)
        print("\nSources:")
        for n, chunk in enumerate(answer.sources, 1):
            mark = "*" if n in answer.cited else " "
            print(f" {mark}[{n}] {chunk.heading_path[:80]}\n       {chunk.link}")
        print(f"\n({seconds:.1f} s, {answer.prompt_tokens} + {answer.completion_tokens} tokens; * = cited)")
        print("-" * 100)

    print(f"\nTotal tokens: {total_in} in + {total_out} out for {len(args.questions)} question(s)")
    get_client().flush()  # send traces to Langfuse before exiting


if __name__ == "__main__":
    main()
