"""
test_tool_calling.py
---------------------
Runs a fixed list of test questions to verify all tools work correctly.
"""
import json
import os
from datetime import date

from dotenv import load_dotenv
from openai import OpenAI

from chatbot_tools import AVAILABLE_TOOLS, TOOL_SCHEMAS

load_dotenv()

client = OpenAI()
MODEL = os.environ["OPENAI_MODEL"]

# Tell the model to ONLY use tools -- never answer from general knowledge.
# Today's date is included so the model can handle "today" questions correctly.
SYSTEM_PROMPT = (
    f"You are an assistant for a company's asset tracking system. "
    f"Today's date is {date.today()}. "
    "Answer ONLY by using the provided tools. "
    "If the user's question cannot be answered with the available tools, say: "
    "'I can only help with questions about asset status, location, movement history, and stock counts.' "
    "Never make up data or answer from general knowledge."
)

TEST_QUESTIONS = [
    # Tool 1: look up one asset -- by EPC, asset number, or item name
    "Where is tag e2003411fe0e1001 right now?",
    "What's the status of EPC E2003411FE0E1004?",
    "Where is the Dell Laptop?",           # search by description (new)
    "What's the status of Toyota Forklift?",  # search by description (new)

    # Tool 2: movement history for one asset
    "Show me the movement history for AST-001",
    "What happened to AST-001 between 2026-05-02 and 2026-05-10?",
    "Show me the history for the Pallet Jack",  # search by name (new)

    # Tool 3: count assets by group
    "How many assets are currently checked out?",
    "How many IT equipment items do we have available?",

    # Tool 4: list assets by status (new)
    "Which items are checked out right now?",
    "Which assets are available?",

    # Tool 5: transactions by date (new)
    "What transactions happened on 2026-05-01?",
    "Show all movements between 2026-05-01 and 2026-05-10",

    # Edge cases
    "Tell me about asset number AST-099",   # doesn't exist
    "What is the capital of France?",        # completely unrelated -- should refuse
]


def format_answer(tool_name: str, result) -> str:
    """Turn a raw database result into a readable sentence."""

    if tool_name == "get_asset_by_identifier":
        if result is None:
            return "I couldn't find an asset matching that identifier."
        return (
            f"{result['Description']} ({result['Asset_No']}) is currently "
            f"'{result['Status']}' at {result['Location']}, assigned to {result['PIC']}."
        )

    if tool_name == "get_flow_history":
        if result is None:
            return "I couldn't find an asset matching that identifier."
        if not result:
            return "That asset exists, but has no movement history in that range."
        lines = [
            f"  {row['Date']}: {'IN' if row['Qty_In'] else 'OUT'} "
            f"by {row['Person_In_Charge']} ({row['Remarks']})"
            for row in result
        ]
        return "Movement history:\n" + "\n".join(lines)

    if tool_name == "get_stock_balance":
        if not result:
            return "No assets matched that filter."
        parts = [f"{row['Count']} {row['Status']}" for row in result]
        return "Current breakdown: " + ", ".join(parts) + "."

    if tool_name == "get_assets_by_status":
        if not result:
            return "No assets found with that status."
        lines = [
            f"  - {row['Description']} ({row['Asset_No']}) at {row['Location']}, assigned to {row['PIC']}"
            for row in result
        ]
        return f"{len(result)} asset(s) are '{result[0]['Status']}':\n" + "\n".join(lines)

    if tool_name == "get_transactions_by_date":
        if not result:
            return "No transactions found for that date range."
        lines = [
            f"  - {row['Date']} | {row['Asset_No']} {row['Description']}: "
            f"{'IN' if row['Qty_In'] else 'OUT'} by {row['Person_In_Charge']} ({row['Remarks']})"
            for row in result
        ]
        return f"{len(result)} transaction(s) found:\n" + "\n".join(lines)

    return "I don't know how to format that result yet."


def ask(question: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        tools=TOOL_SCHEMAS,
    )

    message = response.choices[0].message
    tool_calls = message.tool_calls or []

    for tool_call in tool_calls:
        tool_fn = AVAILABLE_TOOLS.get(tool_call.function.name)
        if tool_fn is None:
            return f"Model asked for an unknown tool: {tool_call.function.name}"

        args = json.loads(tool_call.function.arguments)
        print(f"  -> model chose '{tool_call.function.name}' with args {args}")

        result = tool_fn(**args)
        return format_answer(tool_call.function.name, result)

    # No tool used -- the system prompt tells the model to say it can't help
    return message.content


def main():
    for question in TEST_QUESTIONS:
        print(f"\nQ: {question}")
        print("A:", ask(question))


if __name__ == "__main__":
    main()
