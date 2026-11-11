"""Stage B — Document-aware chatbot: grounding first, then RAG. (outline §3, Stage B)

Part 1 - prompt-based grounding: the WHOLE services/FAQ document goes into the
         system prompt. Works great for a short file like ours (`data/company_services.txt`).
Part 2 - RAG pipeline: load -> chunk -> embed -> retrieve -> answer with sources.
         Needed once a document grows past the "just paste it" point.

Note: embeddings need a separate model/provider — Groq does not offer one —
so this stage uses OpenAI text-embedding-3-small via OPENAI_API_KEY.

Run:  python python/stage_b_rag_chatbot.py     (type 'quit' to exit)
"""
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from common import COMPANY_DOCUMENT, get_llm, require_openai_key
from stage_a_chatbot import SYSTEM_PROMPT

# ---------- Part 1: whole-document grounding (the easy case) ----------
def grounded_answer(llm, document_text: str, question: str) -> str:
    system = (
        "You are Brightlane Home Services customer care.\n"
        "Answer ONLY using the company document below. If the answer is not in it, say so.\n\n"
        "=== COMPANY DOCUMENT ===\n"
        f"{document_text}\n=== END DOCUMENT ==="
    )
    reply = llm.invoke([SystemMessage(content=system), HumanMessage(content=question)])
    return reply.content


# ---------- Part 2: RAG (chunk -> embed -> retrieve -> answer) ----------
def build_rag_store():
    """Chunk the document and embed the chunks into an in-memory vector store."""
    text = COMPANY_DOCUMENT.read_text(encoding="utf-8")

    splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=60)
    chunks = splitter.create_documents([text])

    print(f"\n[RAG setup] document: {len(text)} chars -> {len(chunks)} chunks "
          "(chunk_size=400, overlap=60; each embedding call costs API tokens)")

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=require_openai_key())
    # Swap in local embeddings (no key, HF sentence-transformers) if you prefer offline demos.
    return InMemoryVectorStore.from_documents(chunks, embeddings)


def rag_answer(llm, store: InMemoryVectorStore, question: str) -> str:
    hits = store.similarity_search_with_score(question, k=3)
    print("\n  retrieved chunks:")  # retrieval is visible -> great teaching moment
    for i, (doc, score) in enumerate(hits, 1):
        preview = " ".join(doc.page_content.split())[:72]
        print(f"   {i}. (score {score:.2f}) {preview}...")

    context = "\n\n".join(f"[chunk {i}] {doc.page_content}" for i, (doc, _) in enumerate(hits, 1))
    system = (
        "You are Brightlane Home Services customer care.\n"
        "Answer ONLY from the retrieved chunks and cite [chunk N] markers.\n"
        "If the chunks do not contain the answer, say you are not sure.\n\n"
        f"{context}"
    )
    reply = llm.invoke([SystemMessage(content=system), HumanMessage(content=question)])
    return reply.content


def main() -> None:
    llm = get_llm()
    document_text = COMPANY_DOCUMENT.read_text(encoding="utf-8")
    store = build_rag_store()

    print("\nSame question goes to BOTH methods so you can compare (type 'quit' to exit).")
    print("Try: 'What is your reschedule policy?' or 'Do you visit Maple Street, Zone B?'\n")

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            continue
        if question.lower() in {"quit", "exit", "q"}:
            break

        print("\n--- 1) Whole-document grounding ---")
        print(f"Assistant: {grounded_answer(llm, document_text, question)}\n")
        print("--- 2) RAG (retriever + grounded answer) ---")
        print(f"Assistant: {rag_answer(llm, store, question)}\n")

    print("\n(Stage B done. Next: Stage C turns chat into validated customer intake.)")


if __name__ == "__main__":
    main()
