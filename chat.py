import calendar
import json
import os
import re
from datetime import date, timedelta

from dotenv import load_dotenv
from openai import OpenAI

from chatbot_tools import AVAILABLE_TOOLS, TOOL_SCHEMAS
from session import Session

load_dotenv()

client = OpenAI()
MODEL = os.environ["OPENAI_MODEL"]

DISPLAY_LIMIT = 10

SYSTEM_PROMPT = (
    "You are an assistant for a company's asset tracking and inventory "
    "system. You can ONLY help with questions about assets -- their "
    "current status, location, category, minor/sub-category, movement "
    "history, stock counts and last balance, cost and current value, "
    "depreciation, purchase/warranty/calibration/scrap/expiry dates, "
    "SKU, remarks/notes, vendor/supplier, useful life, unit of measure, "
    "reference number, batch number, whether they're tracked as single "
    "or multiple, who created or last edited a record, which assets have "
    "the most or least stock balance, which assets have the most "
    "movement history, assets filtered by balance thresholds (under/over "
    "a number), and assets filtered by status (available, not available, "
    "on loan, in-transit, discarded) -- using the tools provided. "
    "If the user asks "
    "about anything unrelated to assets or inventory, politely say that's "
    "outside what you can help with here, and do not attempt to answer it "
    "from general knowledge. If the user asks for information about an "
    "asset but hasn't given an identifier (EPC, Tag ID, Asset No, Display "
    "ID) or a description of what it is, ask them which asset they mean "
    "instead of guessing or calling a tool with a made-up value. "
    "IMPORTANT -- you are never told the real EPC/Asset No/Display ID of "
    "any asset found in an earlier turn; earlier turns only show you a "
    "count and reference tags like '@1', '@2'. So if the user refers back "
    "to an asset already discussed using words like 'that', 'it', 'the "
    "same one', or 'the second one you listed', you must pass the literal "
    "reference '@last' (the most recently discussed asset) or '@1', '@2', "
    "etc. (the Nth asset from the last list) as the identifier argument. "
    "Do NOT construct, guess, or reuse an asset code from your own memory "
    "of typical codes -- if you don't have a real code the user typed "
    "themselves THIS conversation, the only safe values are '@last' or "
    "'@1'/'@2'/etc. "
    "HOWEVER, if the user's CURRENT message itself names or describes an "
    "asset -- a code like 'AST-001', or a plain description like 'the Dell "
    "laptop' or 'the Toyota forklift' -- you MUST pass that exact text as "
    "the identifier this turn. Never substitute '@last' or '@1'/'@2'/etc. "
    "in place of a code or description the user just typed, even if it "
    "looks the same as or similar to something discussed earlier in the "
    "conversation. '@last'/'@N' are ONLY for pronouns and positional "
    "references ('it', 'that', 'the same one', 'the second one') -- never "
    "for a fresh mention of an asset by name or code. "
    "When the user names or describes an asset in plain words (not a code) "
    "and asks about any of its fields -- cost, current value, depreciation, "
    "balance, warranty, or anything else -- call search_assets_by_description "
    "immediately using that description; do not ask the user for an "
    "identifier first. Only ask for clarification when the user's message "
    "gives NO code and NO description at all. "
    "A single call to get_asset_by_identifier or search_assets_by_description "
    "already returns EVERY field for that asset, so a question about several "
    "attributes of ONE asset (e.g. 'location and cost', 'cost and current "
    "value') needs only ONE call -- never call the same tool twice for the "
    "same asset in the same turn. Only make a second, DIFFERENT tool call in "
    "the same turn when the question needs a fundamentally different kind of "
    "lookup (e.g. current details AND movement history together, or two "
    "different assets) -- do not answer only part of a question like that. "
    "Some earlier assistant turns in this conversation look like short "
    "internal notes (e.g. starting with '(internal note'); those are "
    "bookkeeping only, never an example of how to reply. Always answer the "
    "user in plain natural language sentences, never as JSON or as a raw "
    "internal note, and always call the appropriate tool yourself for the "
    "CURRENT question rather than reusing a count or answer from an earlier "
    "turn."
)


_CURRENT_VALUE_ONLY_RE = re.compile(r"\btotal cost\b|\bcurrent price\b|\bcurrent cost\b")


def _wants_cost(q: str) -> bool:
    """'cost', 'price', 'unit cost' -> the Cost column. Phrases that mean
    the Current_Value column instead ('total cost', 'current price',
    'current cost') are stripped out first so they don't also trip the bare
    'cost'/'price' substring match here."""
    stripped = _CURRENT_VALUE_ONLY_RE.sub(" ", q)
    return any(k in stripped for k in ("unit cost", "cost per unit", "cost", "price"))


def _wants_current_value(q: str) -> bool:
    """'current value', 'value', 'worth' -> Current_Value, as do the
    cost-shaped phrases ('total cost', 'current price', 'current cost')
    that actually mean the asset's current value, not its original Cost."""
    return bool(_CURRENT_VALUE_ONLY_RE.search(q)) or any(k in q for k in ("current value", "value", "worth"))


_UOM_KEYWORDS = ("uom", "unit of measure", "unit of measurement", "units of measure")
_COST_UNIT_PHRASE_RE = re.compile(
    r"\bunit\s+cost\b|\bcost\s+per\s+unit\b|\bper\s+unit\s+cost\b|"
    r"\bunit\s+price\b|\bprice\s+per\s+unit\b|\bper\s+unit\s+price\b"
)


def _wants_uom(q: str) -> bool:
    """'uom'/'unit of measure' always mean the UOM field. A bare 'unit'
    (e.g. 'what unit is this in?') counts too -- but NOT when it's part of
    a cost/price phrase like 'unit cost' or 'price per unit', which is
    asking about Cost, not the unit of measure, despite sharing the word
    'unit'."""
    if any(k in q for k in _UOM_KEYWORDS):
        return True
    stripped = _COST_UNIT_PHRASE_RE.sub(" ", q)
    return "unit" in stripped


def _shared_field_groups(result: dict) -> list:
    return [
        (["epc", "tag id", "rfid", "tag number", "epc id", "epc number"],
         "EPC / Tag ID", result.get("EPC_ID")),
        (["display id", "display_id", "display number"],
         "Display ID", result.get("Display_ID")),
        (["category", "type of asset", "asset type", "it equipment", "machinery",
          "furniture", "safety equipment", "tools"], "Category", result.get("Category")),
        (_wants_cost, "Cost", result.get("Cost")),
        (_wants_current_value, "Current value", result.get("Current_Value")),
        (["depreciat"], "Depreciation", _depreciation_text(result)),
        (["warranty"], "Warranty expiry", result.get("Warranty_Expiry_Date")),
        (["purchase", "bought", "acquired"], "Date of purchase", result.get("Date_of_Purchase")),
        (["sku"], "SKU", result.get("SKU")),
        (["last balance", "lastbal", "remaining", "stock level", "balance"],
         "Last balance", result.get("LastBal")),
        (["remark", "note", "comment"], "Remarks", result.get("Remarks")),
        (["expire", "expiry", "expiration", "date of expire", "expiry date"],
         "Expiry date", result.get("Date_of_Expire")),
        (["minor category", "subcategory", "sub-category", "sub category", "minor cat"],
         "Minor category", result.get("Minor_Category")),
    ]


def _depreciation_text(result: dict) -> str | None:
    yearly, final = result.get("Yearly_Depreciation"), result.get("Final_Depreciation")
    if yearly is None and final is None:
        return None
    return f"yearly {yearly if yearly is not None else 'not recorded'}, final {final if final is not None else 'not recorded'}"


def _created_by_text(result: dict) -> str | None:
    if result.get("Creator") is None:
        return None
    return f"{result.get('Creator')} on {result.get('Creation_Time')}"


def _render_matched_groups(groups: list, q: str, want_all: bool) -> list[str]:
    """Format the field groups whose keywords appear in the question (or
    every group if want_all), skipping fields the record has no data for --
    in a want_all dump those would just be clutter; for an explicitly-asked
    field we still answer, just with a friendly "not recorded" instead of a
    raw None.
    """
    out = []
    for keywords, label, value in groups:
        explicit = keywords(q) if callable(keywords) else any(k in q for k in keywords)
        if not (want_all or explicit):
            continue
        if value is None:
            if want_all:
                continue
            value = "not recorded"
        out.append(f"{label}: {value}")
    return out


def _matched_extras(result: dict, q: str, want_all: bool) -> list[str]:
    return _render_matched_groups(_shared_field_groups(result), q, want_all)


def _single_only_groups(result: dict) -> list:
    """Field groups that only make sense for a single looked-up asset (as
    opposed to _shared_field_groups, which also apply to rows in a list)."""
    return [
        (["where", "location"], "Location", result.get("Location")),
        (["status", "available", "on loan", "in-transit", "in transit",
          "discarded", "scrapped", "not available"], "Status", result.get("Status")),
        (["who has", "who is holding", "assigned to", "in charge", "pic"],
         "Person in charge", result.get("PIC")),
        (["calibrat"], "Calibration date", result.get("Calibration_Date")),
        (["scrap"], "Date of scrap", result.get("Date_of_Scrap")),
        (["single", "multiple", "bulk", "individual", "serialized"],
         "Tracking type", result.get("TrackingType")),
        (["who created", "who added", "who made", "who registered", "creator"],
         "Created by", _created_by_text(result)),
        (["who edited", "who updated", "who modified", "last edited",
          "last changed", "edited", "updated", "modified"],
         "Last edited", result.get("Edit_Time")),
        (["vendor", "supplier", "vendor name", "supplier name"],
         "Vendor", result.get("Vendor_Name")),
        (["useful life", "lifespan", "life span", "service life"],
         "Useful life (years)", result.get("Useful_Life")),
        (_wants_uom, "Unit of measure", result.get("UOM")),
        (["ref no", "ref number", "reference number", "reference no"],
         "Ref No", result.get("Ref_No")),
        (["batch", "batch no", "batch number"],
         "Batch No", result.get("BatchNo")),
    ]


def _all_asset_field_matches(result: dict, q: str, want_all: bool) -> list[str]:
    """Every field (single-asset-only + shared) whose keywords appear in the
    question, or every field if want_all. Shared by get_asset_by_identifier,
    search_assets_by_description, and get_flow_history so all three produce
    IDENTICAL wording for the same asset regardless of how it was looked up
    -- a combined question ('what's the location of X and its movement
    history?') also gets both parts answered regardless of which tool the
    model routed it to."""
    return _render_matched_groups(_single_only_groups(result) + _shared_field_groups(result), q, want_all)


_MONTH_LOOKUP = {}
for _i, _name in enumerate(calendar.month_name):
    if _name:
        _MONTH_LOOKUP[_name.lower()] = _i
for _i, _abbr in enumerate(calendar.month_abbr):
    if _abbr:
        _MONTH_LOOKUP[_abbr.lower()] = _i

_DAY_MONTH_RE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-zA-Z]+)(?:\s+(\d{4}))?\b")
_MONTH_DAY_RE = re.compile(r"\b([a-zA-Z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?(?:\s+(\d{4}))?\b")
_MONTH_ONLY_RE = re.compile(r"\b(?:in|during)\s+([a-zA-Z]+)(?:\s+(\d{4}))?\b")


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _infer_date_range(question: str, today: date) -> tuple[str, str] | None:
    """Resolve relative date language in the raw question ('yesterday', 'on
    10 May', 'in May', 'last week', 'lately', ...) into a concrete
    date_from/date_to pair, using the REAL current date on our side.

    The model has no reliable notion of "today" and tends to guess wildly
    (e.g. the wrong year) when asked to compute a relative date itself, the
    same way it can't be trusted with real asset codes. So this runs
    locally, exactly like Session.resolve() does for '@last'/'@1' -- the
    model just needs to recognize a date is being talked about; the actual
    arithmetic happens here.

    Returns None when nothing relative is recognized in the question, so
    callers fall back to whatever explicit date the model/user supplied.
    """
    q = question.lower()

    if "yesterday" in q:
        d = today - timedelta(days=1)
        return d.isoformat(), d.isoformat()
    if re.search(r"\btoday\b", q):
        return today.isoformat(), today.isoformat()

    for m in _DAY_MONTH_RE.finditer(q):
        day, month_name, year_str = m.groups()
        month = _MONTH_LOOKUP.get(month_name.lower())
        if month:
            year = int(year_str) if year_str else today.year
            try:
                d = date(year, month, int(day))
            except ValueError:
                continue
            return d.isoformat(), d.isoformat()

    for m in _MONTH_DAY_RE.finditer(q):
        month_name, day, year_str = m.groups()
        month = _MONTH_LOOKUP.get(month_name.lower())
        if month:
            year = int(year_str) if year_str else today.year
            try:
                d = date(year, month, int(day))
            except ValueError:
                continue
            return d.isoformat(), d.isoformat()

    for m in _MONTH_ONLY_RE.finditer(q):
        month = _MONTH_LOOKUP.get(m.group(1).lower())
        if month:
            year = int(m.group(2)) if m.group(2) else today.year
            start, end = _month_bounds(year, month)
            return start.isoformat(), end.isoformat()

    if "this week" in q:
        start = today - timedelta(days=today.weekday())
        return start.isoformat(), today.isoformat()
    if "last week" in q:
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return start.isoformat(), end.isoformat()
    if "this month" in q:
        start, _ = _month_bounds(today.year, today.month)
        return start.isoformat(), today.isoformat()
    if "last month" in q:
        year, month = today.year, today.month - 1
        if month == 0:
            year, month = year - 1, 12
        start, end = _month_bounds(year, month)
        return start.isoformat(), end.isoformat()
    if "lately" in q or "recently" in q:
        return (today - timedelta(days=30)).isoformat(), today.isoformat()

    return None


def _format_row_list(result: list[dict], noun: str, question: str) -> str:
    if not result:
        return f"No {noun}s found matching that filter."

    q = question.lower()
    want_all = any(k in q for k in ("everything", "all details", "full details", "all info"))

    total = len(result)
    shown = result[:DISPLAY_LIMIT]

    lines = []
    for row in shown:
        base = (
            f"  {row.get('Asset_No')}: {row.get('Description')} -- "
            f"{row.get('Status')} at {row.get('Location')} (PIC: {row.get('PIC')})"
        )
        extras = _matched_extras(row, q, want_all)
        if extras:
            base += " | " + " | ".join(extras)
        lines.append(base)

    header = f"Found {total} {noun}(s)"
    if total > DISPLAY_LIMIT:
        header += (
            f", showing the first {DISPLAY_LIMIT}. "
            f"Check the Item Management Module to see the full list."
        )

    return header + ":\n" + "\n".join(lines)


def format_answer(tool_name: str, result, question: str) -> str:
    q = question.lower()

    if tool_name == "get_asset_by_identifier":
        if result is None:
            return "I couldn't find an asset matching that identifier."

        want_all = any(k in q for k in ("everything", "all details", "full details", "all info"))
        matched = [f"{m}." for m in _all_asset_field_matches(result, q, want_all)]

        header = f"{result.get('Description')} ({result.get('Asset_No')})"

        if matched:
            return f"{header} -- " + " ".join(matched)

        # Nothing specific detected -- short general summary, NOT a full dump.
        # Full info only comes from an EXPLICIT "everything/all details/full
        # info" phrase (handled above via want_all), so a plain "tell me
        # about X" stays concise, while "tell me ALL INFORMATION about X"
        # still correctly triggers the full breakdown.
        return (
            f"{header} is currently '{result.get('Status')}' at {result.get('Location')}, "
            f"person in charge: {result.get('PIC')}."
        )

    if tool_name == "get_flow_history":
        if result is None:
            return "I couldn't find an asset matching that identifier."
        asset = result.get("asset")
        rows = result.get("history", [])
        if not rows:
            return "That asset exists, but has no movement history in that range."

        def _format_flow_row(row: dict) -> str:
            qty_in = row.get("Qty_In") or 0
            qty_out = row.get("Qty_Out") or 0
            direction = f"Check In (+{qty_in})" if qty_in > 0 else f"Check Out (-{qty_out})"
            location = row.get("Flow_Location") or "—"
            parts = [
                f"{row.get('Date')}: {direction}",
                f"by {row.get('Person_In_Charge')}",
                f"at {location}",
                f"balance: {row.get('Balance')}",
                f"doc: {row.get('Doc_No')}",
            ]
            if row.get("Remarks"):
                parts.append(f"({row.get('Remarks')})")
            return " | ".join(parts)

        answer_parts = []
        # Combined questions ("who created X and what's its history?", "what's
        # the location of X and its movement history?") also want fields off
        # the asset record itself, not just the history rows.
        want_all = any(k in q for k in ("everything", "all details", "full details", "all info"))
        if asset:
            answer_parts += [f"{m}." for m in _all_asset_field_matches(asset, q, want_all)]

        if any(k in q for k in ("latest", "most recent", "last checkout",
                                 "last check-out", "last check out", "last check-in",
                                 "last check in")):
            # Rows are ordered ascending by date, so the last one is most recent.
            answer_parts.append(f"Most recent movement -- {_format_flow_row(rows[-1])}")
            return " ".join(answer_parts)

        total_rows = len(rows)
        shown_rows = rows[:DISPLAY_LIMIT]
        lines = [_format_flow_row(row) for row in shown_rows]
        history_header = f"Movement history ({total_rows} records"
        if total_rows > DISPLAY_LIMIT:
            history_header += (
                f", showing first {DISPLAY_LIMIT}. "
                f"Check the Item Management Module to see the full history"
            )
        history_header += "):"
        answer_parts.append(history_header + "\n" + "\n".join(lines))
        return " ".join(answer_parts)

    if tool_name == "get_stock_balance":
        if not result:
            return "No assets matched that filter."
        total = sum(row.get("Count", 0) for row in result)
        parts = [f"{row.get('Count')} {row.get('Status')}" for row in result]
        return f"Total: {total}. Breakdown: " + ", ".join(parts) + "."

    if tool_name == "list_assets":
        # "What categories does X have?" -- extract distinct categories from the result
        # instead of listing every individual asset.
        if "categor" in q and not result:
            return "No assets found matching that filter."
        if "categor" in q and result:
            categories = sorted(set(row.get("Category") for row in result if row.get("Category")))
            return "Categories found: " + ", ".join(categories) + "."
        return _format_row_list(result, noun="asset", question=question)

    if tool_name == "search_assets_by_description":
        # "How many X?" -- the user wants a count, not details.
        if "how many" in q:
            count = len(result)
            if count == 0:
                return "There are no matching assets in the system."
            if count == 1:
                row = result[0]
                return (
                    f"There is 1 {row.get('Description')} in the system "
                    f"({row.get('Asset_No')}, currently '{row.get('Status')}' "
                    f"at {row.get('Location')})."
                )
            # Multiple: "Found N matching assets" already gives the count + list.
            return _format_row_list(result, noun="matching asset", question=question)

        if len(result) == 1:
            # Exactly one match -- use the exact same field-matching helper as
            # get_asset_by_identifier so the answer is IDENTICAL whether the
            # user gave a code or a plain description (previously this used a
            # narrower field set that silently dropped things like Location).
            row = result[0]
            want_all = any(k in q for k in ("everything", "all details", "full details", "all info"))
            matched = [f"{m}." for m in _all_asset_field_matches(row, q, want_all)]
            header = f"{row.get('Description')} ({row.get('Asset_No')})"
            if matched:
                return f"{header} -- " + " ".join(matched)
            return (
                f"{header} is currently '{row.get('Status')}' at {row.get('Location')}, "
                f"person in charge: {row.get('PIC')}."
            )
        # Multiple (or zero) matches -- keep the list format.
        return _format_row_list(result, noun="matching asset", question=question)

    if tool_name == "get_asset_ranking":
        if not result:
            return "No assets found matching that filter."
        is_movement = "Move_Count" in result[0]
        lines = []
        for i, row in enumerate(result):
            if is_movement:
                detail = f"movements: {row.get('Move_Count')}"
            else:
                detail = f"balance: {row.get('LastBal')}"
            lines.append(
                f"  {i + 1}. {row.get('Asset_No')} -- {row.get('Description')} "
                f"| {detail} | {row.get('Status')} at {row.get('Location')} "
                f"(PIC: {row.get('PIC')})"
            )
        label = "movement activity" if is_movement else "stock balance"
        return f"Top {len(result)} assets by {label}:\n" + "\n".join(lines)

    return "I don't know how to format that result yet."


def _extract_identifiers(tool_name: str, result) -> list[str]:
    """Pull the real Asset_No values a tool result touched, in the same
    order they were shown to the user. Session uses this list so "@1",
    "@2", ... "@last" can later stand in for these real codes. This list
    itself is only ever used locally -- it is never sent to OpenAI.
    """
    if not result:
        return []

    if tool_name == "get_asset_by_identifier":
        asset_no = result.get("Asset_No")
        return [asset_no] if asset_no else []

    if tool_name == "get_flow_history":
        asset = result.get("asset")
        asset_no = asset.get("Asset_No") if asset else None
        return [asset_no] if asset_no else []

    if tool_name in ("list_assets", "search_assets_by_description", "get_asset_ranking"):
        # Only remember what was actually shown (format_answer truncates to
        # DISPLAY_LIMIT rows), so "@2" means the second one the user saw.
        shown = result[:DISPLAY_LIMIT]
        return [row.get("Asset_No") for row in shown if row.get("Asset_No")]

    return []  # get_stock_balance has no individual assets to remember


def _build_stub(tool_name: str, result, refs: list[str]) -> str:
    """Build the SAFE, no-real-data summary of a tool result that we are
    allowed to hand back to OpenAI as conversation history. Real EPCs/Asset
    Nos never appear here -- just a count and a list of "@1"/"@2" tags.

    This is deliberately plain prose, NOT JSON -- earlier versions stored a
    raw {"tool": ..., "found": ..., "refs": [...]} dict here, and the model
    would sometimes pattern-match that shape and parrot a similar-looking
    JSON blob back as its own final answer (skipping the tool call
    entirely) instead of treating it as internal bookkeeping.
    """
    if tool_name in ("get_asset_by_identifier", "get_flow_history"):
        found = 1 if result else 0
    elif isinstance(result, list):
        found = len(result)
    else:
        found = 0
    ref_text = ", ".join(refs) if refs else "none"
    return (
        f"(internal note, not a reply to show the user) A previous "
        f"{tool_name} lookup this turn found {found} result(s). Reference "
        f"tags available for follow-ups: {ref_text}."
    )


_TRAILING_ASSET_RE = re.compile(
    r"\b(?:of|for|about|regarding)\s+(?:one\s+|a\s+|an\s+|the\s+)?"
    r"([a-z0-9][a-z0-9 \-']*?)\s*\??$",
    re.IGNORECASE,
)
_BARE_PRONOUN_PHRASES = {
    "it", "that", "this", "this one", "that one", "the same one", "the same",
    "same", "same one", "them", "those", "the first one", "the second one",
    "the third one", "the last one", "the other one", "one",
}


def _extract_named_asset(question: str) -> str | None:
    """Pull out the asset name/code the CURRENT question is actually about,
    when it's named in plain text after a trailing preposition -- 'the cost
    of X', 'the price for X', 'what about X' -- as opposed to a pronoun-style
    follow-up about the asset already discussed ('of it', 'for the same
    one').

    The model is unreliable here: even when the question plainly names a
    DIFFERENT asset than the one just discussed, it often still resolves the
    identifier to '@last'/'@1' (the previous asset) instead of the literal
    text the user just typed. Rather than trust that judgment call, this
    scans the raw question directly -- same reasoning as _infer_date_range
    resolving relative dates locally instead of trusting the model's date
    math. Only the LAST such phrase in the sentence is used, since that's
    where the asset name sits in every phrasing this handles.
    """
    matches = list(_TRAILING_ASSET_RE.finditer(question.strip()))
    if not matches:
        return None
    phrase = matches[-1].group(1).strip()
    if not phrase or phrase.lower() in _BARE_PRONOUN_PHRASES:
        return None
    return phrase


def _looks_like_code(phrase: str) -> bool:
    """True for short asset codes ('AST-001', 'A-0011') -- no spaces, and
    at least one digit. Plain descriptions ('dell laptop', 'office chair')
    always contain a space, so this cleanly tells the two apart."""
    p = phrase.strip()
    return " " not in p and any(c.isdigit() for c in p)


_HISTORY_KEYWORDS = (
    "history", "movement", "moved", "check in", "check-in", "checked in",
    "check out", "check-out", "checked out", "flow history",
    "yesterday", "today", "last week", "this week", "last month",
    "this month", "lately", "recently", "latest", "most recent",
)


def _wants_history(q: str) -> bool:
    return any(k in q for k in _HISTORY_KEYWORDS)


def ask(question: str, session: Session | None = None) -> tuple[str, int]:
    if session is None:
        session = Session()  # no memory requested -- behaves like a one-off question

    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + session.messages_for_openai()
        + [{"role": "user", "content": question}]
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOL_SCHEMAS,
    )

    tokens_used = response.usage.total_tokens if response.usage else 0
    message = response.choices[0].message
    tool_calls = message.tool_calls or []

    if not tool_calls:
        # No lookup happened, so the model's own reply is already safe to
        # store as-is -- it can't contain any real data we didn't already
        # send it this turn.
        session.add_turn(question, message.content or "")
        return message.content, tokens_used

    q = question.lower()
    overrode_identifier = False  # true once we've caught the model backreferencing the WRONG asset this turn

    answers = []
    stubs = []  # safe-for-OpenAI summaries, one per tool call this turn
    seen_calls = set()  # (tool_name, resolved args) signatures already answered this turn
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)
        raw_identifier = args.get("identifier")  # kept only for the debug print below

        if isinstance(raw_identifier, str) and raw_identifier.strip().lower().startswith("@"):
            # The model resolved this to a backward reference ('@last'/'@N'),
            # meaning it thinks this is a pronoun-style follow-up about the
            # asset already discussed. But if the CURRENT question plainly
            # names an asset in its own text, that reference is very likely
            # wrong -- pick the right tool for what was actually typed
            # instead of trusting the model's resolution.
            fresh = _extract_named_asset(question)
            if fresh is not None:
                if _looks_like_code(fresh):
                    tool_name, args = "get_asset_by_identifier", {"identifier": fresh}
                elif _wants_history(q):
                    tool_name, args = "get_flow_history", {"identifier": fresh}
                else:
                    tool_name, args = "search_assets_by_description", {"keyword": fresh}
                overrode_identifier = True
                print(f"  -> question names '{fresh}' -- overriding bad backref '{raw_identifier}' with '{tool_name}' {args}")

        if tool_name == "get_stock_balance" and overrode_identifier and not any(k in q for k in ("how many", "count of", "number of")):
            # A bare get_stock_balance() call alongside a single-asset lookup
            # is never what a location/cost/etc. question meant -- the model
            # only reaches for it when it's already confused about which
            # asset this turn is about.
            print("  -> skipping spurious get_stock_balance call alongside a single-asset question")
            continue

        tool_fn = AVAILABLE_TOOLS.get(tool_name)
        if tool_fn is None:
            answers.append(f"Model asked for an unknown tool: {tool_name}")
            continue

        # If the model passed "@last"/"@2" instead of a real code, swap it
        # for the real identifier here -- this happens locally, so OpenAI
        # never sees the real value either way. (A no-op when `args` was
        # just replaced above with a literal code/description.)
        if "identifier" in args:
            args["identifier"] = session.resolve(args["identifier"])

        if tool_name == "get_flow_history":
            # Relative date phrases ("yesterday", "on 10 May", "lately", ...)
            # are resolved from the RAW question here, using the real
            # current date, rather than trusting the model's own date math
            # -- same reasoning as the identifier resolution above.
            inferred = _infer_date_range(question, date.today())
            if inferred:
                args["date_from"], args["date_to"] = inferred

        if raw_identifier is not None and raw_identifier != args.get("identifier"):
            print(f"  -> model chose '{tool_name}' with args {args} (resolved from '{raw_identifier}')")
        else:
            print(f"  -> model chose '{tool_name}' with args {args}")

        # gpt-4o-mini occasionally issues two identical parallel tool calls
        # for one question -- once resolved, they'd produce the exact same
        # result, so skip repeats rather than doubling up the answer text.
        call_signature = (tool_name, tuple(sorted(args.items())))
        if call_signature in seen_calls:
            print(f"  -> skipped duplicate call to '{tool_name}' with the same args")
            continue
        seen_calls.add(call_signature)

        result = tool_fn(**args)
        answers.append(format_answer(tool_name, result, question))

        identifiers = _extract_identifiers(tool_name, result)
        if identifiers:
            session.remember_assets(identifiers)
        refs = [f"@{i + 1}" for i in range(len(identifiers))]
        stubs.append(_build_stub(tool_name, result, refs))

    # Store only the safe stub(s) in history, never the real formatted answer.
    stub_for_history = " ".join(stubs)
    session.add_turn(question, stub_for_history)

    return " ".join(answers), tokens_used


def main():
    print("Asset Chatbot (test mode) -- type 'exit' or 'quit' to stop.\n")
    session = Session()  # one Session per run -- this is what remembers the conversation
    session_total_tokens = 0
    while True:
        question = input("You: ").strip()
        if question.lower() in ("exit", "quit"):
            print(f"Bye! Total tokens this session: {session_total_tokens}")
            break
        if not question:
            continue
        answer, tokens_used = ask(question, session)
        session_total_tokens += tokens_used
        print(f"Bot: {answer}  [{tokens_used} tokens | {session_total_tokens} total this session]\n")


if __name__ == "__main__":
    main()