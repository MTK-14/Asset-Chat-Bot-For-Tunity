IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'AssetChatbotTest')
BEGIN
    CREATE DATABASE AssetChatbotTest;
END
GO

USE AssetChatbotTest;
GO

-- drop tables 
IF OBJECT_ID('Asset_Flow_History', 'U') IS NOT NULL DROP TABLE Asset_Flow_History;
IF OBJECT_ID('Asset', 'U') IS NOT NULL DROP TABLE Asset;
IF OBJECT_ID('Asset_Status', 'U') IS NOT NULL DROP TABLE Asset_Status;
IF OBJECT_ID('Asset_Location', 'U') IS NOT NULL DROP TABLE Asset_Location;
GO

CREATE TABLE Asset_Status (
    Asset_Status_ID INT PRIMARY KEY,
    Name            NVARCHAR(255) NOT NULL
);

CREATE TABLE Asset_Location (
    Asset_Location_ID INT PRIMARY KEY,
    Location           NVARCHAR(255) NOT NULL
);

CREATE TABLE Asset (
    Asset_ID          INT PRIMARY KEY,
    Display_ID        NVARCHAR(50),
    Asset_No          NVARCHAR(50),
    EPC_ID             NVARCHAR(100),   -- shown in the UI as "Tag ID"
    Description        NVARCHAR(255),
    Category           NVARCHAR(100),
    Asset_Status_ID    INT,
    Asset_Location_ID  INT,
    PIC                NVARCHAR(100),   -- person in charge
    IsDelete           BIT DEFAULT 0,
    FOREIGN KEY (Asset_Status_ID)   REFERENCES Asset_Status(Asset_Status_ID),
    FOREIGN KEY (Asset_Location_ID) REFERENCES Asset_Location(Asset_Location_ID)
);

CREATE TABLE Asset_Flow_History (
    Asset_Flow_History_ID INT PRIMARY KEY,
    Date                  DATE NOT NULL,
    Qty_In                 FLOAT DEFAULT 0,
    Qty_Out                FLOAT DEFAULT 0,
    Person_In_Charge       NVARCHAR(100),
    Remarks                NVARCHAR(300),
    Asset_ID               INT NOT NULL,
    Balance                FLOAT,
    Doc_No                 NVARCHAR(50),
    Location_Id            INT,
    FOREIGN KEY (Asset_ID)    REFERENCES Asset(Asset_ID),
    FOREIGN KEY (Location_Id) REFERENCES Asset_Location(Asset_Location_ID)
);
GO

--seed data 
INSERT INTO Asset_Status (Asset_Status_ID, Name) VALUES
    (1, 'Available'), (2, 'Checked Out'), (3, 'Under Maintenance'), (4, 'Scrapped');

INSERT INTO Asset_Location (Asset_Location_ID, Location) VALUES
    (1, 'Warehouse A'), (2, 'Warehouse B'), (3, 'Site Office'), (4, 'Workshop');


INSERT INTO Asset (Asset_ID, Display_ID, Asset_No, EPC_ID, Description, Category,
                    Asset_Status_ID, Asset_Location_ID, PIC, IsDelete) VALUES
    (1,  'A-0001', 'AST-001', 'E2003411FE0E1001', 'Dell Laptop',          'IT Equipment',     2, 1, 'John Tan',    0),
    (2,  'A-0002', 'AST-002', 'e2003411fe0e1002', 'Toyota Forklift',      'Machinery',        1, 2, 'Mary Lim',    0),
    (3,  'A-0003', 'AST-003', 'E2003411FE0E1003', 'Zebra Barcode Scanner','IT Equipment',     1, 1, 'John Tan',    0),
    (4,  'A-0004', 'AST-004', 'E2003411FE0E1004', 'iPad Tablet',          'IT Equipment',     2, 3, 'Ahmad Rizal', 0),
    (5,  'A-0005', 'AST-005', 'e2003411fe0e1005', 'Honda Generator',      'Machinery',        3, 4, 'Mary Lim',    0),
    (6,  'A-0006', 'AST-006', 'E2003411FE0E1006', 'Office Chair',         'Furniture',        1, 3, 'Ahmad Rizal', 0),
    (7,  'A-0007', 'AST-007', 'E2003411FE0E1007', 'Pallet Jack',          'Machinery',        2, 2, 'John Tan',    0),
    (8,  'A-0008', 'AST-008', 'E2003411FE0E1008', 'Safety Helmet Set',    'Safety Equipment', 1, 4, 'Mary Lim',    0),
    (9,  'A-0009', 'AST-009', 'E2003411FE0E1009', 'Old Printer',          'IT Equipment',     4, 4, 'Ahmad Rizal', 1),  -- soft-deleted
    (10, 'A-0010', 'AST-010', 'E2003411FE0E1010', 'Hand Drill',           'Tools',            1, 4, 'John Tan',    0);

INSERT INTO Asset_Flow_History (Asset_Flow_History_ID, Date, Qty_In, Qty_Out, Person_In_Charge,
                                 Remarks, Asset_ID, Balance, Doc_No, Location_Id) VALUES
    (1, '2026-05-01', 1, 0, 'John Tan',    'Issued for fieldwork',    1, 1, 'DOC-1001', 1),
    (2, '2026-05-03', 0, 1, 'John Tan',    'Checked out to site',     1, 0, 'DOC-1002', 2),
    (3, '2026-05-10', 1, 0, 'Mary Lim',    'Returned to warehouse',   2, 1, 'DOC-1003', 2),
    (4, '2026-05-15', 0, 1, 'Mary Lim',    'Sent to client site',     2, 0, 'DOC-1004', 2),
    (5, '2026-05-18', 1, 0, 'Ahmad Rizal', 'Maintenance completed',   5, 1, 'DOC-1005', 4),
    (6, '2026-05-20', 0, 1, 'John Tan',    'Picked for project A',    7, 0, 'DOC-1006', 2),
    (7, '2026-05-22', 1, 0, 'Mary Lim',    'Stock take adjustment',   8, 1, 'DOC-1007', 4),
    (8, '2026-05-25', 0, 1, 'Ahmad Rizal', 'Issued to workshop',      6, 0, 'DOC-1008', 3);
GO

SELECT a.Asset_No, a.Description, a.EPC_ID, s.Name AS Status, l.Location
FROM Asset a
JOIN Asset_Status s   ON a.Asset_Status_ID = s.Asset_Status_ID
JOIN Asset_Location l ON a.Asset_Location_ID = l.Asset_Location_ID
WHERE a.IsDelete = 0
ORDER BY a.Asset_No;