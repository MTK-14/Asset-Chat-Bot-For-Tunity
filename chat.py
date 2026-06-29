"""
chat.py
-------
Type a question, get an answer. Type 'exit' or 'quit' to stop.

This is the exact same engine you've been testing -- chatbot_tools.py
picks what to run, OpenAI just decides WHICH tool to use. The only
thing that's different from before is that YOU type the question now,
instead of it looping through a fixed test list.
"""
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from chatbot_tools import AVAILABLE_TOOLS, TOOL_SCHEMAS

load_dotenv()

client = OpenAI()
MODEL = os.environ["OPENAI_MODEL"]



SYSTEM_PROMPT = (
    "You are an assistant for a company's asset tracking and inventory "
    "system. You can ONLY help with questions about assets -- their "
    "current status, location, movement history, stock counts, cost and "
    "current value, depreciation, purchase/warranty/calibration/scrap "
    "dates, SKU, whether they're tracked as single or multiple, and who "
    "created or last edited a record -- using the tools provided. If the "
    "user asks about anything unrelated to assets or inventory, politely "
    "say that's outside what you can help with here, and do not attempt "
    "to answer it from general knowledge."
)


def ask(question: str) -> tuple[str, int]:
    # Step 1: ask the model what to do. It will pick a tool (or answer directly).
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOL_SCHEMAS,
    )

    tokens_used = response.usage.total_tokens if response.usage else 0
    message = response.choices[0].message
    tool_calls = message.tool_calls or []

    # If the model answered directly (no tool needed), return that answer.
    if not tool_calls:
        return message.content, tokens_used

    # Step 2: run each tool the model asked for, then send the results back
    # so the model can write a natural-language answer from the real data.
    messages.append(message)  # keep the assistant's tool-call in the history

    for tool_call in tool_calls:
        tool_fn = AVAILABLE_TOOLS.get(tool_call.function.name)
        if tool_fn is None:
            return f"Model asked for an unknown tool: {tool_call.function.name}", tokens_used

        args = json.loads(tool_call.function.arguments)
        print(f"  -> model chose '{tool_call.function.name}' with args {args}")

        result = tool_fn(**args)

        # Add the tool result to the conversation so the model can see it.
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result, default=str),  # default=str handles dates
        })

    # Step 3: second model call — it now reads the tool results and writes the answer.
    response2 = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOL_SCHEMAS,
    )
    tokens_used += response2.usage.total_tokens if response2.usage else 0
    return response2.choices[0].message.content, tokens_used


def main():
    print("Asset Chatbot (test mode) -- type 'exit' or 'quit' to stop.\n")
    session_total_tokens = 0
    while True:
        question = input("You: ").strip()
        if question.lower() in ("exit", "quit"):
            print(f"Bye! Total tokens this session: {session_total_tokens}")
            break
        if not question:
            continue
        answer, tokens_used = ask(question)
        session_total_tokens += tokens_used
        print(f"Bot: {answer}  [{tokens_used} tokens | {session_total_tokens} total this session]\n")


if __name__ == "__main__":
    main()