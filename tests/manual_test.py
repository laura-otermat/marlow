import os

from app.services.llm import extract_memory


examples = [
    "My kids don't wear uniforms.",
    "We use snowsuits every winter.",
    "Our wedding anniversary is June 14th.",
    "The yogurt expires Friday.",
    "Hello!"
]


def main():
    if os.getenv("RUN_LIVE_LLM_TESTS") != "1":
        raise SystemExit("Set RUN_LIVE_LLM_TESTS=1 to call the live OpenAI API.")

    for example in examples:
        print("\nINPUT:")
        print(example)

        print("\nMEMORY:")
        print(extract_memory(example))


if __name__ == "__main__":
    main()
