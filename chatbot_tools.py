import pyodbc

SQL_SERVER_NAME = r"localhost\SQLEXPRESS"
SQL_SERVER_DATABASE = "TCubeRealSchema"


def get_connection() -> pyodbc.Connection:
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={SQL_SERVER_NAME};"
        f"DATABASE={SQL_SERVER_DATABASE};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )


def _rows_to_dicts(cursor: pyodbc.Cursor, rows: list) -> list[dict]:
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def get_asset_by_identifier(identifier: str) -> dict | None:
    query = """
        SELECT a.Asset_No, a.Display_ID, a.EPC_ID, a.Description, a.SKU, a.Category,
               s.Label AS Status, l.Location, a.PIC,
               a.Date_of_Purchase, a.Warranty_Expiry_Date, a.Calibration_Date, a.Date_of_Scrap,
               a.Cost, a.Current_Value, a.Yearly_Depreciation, a.Final_Depreciation,
               a.LastBal, a.Remarks,
               a.Date_of_Expire, a.Vendor_Name, a.Useful_Life, a.Minor_Category,
               a.UOM, a.Ref_No, a.BatchNo,
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


def get_flow_history(identifier, date_from=None, date_to=None):
    asset = get_asset_by_identifier(identifier)
    if asset is None:
        # identifier might be a plain description -- find the asset by keyword
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT Asset_No FROM Asset WHERE IsDelete = 0 AND UPPER(Description) LIKE UPPER(?)",
                (f"%{identifier}%",)
            )
            desc_rows = cursor.fetchall()
            if len(desc_rows) == 1:
                asset = get_asset_by_identifier(desc_rows[0][0])
    if asset is None:
        return None
    query = """
        SELECT f.Date, f.Qty_In, f.Qty_Out, f.Person_In_Charge,
               f.Remarks, f.Balance, f.Doc_No,
               f.Creator, f.Creation_Time, f.Edit_Time,
               l.Location AS Flow_Location
        FROM Asset_Flow_History f
        JOIN Asset a ON f.Asset_ID = a.Asset_ID
        LEFT JOIN Asset_Location l ON f.Location_Id = l.Asset_Location_ID
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
        return {"asset": asset, "history": _rows_to_dicts(cursor, rows)}


def get_stock_balance(category=None, location=None, pic=None):
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
    if pic:
        query += " AND UPPER(a.PIC) = UPPER(?)"
        params.append(pic)
    query += " GROUP BY s.Label ORDER BY s.Label"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return _rows_to_dicts(cursor, rows)


def list_assets(category=None, location=None, status=None, pic=None,
                balance_lt=None, balance_gt=None):
    query = """
        SELECT a.Asset_No, a.Display_ID, a.EPC_ID, a.Description, a.Category,
               s.Label AS Status, l.Location, a.PIC,
               a.SKU, a.Cost, a.Current_Value, a.Yearly_Depreciation, a.Final_Depreciation,
               a.Date_of_Purchase, a.Warranty_Expiry_Date, a.LastBal, a.Remarks,
               a.Date_of_Expire, a.Minor_Category
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
    if status:
        query += " AND UPPER(s.Label) = UPPER(?)"
        params.append(status)
    if pic:
        query += " AND UPPER(a.PIC) = UPPER(?)"
        params.append(pic)
    if balance_lt is not None:
        query += " AND a.LastBal < ?"
        params.append(balance_lt)
    if balance_gt is not None:
        query += " AND a.LastBal > ?"
        params.append(balance_gt)
    query += " ORDER BY a.Asset_No"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return _rows_to_dicts(cursor, rows)


def search_assets_by_description(keyword: str) -> list[dict]:
    """
    Search for assets by a word or phrase in their description. Now
    includes the same extra fields as list_assets (see above) for the
    same reason -- consistency across every tool that can return asset
    rows. No row limit; formatting decides display length.
    """
    query = """
        SELECT a.Asset_No, a.Display_ID, a.EPC_ID, a.Description, a.Category,
               s.Label AS Status, l.Location, a.PIC,
               a.SKU, a.Cost, a.Current_Value, a.Yearly_Depreciation, a.Final_Depreciation,
               a.Date_of_Purchase, a.Warranty_Expiry_Date, a.LastBal, a.Remarks,
               a.Date_of_Expire, a.Minor_Category
        FROM Asset a
        JOIN Asset_Status s   ON a.Asset_Status_ID = s.Asset_Status_ID
        JOIN Asset_Location l ON a.Asset_Location_ID = l.Asset_Location_ID
        WHERE a.IsDelete = 0
          AND UPPER(a.Description) LIKE UPPER(?)
        ORDER BY a.Asset_No
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (f"%{keyword}%",))
        rows = cursor.fetchall()
        return _rows_to_dicts(cursor, rows)


GET_ASSET_BY_IDENTIFIER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_asset_by_identifier",
        "description": (
            "Look up a single asset's current status, location, and assigned "
            "person. Use this ONLY when the user gives a short CODE -- this "
            "includes EPC, EPC ID, Tag ID, RFID tag, asset number (e.g. "
            "'AST-001' or 'ast-001'), or display ID (e.g. 'A-0011' or "
            "'a-0011'). Codes can be in ANY case -- uppercase, lowercase, or "
            "mixed -- pass them exactly as the user typed. The system always "
            "matches case-insensitively. Do NOT use this if the user describes "
            "the asset in plain words instead of giving a code (e.g. "
            "'Laptop #11', 'the forklift', 'office chair') -- use "
            "search_assets_by_description for that instead, even if the "
            "wording looks like it could be copied from a record. If the "
            "user means an asset already found earlier in the conversation "
            "('that', 'it', 'the second one') and you were not given its "
            "real code, pass '@last' or '@1'/'@2'/etc. instead -- never "
            "invent a code. "
            "This is ALSO the correct tool for 'full details', 'all "
            "information', 'everything', or 'all info' about ONE asset -- "
            "use it for those even when the identifier is a short code, "
            "UNLESS the user also explicitly asks about history, movements, "
            "or past check-ins/check-outs (use get_flow_history for that "
            "instead). Asking for 'full details' by itself is never a "
            "reason to call get_flow_history."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "The asset code the user mentioned -- EPC, Tag ID, Asset No (e.g. 'ast-001' or 'AST-001'), or Display ID (e.g. 'a-0011' or 'A-0011'). Any case works. Pass it exactly as typed. OR, if referring back to a previously found asset whose real code you were never shown, pass '@last' (most recent) or '@1'/'@2'/etc. (Nth from the last list shown).",
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
            "activity within a date range. ALSO use this for COMBINED questions "
            "that explicitly ask about an asset's details AND its history "
            "together (e.g. 'who created the Toyota Forklift and what is its "
            "flow history?') -- this tool returns both the asset details and "
            "the history in one call. The identifier can be a short code OR a "
            "plain description of the asset. "
            "Do NOT use this tool just because the user said 'full details', "
            "'everything', or 'all info' about an asset -- that phrase alone "
            "means get_asset_by_identifier (or search_assets_by_description), "
            "NOT history. Only use get_flow_history when the question itself "
            "specifically mentions history, movement(s), being checked in/out, "
            "activity, or a date/time range (e.g. 'yesterday', 'last week', "
            "'on 10 May', 'in May', 'lately', 'latest'). "
            "For date_from/date_to, pass the date phrase the user actually "
            "used (e.g. 'yesterday', '10 May', 'May', 'last week') if it "
            "isn't a full explicit calendar date -- do not try to compute or "
            "guess the real calendar date yourself, the system resolves "
            "relative phrases locally using the real current date. Only pass "
            "an explicit YYYY-MM-DD directly when the user typed a full date "
            "including the year."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "The asset code (EPC/Tag ID/Asset No/Display ID, any case) OR a plain description of the asset (e.g. 'Toyota Forklift'). Pass exactly what the user said. OR, if referring back to a previously found asset whose real code you were never shown, pass '@last' (most recent) or '@1'/'@2'/etc. (Nth from the last list shown).",
                },
                "date_from": {
                    "type": "string",
                    "description": (
                        "Optional start date. Use YYYY-MM-DD if the user gave an "
                        "explicit full date. Otherwise pass the natural phrase "
                        "verbatim (e.g. 'yesterday', '10 May', 'May', 'last "
                        "week', 'lately') and it will be resolved locally. Omit "
                        "if not mentioned."
                    ),
                },
                "date_to": {
                    "type": "string",
                    "description": (
                        "Optional end date. Same rules as date_from -- use "
                        "YYYY-MM-DD for an explicit full date, otherwise pass "
                        "the natural phrase verbatim. Omit if not mentioned."
                    ),
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
            "specific named asset; use get_asset_by_identifier for that instead. "
            "IMPORTANT: Do NOT use this when the user asks about an individual "
            "asset's 'last balance', 'remaining quantity', or 'stock level' -- "
            "those refer to the per-asset LastBal field, not a status count. "
            "Use search_assets_by_description or get_asset_by_identifier for those."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": (
                        "Optional EXACT category label to filter by. The only valid "
                        "values are: 'IT Equipment', 'Machinery', 'Furniture', "
                        "'Safety Equipment', 'Tools'. Do NOT infer a category from "
                        "a product description -- if the user says 'laptops', "
                        "'generators', 'chairs', etc., that is a DESCRIPTION keyword, "
                        "not a category; use search_assets_by_description for those "
                        "instead. Only use this field when the user says one of the "
                        "exact category names above. Never put a status word here."
                    ),
                },
                "location": {
                    "type": "string",
                    "description": "Optional location to filter by, e.g. 'Warehouse A'.",
                },
                "pic": {
                    "type": "string",
                    "description": "Optional person in charge to filter by, e.g. 'Mary Lim', 'John Tan'. Use this when the user asks about assets belonging to or managed by a specific person.",
                },
            },
            "required": [],
        },
    },
}

LIST_ASSETS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_assets",
        "description": (
            "List multiple assets, optionally filtered by category, location, "
            "status, person in charge (PIC), or balance threshold. Use this "
            "when the user asks to LIST or SEE assets -- for example 'what are "
            "the assets under IT Equipment', 'show me all assets at Warehouse A', "
            "'list all available assets', 'show not available items', 'which "
            "assets are on loan?', 'show in-transit assets', 'list all assets "
            "under Mary Lim', 'what does John Tan have?', 'what categories are "
            "under Mary Lim?' (use pic param for any person-based filter), or "
            "balance threshold questions like 'which assets at Warehouse A have "
            "balance under 10', 'show items with balance more than 5' (use "
            "balance_lt for less-than, balance_gt for greater-than). "
            "Do NOT use this for counting -- use get_stock_balance for that. "
            "Do NOT use this for a single specific asset -- use get_asset_by_identifier."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional category, e.g. 'IT Equipment', 'Machinery', 'Furniture', 'Safety Equipment', 'Tools'.",
                },
                "location": {
                    "type": "string",
                    "description": "Optional location, e.g. 'Warehouse A', 'Site Office'.",
                },
                "status": {
                    "type": "string",
                    "description": "Optional status, e.g. 'Available', 'On Loan', 'In-Transit', 'Not Available', 'Discarded'.",
                },
                "pic": {
                    "type": "string",
                    "description": "Optional person in charge to filter by, e.g. 'Mary Lim', 'John Tan'. Use this when the user asks what assets a specific person has or manages.",
                },
                "balance_lt": {
                    "type": "number",
                    "description": "Optional: only include assets whose LastBal is LESS THAN this number. Use for 'balance under N', 'balance below N', 'less than N'. e.g. 10 for 'balance under 10'.",
                },
                "balance_gt": {
                    "type": "number",
                    "description": "Optional: only include assets whose LastBal is GREATER THAN this number. Use for 'balance above N', 'balance over N', 'more than N'.",
                },
            },
            "required": [],
        },
    },
}

SEARCH_ASSETS_BY_DESCRIPTION_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_assets_by_description",
        "description": (
            "Search for assets by a word or phrase describing what they ARE, "
            "rather than a short code. Use this for: finding items "
            "('find the forklift', 'search for laptops', 'do we have any "
            "generators'); yes/no category questions ('is the dell laptop a "
            "safety equipment?'); COUNTING by product name ('how many laptops?', "
            "'how many generators?'); and asking about any field of a SPECIFIC "
            "named asset -- including its last balance, current balance, "
            "remaining stock, cost, current value, yearly depreciation rate, "
            "warranty, remarks, EPC, category, etc. (e.g. 'what is the last "
            "balance of the Toyota Forklift?', 'what is the current balance of "
            "the Dell Laptop?', 'what is the depreciation rate of the Dell "
            "Laptop?', 'what is the EPC of the office "
            "chair?'). Always call this tool for these field questions when the "
            "user gives a description instead of a code -- do NOT ask the user "
            "for an identifier first. For counting by product name, pass the product name as "
            "the keyword -- do NOT use get_stock_balance for this, because "
            "product names like 'laptop' or 'generator' are not category labels. "
            "Do NOT use this for asset codes or IDs even in lowercase "
            "(e.g. 'ast-001', 'a-0011', 'e2003...') -- use "
            "get_asset_by_identifier for those. Only use get_stock_balance "
            "if the user says an EXACT category name like 'IT Equipment' or "
            "'Machinery', or filters by location or status."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "A word or phrase from the asset's description, e.g. 'forklift', 'office chair', 'laptop #11'.",
                }
            },
            "required": ["keyword"],
        },
    },
}


def get_asset_ranking(rank_by: str, category=None, location=None, limit=10):
    top_n = min(int(limit or 10), 50)  # cast to int, cap at 50 for safety

    if rank_by == "most_movement":
        query = f"""
            SELECT TOP {top_n}
                   a.Asset_No, a.Display_ID, a.Description, a.Category,
                   s.Label AS Status, l.Location, a.PIC,
                   COUNT(f.Asset_Flow_History_ID) AS Move_Count
            FROM Asset a
            JOIN Asset_Status s   ON a.Asset_Status_ID = s.Asset_Status_ID
            JOIN Asset_Location l ON a.Asset_Location_ID = l.Asset_Location_ID
            LEFT JOIN Asset_Flow_History f ON a.Asset_ID = f.Asset_ID
            WHERE a.IsDelete = 0
        """
        params = []
        if category:
            query += " AND UPPER(a.Category) = UPPER(?)"
            params.append(category)
        if location:
            query += " AND UPPER(l.Location) = UPPER(?)"
            params.append(location)
        query += (
            " GROUP BY a.Asset_No, a.Display_ID, a.Description, a.Category,"
            " s.Label, l.Location, a.PIC"
            " ORDER BY Move_Count DESC"
        )
    else:
        order = "ASC" if rank_by == "least_balance" else "DESC"
        query = f"""
            SELECT TOP {top_n}
                   a.Asset_No, a.Display_ID, a.Description, a.Category,
                   s.Label AS Status, l.Location, a.PIC, a.LastBal
            FROM Asset a
            JOIN Asset_Status s   ON a.Asset_Status_ID = s.Asset_Status_ID
            JOIN Asset_Location l ON a.Asset_Location_ID = l.Asset_Location_ID
            WHERE a.IsDelete = 0 AND a.LastBal IS NOT NULL
        """
        params = []
        if category:
            query += " AND UPPER(a.Category) = UPPER(?)"
            params.append(category)
        if location:
            query += " AND UPPER(l.Location) = UPPER(?)"
            params.append(location)
        query += f" ORDER BY a.LastBal {order}"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return _rows_to_dicts(cursor, rows)


GET_ASSET_RANKING_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_asset_ranking",
        "description": (
            "Rank assets by stock balance or movement activity. Use this for: "
            "least/lowest balance ('which asset has the least stock?', 'what "
            "needs restocking?', 'which item is running low?', 'show me assets "
            "with least balance'); most/highest balance ('which asset has the "
            "most stock?', 'what has the highest balance?'); or most movement "
            "history ('which asset has the most movements?', 'what is the most "
            "active item?', 'what is the most selling item?', 'which asset is "
            "checked in or out the most?'). Can be filtered by category or "
            "location. Do NOT use this to list all assets -- use list_assets."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "rank_by": {
                    "type": "string",
                    "enum": ["least_balance", "most_balance", "most_movement"],
                    "description": (
                        "'least_balance' = lowest LastBal first (items to restock); "
                        "'most_balance' = highest LastBal first; "
                        "'most_movement' = most flow history records first "
                        "(most active / most selling item)."
                    ),
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter, e.g. 'IT Equipment', 'Machinery', 'Furniture', 'Safety Equipment', 'Tools'.",
                },
                "location": {
                    "type": "string",
                    "description": "Optional location filter, e.g. 'Warehouse A', 'Warehouse B'.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of top results to return. Defaults to 10 if not specified.",
                },
            },
            "required": ["rank_by"],
        },
    },
}


AVAILABLE_TOOLS = {
    "get_asset_by_identifier": get_asset_by_identifier,
    "get_flow_history": get_flow_history,
    "get_stock_balance": get_stock_balance,
    "list_assets": list_assets,
    "search_assets_by_description": search_assets_by_description,
    "get_asset_ranking": get_asset_ranking,
}

TOOL_SCHEMAS = [
    GET_ASSET_BY_IDENTIFIER_SCHEMA,
    GET_FLOW_HISTORY_SCHEMA,
    GET_STOCK_BALANCE_SCHEMA,
    LIST_ASSETS_SCHEMA,
    SEARCH_ASSETS_BY_DESCRIPTION_SCHEMA,
    GET_ASSET_RANKING_SCHEMA,
]