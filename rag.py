# rag.py
#
# The "guide" half of the chatbot: answers HOW-TO questions about using
# the TCube system, by searching the user manuals instead of the database.
#
# How this differs from chatbot_tools.py (the SQL half):
#   * chatbot_tools.py  -> answers questions about DATA  (asset status,
#                          flow history...). Data is private, so real
#                          values never go to OpenAI.
#   * rag.py (this file)-> answers questions about the SYSTEM (how do I
#                          do a stocktake? what is EPC?). The manuals are
#                          public product documentation -- nothing private
#                          -- so we can safely send slide text to OpenAI
#                          and let it phrase the answer.
#
# That is why this file is deliberately SIMPLER than the SQL side: there
# is no client data here to protect, so none of the @1/@last stub-and-
# resolve machinery is needed or wanted.
#
# The search works on MEANING, not keywords. Users ask "how do I count my
# inventory"; the manual says "Stock Taking". Those share no words, so a
# keyword search would fail. Embeddings put both phrases near each other
# in "meaning space", so the right slide is still found.

import json
import math
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

# Must be the SAME model used in build_guide_index.py. The question and
# the slides have to be embedded the same way, or comparing them is
# meaningless -- like measuring one in metres and the other in feet.
EMBEDDING_MODEL = "text-embedding-3-small"

# Model used to phrase the final answer from the retrieved slides.
ANSWER_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

INDEX_FILE = "guide_index.json"

# How many slides to hand the model per question. One task in the manual
# often spans 2-3 slides. Raised from 5 to 7 because some questions span
# TWO modules (e.g. "count my inventory" could mean the Stock Taking
# module OR checking balances in Item Management) -- with only 5 slots,
# one module's slides can crowd out the other entirely, and the model
# can't mention an alternative it never saw.
TOP_K = 7

# The rule that keeps answers honest. The model may translate jargon and
# join slides into readable steps, but every actual instruction must come
# from the retrieved slides -- never invented.
ANSWER_SYSTEM_PROMPT = (
    "You help users of TCube, an RFID inventory and asset tracking system. "
    "Answer ONLY using the manual excerpts provided in the user message. "
    "The person asking is often not familiar with the system's technical "
    "terms, so explain in plain everyday language -- but keep button names, "
    "menu names and field names EXACTLY as they appear in the excerpts, "
    "since they must match what the user sees on screen. "
    "If the excerpts describe steps, give them as a short numbered list. "
    "When the answer differs between the web system and the mobile app, say "
    "which one you are describing. "

    # --- Always tell the user WHERE to go. Half of what a confused user
    # --- needs is simply which part of the system to open.
    "Always name the module the user should go to (for example 'Stock "
    "Taking' or 'Item Management'). If the question could reasonably mean "
    "tasks in more than one module, briefly say so, cover the most likely "
    "one first, then point to the other. For example, 'how do I count my "
    "inventory' may mean performing a physical count in the Stock Taking "
    "module, or looking up current balance quantities in Item Management. "
    "Many tasks can be done on BOTH the web system and the mobile app, "
    "often through differently-named modules (for example adding an item is "
    "'Item Management' on the web but 'Registration' on the mobile app). "
    "Never say a task cannot be done on a platform unless an excerpt states "
    "that directly -- if the excerpts only cover one platform, describe that "
    "one and say the guide excerpts don't cover the other, rather than "
    "claiming it is unavailable. "

    # --- TCube has four different identifiers and they are easy to confuse.
    # --- Some ARE auto-generated and some are NOT, so blurring them
    # --- produces confidently wrong answers. Always use the name the user
    # --- actually sees on screen: "Tag ID", not the internal word "EPC".
    "TCube uses several different identifiers and they must never be "
    "confused with each other. The number encoded on the physical RFID or "
    "barcode tag attached to an item is shown in TCube as 'Tag ID' -- always "
    "call it Tag ID when talking to the user, since that is the label they "
    "see on screen. ('EPC' is the internal/technical name for the same "
    "thing; only mention that word if the user uses it first.) Asset No and "
    "Display ID are separate internal reference codes, not the same as Tag "
    "ID. If an excerpt says something about one identifier, never assume the "
    "same is true of the others, and never state how an identifier is "
    "created unless an excerpt says so directly. "

    # --- The anti-invention rule, stated last so it lands hardest.
    "Being wrong is worse than being incomplete. If the excerpts do not "
    "clearly state something, say the user guide does not specify it. "
    "Never fill a gap with what seems technically plausible, and never "
    "guess at steps, menus or buttons. "
    "If the question is not about TCube or inventory/asset tracking at all, "
    "simply say it is outside what you can help with -- do NOT suggest "
    "searching the TCube manual for unrelated topics."
)

# Loaded once, the first time a search happens, then kept in memory.
_INDEX_CACHE = None


def _load_index() -> list[dict]:
    """Read guide_index.json from disk (once) and keep it in memory."""
    global _INDEX_CACHE
    if _INDEX_CACHE is None:
        if not os.path.exists(INDEX_FILE):
            raise FileNotFoundError(
                f"{INDEX_FILE} not found. Run build_guide_index.py first."
            )
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            _INDEX_CACHE = json.load(f)
    return _INDEX_CACHE


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """How similar are two embeddings? Returns roughly 0.0 (unrelated) to
    1.0 (near-identical meaning).

    This is 'cosine similarity': it compares the DIRECTION the two lists of
    numbers point in, ignoring their size. Pointing the same way = same
    meaning. Written in plain Python (no numpy needed) -- with only a few
    hundred chunks this is instant."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embed_question(question: str) -> list[float]:
    """Turn the user's question into an embedding, the same way the slides
    were turned into embeddings during indexing."""
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=question)
    return response.data[0].embedding


def retrieve(question: str, platform: str = "both", top_k: int = TOP_K) -> list[dict]:
    """Find the slides whose MEANING is closest to the question.

    platform: "web", "mobile", or "both".
      - "both" is the safe default: some tasks exist on both systems, and
        a user often doesn't know which one their task belongs to.
      - Later, when this becomes a tool the model calls, the model can set
        this itself (e.g. "on the scanner" -> "mobile") with no code change.

    Returns the top matching chunks, each with a 'score' added.
    """
    index = _load_index()

    if platform in ("web", "mobile"):
        candidates = [c for c in index if c["source"] == platform]
    else:
        candidates = index

    question_embedding = _embed_question(question)

    scored = []
    for chunk in candidates:
        score = _cosine_similarity(question_embedding, chunk["embedding"])
        scored.append({
            "source": chunk["source"],
            "slide": chunk["slide"],
            "text": chunk["text"],
            "score": score,
        })

    # Highest similarity first, then keep only the best few.
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:top_k]


def search_user_guide(question: str, platform: str = "both") -> str:
    """Full guide answer: retrieve the closest slides, then have the model
    phrase a grounded answer from ONLY those slides.

    This is the function that will later be registered as the chatbot's
    7th tool. It returns finished answer text."""
    matches = retrieve(question, platform=platform)

    if not matches:
        return "I couldn't find anything about that in the user guide."

    # Build the excerpt block the model is allowed to answer from. Each
    # excerpt is labelled so the model can say "in the mobile app..." and
    # so we could cite slide numbers to the user.
    excerpts = []
    for m in matches:
        if m["source"] == "web":
            label = f"Web system, slide {m['slide']}"
        elif m["source"] == "mobile":
            label = f"Mobile app, slide {m['slide']}"
        else:  # "note" -- hand-written knowledge, not from a manual slide
            label = "Internal note"
        excerpts.append(f"[{label}]\n{m['text']}")
    excerpt_block = "\n\n---\n\n".join(excerpts)

    user_message = (
        f"User's question: {question}\n\n"
        f"Manual excerpts:\n\n{excerpt_block}"
    )

    response = client.chat.completions.create(
        model=ANSWER_MODEL,
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------
# Standalone test mode: run `python rag.py` to try the guide search on its
# own, BEFORE wiring it into the main chatbot. Shows which slides were
# retrieved and how well they matched, so you can judge retrieval quality
# separately from answer quality.
# ---------------------------------------------------------------------
def main():
    print("Guide search test -- type 'exit' to quit.")
    print("(searching BOTH web and mobile manuals)\n")
    while True:
        question = input("Question: ").strip()
        if question.lower() in ("exit", "quit"):
            break
        if not question:
            continue

        matches = retrieve(question)
        print("\n  --- retrieved slides ---")
        for m in matches:
            preview = m["text"].replace("\n", " ")
            if len(preview) > 90:
                preview = preview[:90] + "..."
            print(f"  [{m['score']:.3f}] {m['source']:6} slide {m['slide']:>3} | {preview}")

        answer = search_user_guide(question)
        print("\n  --- answer ---")
        print(f"  {answer}\n")


if __name__ == "__main__":
    main()