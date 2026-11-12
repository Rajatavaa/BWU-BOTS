"""Stage A — General chatbot. (outline §3, Stage A)

What this stage demonstrates:
- API authentication without leaking secrets (keys live in .env, never printed)
- a request = system + user messages; a response = a message object
- temperature: creativity knob (try 0.2 vs 1.5 — see answer stability)
- the model has NO knowledge of our university: it will guess answers!

Run:  python python/stage_a_chatbot.py     (type 'quit' to exit)
"""
import os
import sys

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=False))

SYSTEM_PROMPT = (
    "You are a friendly assistant in a live workshop demo. Keep answers short "
    "(max 3 sentences) so the presenter can read them aloud. "
    "Reply in plain text: no Markdown, tables, ** or # symbols."
)


def main() -> None:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        sys.exit(
            "\n[setup] GROQ_API_KEY is not set.\n"
            "  1. cp .env.example .env\n"
            "  2. Paste your key from https://console.groq.com/keys\n"
        )
    model_id = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
    # ChatGroq reads GROQ_API_KEY from the env by default; passing it explicitly
    # shows exactly where the credential is consumed (without printing it).
    llm = ChatGroq(model=model_id, api_key=api_key, temperature=0.2)

    print(f"Model : {model_id}\nTemp  : 0.2   (change it above and re-run)\nKey loaded: yes (hidden)")
    print("Try: 'What programmes does Brainware University offer?'  -> it will invent answers: no university data yet!\n")

    history: list = [SystemMessage(content=SYSTEM_PROMPT)]  # memory lives in this list (Stage C explains)
    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user:
            continue
        if user.lower() in {"quit", "exit", "q"}:
            break

        history.append(HumanMessage(content=user))
        try:
            reply = llm.invoke(history)  # one HTTP round-trip: chat completion
        except Exception as exc:  # demo-friendly: auth errors, quota, network...
            print(f"  API error: {exc}\n  (Check your key and quota - Stage F covers debugging.)")
            history.pop()  # don't keep the failed turn in memory
            continue

        history.append(reply)
        print(f"Assistant: {reply.content}\n")

    print("\n(Stage A done: a general chatbot with no company facts. Next: Stage B grounds it in a document.)")


if __name__ == "__main__":
    main()
