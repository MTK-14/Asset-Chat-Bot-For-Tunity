import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "assetchatbot_test.db"


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the lookup tables and the two tables the chatbot cares about."""
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        DROP TABLE IF EXISTS Asset_Flow_History;
        DROP TABLE IF EXISTS Asset;
        DROP TABLE IF EXISTS Asset_Status;
        DROP TABLE IF EXISTS Asset_Location;

        -- Lookup table: what does Asset_Status_ID actually mean?
        CREATE TABLE Asset_Status (
            Asset_Status_ID INTEGER PRIMARY KEY,
            Name            TEXT NOT NULL
        );

        -- Lookup table: what does Asset_Location_ID actually mean?
        CREATE TABLE Asset_Location (
            Asset_Location_ID INTEGER PRIMARY KEY,
            Location           TEXT NOT NULL
        );

        -- Trimmed version of the real Asset table: only the columns
        -- the chatbot's tools will actually need in Week 1-3.
        CREATE TABLE Asset (
            Asset_ID          INTEGER PRIMARY KEY,
            Display_ID        TEXT,
            Asset_No          TEXT,
            EPC_ID             TEXT,      -- shown in the UI as "Tag ID"
            Description        TEXT,
            Category           TEXT,
            Asset_Status_ID    INTEGER,
            Asset_Location_ID  INTEGER,
            PIC                TEXT,      -- person in charge
            IsDelete           INTEGER DEFAULT 0,
            FOREIGN KEY (Asset_Status_ID)   REFERENCES Asset_Status(Asset_Status_ID),
            FOREIGN KEY (Asset_Location_ID) REFERENCES Asset_Location(Asset_Location_ID)
        );

        -- Trimmed version of the real Asset_Flow_History table.
        CREATE TABLE Asset_Flow_History (
            Asset_Flow_History_ID INTEGER PRIMARY KEY,
            Date                  TEXT NOT NULL,   -- ISO format: YYYY-MM-DD
            Qty_In                 REAL DEFAULT 0,
            Qty_Out                REAL DEFAULT 0,
            Person_In_Charge       TEXT,
            Remarks                TEXT,
            Asset_ID               INTEGER NOT NULL,
            Balance                REAL,
            Doc_No                 TEXT,
            Location_Id            INTEGER,
            FOREIGN KEY (Asset_ID)    REFERENCES Asset(Asset_ID),
            FOREIGN KEY (Location_Id) REFERENCES Asset_Location(Asset_Location_ID)
        );
        """
    )


def seed_data(conn: sqlite3.Connection) -> None:
    """Insert realistic dummy rows -- including mixed-case EPCs and a soft-deleted asset."""

    statuses = [
        (1, "Available"),
        (2, "Checked Out"),
        (3, "Under Maintenance"),
        (4, "Scrapped"),
    ]
    conn.executemany(
        "INSERT INTO Asset_Status (Asset_Status_ID, Name) VALUES (?, ?)", statuses
    )

    locations = [
        (1, "Warehouse A"),
        (2, "Warehouse B"),
        (3, "Site Office"),
        (4, "Workshop"),
    ]
    conn.executemany(
        "INSERT INTO Asset_Location (Asset_Location_ID, Location) VALUES (?, ?)",
        locations,
    )

    # Note the deliberately mixed-case EPCs (E2003... vs e2003...) --
    # this is exactly the case-sensitivity problem we need the lookup
    # tool to handle correctly later.
    assets = [
        (1, "A-0001", "AST-001", "E2003411FE0E1001", "Dell Laptop", "IT Equipment", 2, 1, "John Tan", 0),
        (2, "A-0002", "AST-002", "e2003411fe0e1002", "Toyota Forklift", "Machinery", 1, 2, "Mary Lim", 0),
        (3, "A-0003", "AST-003", "E2003411FE0E1003", "Zebra Barcode Scanner", "IT Equipment", 1, 1, "John Tan", 0),
        (4, "A-0004", "AST-004", "E2003411FE0E1004", "iPad Tablet", "IT Equipment", 2, 3, "Ahmad Rizal", 0),
        (5, "A-0005", "AST-005", "e2003411fe0e1005", "Honda Generator", "Machinery", 3, 4, "Mary Lim", 0),
        (6, "A-0006", "AST-006", "E2003411FE0E1006", "Office Chair", "Furniture", 1, 3, "Ahmad Rizal", 0),
        (7, "A-0007", "AST-007", "E2003411FE0E1007", "Pallet Jack", "Machinery", 2, 2, "John Tan", 0),
        (8, "A-0008", "AST-008", "E2003411FE0E1008", "Safety Helmet Set", "Safety Equipment", 1, 4, "Mary Lim", 0),
        (9, "A-0009", "AST-009", "E2003411FE0E1009", "Old Printer", "IT Equipment", 4, 4, "Ahmad Rizal", 1),  # soft-deleted
        (10, "A-0010", "AST-010", "E2003411FE0E1010", "Hand Drill", "Tools", 1, 4, "John Tan", 0),
    ]
    conn.executemany(
        """INSERT INTO Asset
           (Asset_ID, Display_ID, Asset_No, EPC_ID, Description, Category,
            Asset_Status_ID, Asset_Location_ID, PIC, IsDelete)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        assets,
    )

    flow_history = [
        (1, "2026-05-01", 1, 0, "John Tan", "Issued for fieldwork", 1, 1, "DOC-1001", 1),
        (2, "2026-05-03", 0, 1, "John Tan", "Checked out to site", 1, 0, "DOC-1002", 2),
        (3, "2026-05-10", 1, 0, "Mary Lim", "Returned to warehouse", 2, 1, "DOC-1003", 2),
        (4, "2026-05-15", 0, 1, "Mary Lim", "Sent to client site", 2, 0, "DOC-1004", 2),
        (5, "2026-05-18", 1, 0, "Ahmad Rizal", "Maintenance completed", 5, 1, "DOC-1005", 4),
        (6, "2026-05-20", 0, 1, "John Tan", "Picked for project A", 7, 0, "DOC-1006", 2),
        (7, "2026-05-22", 1, 0, "Mary Lim", "Stock take adjustment", 8, 1, "DOC-1007", 4),
        (8, "2026-05-25", 0, 1, "Ahmad Rizal", "Issued to workshop", 6, 0, "DOC-1008", 3),
    ]
    conn.executemany(
        """INSERT INTO Asset_Flow_History
           (Asset_Flow_History_ID, Date, Qty_In, Qty_Out, Person_In_Charge,
            Remarks, Asset_ID, Balance, Doc_No, Location_Id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        flow_history,
    )


def verify(conn: sqlite3.Connection) -> None:
    """Run a couple of sanity-check queries so you SEE the data is real before moving on."""

    print("\n--- All active assets with readable status/location (mirrors Flow_History_View idea) ---")
    rows = conn.execute(
        """
        SELECT a.Asset_No, a.Description, a.EPC_ID, s.Name AS Status, l.Location
        FROM Asset a
        JOIN Asset_Status s   ON a.Asset_Status_ID = s.Asset_Status_ID
        JOIN Asset_Location l ON a.Asset_Location_ID = l.Asset_Location_ID
        WHERE a.IsDelete = 0
        ORDER BY a.Asset_No
        """
    ).fetchall()
    for row in rows:
        print(row)

    print("\n--- Case-insensitive EPC lookup test (typed in lowercase, stored in mixed case) ---")
    test_epc = "e2003411fe0e1001"  # deliberately lowercase
    rows = conn.execute(
        "SELECT Asset_No, Description, EPC_ID FROM Asset WHERE UPPER(EPC_ID) = UPPER(?)",
        (test_epc,),
    ).fetchall()
    for row in rows:
        print(row)

    print("\n--- Flow history for one asset ---")
    rows = conn.execute(
        """
        SELECT f.Date, f.Qty_In, f.Qty_Out, f.Person_In_Charge, f.Remarks, f.Balance
        FROM Asset_Flow_History f
        JOIN Asset a ON f.Asset_ID = a.Asset_ID
        WHERE a.Asset_No = ?
        ORDER BY f.Date
        """,
        ("AST-001",),
    ).fetchall()
    for row in rows:
        print(row)


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    with sqlite3.connect(DB_PATH) as conn:
        create_schema(conn)
        seed_data(conn)
        conn.commit()
        verify(conn)

    print(f"\nDone. Test database created at: {DB_PATH.resolve()}")


if __name__ == "__main__":
    main()