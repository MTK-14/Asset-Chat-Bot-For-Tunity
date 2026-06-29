"""
chatbot_tools.py
-----------------
This file defines the chatbot's "tools" -- the ONLY things the AI model
is allowed to do. Each tool is ONE hard-coded, parameterized, read-only
SQL query. The AI never writes its own SQL; it only ever picks one of
these tools and supplies the parameters. This is what keeps the chatbot
safe even though it's now calling a cloud model instead of a local one.
"""
import pyodbc

# These three values describe YOUR SQL Server Express install. If you
# used the default instance name during setup, only SQL_SERVER_DATABASE
# should need to change later when you point this at the real database.
SQL_SERVER_NAME = r"localhost\SQLEXPRESS"
SQL_SERVER_DATABASE = "TCubeRealSchema"


def get_connection() -> pyodbc.Connection:
    """
    The ONLY function that knows how to connect to the database.
    Right now that's your local SQL Server Express install. Later, when
    you point this at the real tcube821 database, only the values above
    (and possibly the server name) need to change -- every tool function
    below stays exactly the same, because they all just call get_connection().

    Trusted_Connection=yes means "use my Windows login" -- no password to
    manage or accidentally commit to a file. TrustServerCertificate=yes
    skips validating the server's self-signed certificate -- the same
    fix as the "Trust server certificate" checkbox in SSMS. Fine for a
    local dev database; this would need a real certificate for anything
    accessed over a real network later.
    """
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={SQL_SERVER_NAME};"
        f"DATABASE={SQL_SERVER_DATABASE};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )


def _rows_to_dicts(cursor: pyodbc.Cursor, rows: list) -> list[dict]:
    """
    pyodbc doesn't have sqlite3's row_factory shortcut, so this is the
    one small helper that replaces it: it turns pyodbc's row objects
    into plain dictionaries using the column names from the cursor.
    Every tool function below uses this the same way.
    """
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def get_asset_by_identifier(identifier: str) -> dict | None:
    """
    Look up a single asset by EPC / Tag ID / Asset No / Display ID.
    Matching is case-insensitive because staff may scan or type the
    identifier in any case.

    Returns every column group requested in feedback: core identity,
    dates (purchase/warranty/calibration/scrap), financial/value, SKU,
    single-vs-multiple tracking type, and audit info (creator/times).
    The TrackingType decoding (Single/Multiple/Container) mirrors the
    same CASE logic your real ItemViewItemMgmt view already uses for
    the IsIndividual column.
    """
    query = """
        SELECT a.Asset_No, a.Display_ID, a.EPC_ID, a.Description, a.SKU,
               s.Label AS Status, l.Location, a.PIC,
               a.Date_of_Purchase, a.Warranty_Expiry_Date, a.Calibration_Date, a.Date_of_Scrap,
               a.Cost, a.Current_Value, a.Yearly_Depreciation, a.Final_Depreciation,
               CASE a.IsIndividual
                    WHEN 1 THEN 'Single (serialized)'
                    WHEN 0 THEN 'Multiple/bulk'
                    ELSE 'Container'
               END AS TrackingType,
               a.Creator, a.Creation_Time, a.Edit_Time
        FROM Asset a
        JOIN Asset_Status s   ON a.Asset_Status_ID = s.Asset_Status_ID
        JOIN Asset_Location l ON a.Asset_Location_ID = l.Asset_Location_ID
        WHERE a.IsDelete = 0
          AND (UPPER(a.EPC_ID) = UPPER(?)
               OR UPPER(a.Asset_No) = UPPER(?)
               OR UPPER(a.Display_ID) = UPPER(?))
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (identifier, identifier, identifier))
        row = cursor.fetchone()
        if row is None:
            return None
        return _rows_to_dicts(cursor, [row])[0]


def get_flow_history(
    identifier: str, date_from: str | None = None, date_to: str | None = None
) -> list[dict] | None:
    """
    Get the check-in/check-out history for ONE specific asset, optionally
    limited to a date range. Returns None (not an empty list) if the
    asset itself doesn't exist -- that lets the caller tell the difference
    between "no such asset" and "asset exists, no history in that range".
    Dates are plain "YYYY-MM-DD" strings, both inclusive.
    """
    asset = get_asset_by_identifier(identifier)
    if asset is None:
        return None

    query = """
        SELECT f.Date, f.Qty_In, f.Qty_Out, f.Person_In_Charge,
               f.Remarks, f.Balance, f.Doc_No,
               f.Creator, f.Creation_Time, f.Edit_Time
        FROM Asset_Flow_History f
        JOIN Asset a ON f.Asset_ID = a.Asset_ID
        WHERE UPPER(a.Asset_No) = UPPER(?)
    """
    params = [asset["Asset_No"]]
    if date_from:
        query += " AND f.Date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND f.Date <= ?"
        params.append(date_to)
    query += " ORDER BY f.Date"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return _rows_to_dicts(cursor, rows)


def get_stock_balance(
    category: str | None = None, location: str | None = None
) -> list[dict]:
    """
    Count active (non-deleted) assets grouped by their current status,
    optionally filtered to one category and/or one location. Use this
    for "how many" questions about a group of assets -- NOT for looking
    up one specific asset.
    """
    query = """
        SELECT s.Label AS Status, COUNT(*) AS Count
        FROM Asset a
        JOIN Asset_Status s   ON a.Asset_Status_ID = s.Asset_Status_ID
        JOIN Asset_Location l ON a.Asset_Location_ID = l.Asset_Location_ID
        WHERE a.IsDelete = 0
    """
    params = []
    if category:
        query += " AND UPPER(a.Category) = UPPER(?)"
        params.append(category)
    if location:
        query += " AND UPPER(l.Location) = UPPER(?)"
        params.append(location)
    query += " GROUP BY s.Label ORDER BY s.Label"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return _rows_to_dicts(cursor, rows)


# The JSON schema that tells the model this tool exists, what it does,
# and what parameter it needs. The "description" is doing the heavy
# lifting here -- it's how the model learns that EPC, Tag ID, and
# asset number all mean the same thing in this system, without us
# writing any of that mapping logic ourselves.
#
# This uses the standard Chat Completions "tools" shape (a nested
# "function" object). It's the most widely supported format -- it
# works against real OpenAI, and against Gemini's OpenAI-compatible
# endpoint, with no changes. We skip OpenAI-only extras like
# "strict"/"additionalProperties" so the schema stays portable.
GET_ASSET_BY_IDENTIFIER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_asset_by_identifier",
        "description": (
            "Look up a single asset's current status, location, and assigned "
            "person. Use this whenever the user refers to a SPECIFIC asset by "
            "any kind of identifier -- this includes EPC, EPC ID, Tag ID, RFID "
            "tag, asset number, or asset code. These all refer to the same "
            "kind of value in this system; pass whatever value the user gave, "
            "exactly as typed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "The EPC / Tag ID / Asset No / Display ID the user mentioned.",
                }
            },
            "required": ["identifier"],
        },
    },
}


GET_FLOW_HISTORY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_flow_history",
        "description": (
            "Get the movement / check-in / check-out history for ONE specific "
            "asset over time. Use this when the user asks about an asset's "
            "history, past movements, who checked it in or out previously, or "
            "activity within a date range. Use get_asset_by_identifier instead "
            "if the user just wants the asset's CURRENT status, not its history."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "The EPC / Tag ID / Asset No / Display ID of the asset.",
                },
                "date_from": {
                    "type": "string",
                    "description": "Optional start date in YYYY-MM-DD format. Omit if not mentioned.",
                },
                "date_to": {
                    "type": "string",
                    "description": "Optional end date in YYYY-MM-DD format. Omit if not mentioned.",
                },
            },
            "required": ["identifier"],
        },
    },
}

GET_STOCK_BALANCE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_stock_balance",
        "description": (
            "Get a COUNT of assets grouped by their current status (Available, "
            "Not Available, On Loan, In-Transit, Discarded). The result ALWAYS "
            "shows all status groups -- use this for ANY 'how many' question "
            "about assets, including questions about a specific status like "
            "'how many are available' or 'how many are on loan'. Just call this "
            "with no filters in that case and read the matching status from the "
            "breakdown; status words are never a valid value for the category or "
            "location parameters below. Do NOT use this for looking up one "
            "specific named asset; use get_asset_by_identifier for that instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": (
                        "Optional ASSET TYPE to filter by, such as 'IT Equipment', "
                        "'Machinery', 'Furniture', 'Safety Equipment', or 'Tools'. "
                        "Never put a status word here (e.g. 'available', 'not "
                        "available', 'on loan', 'in-transit', 'discarded') -- those "
                        "are statuses, not categories, and are not valid values for "
                        "this field. Leave this out if no specific asset type was mentioned."
                    ),
                },
                "location": {
                    "type": "string",
                    "description": "Optional location to filter by, e.g. 'Warehouse A'.",
                },
            },
            "required": [],
        },
    },
}


# Maps a tool NAME (that the model returns) to the actual Python function
# to run.
AVAILABLE_TOOLS = {
    "get_asset_by_identifier": get_asset_by_identifier,
    "get_flow_history": get_flow_history,
    "get_stock_balance": get_stock_balance,
}

TOOL_SCHEMAS = [
    GET_ASSET_BY_IDENTIFIER_SCHEMA,
    GET_FLOW_HISTORY_SCHEMA,
    GET_STOCK_BALANCE_SCHEMA,
]