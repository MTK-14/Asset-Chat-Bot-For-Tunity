-- create_real_schema.sql
-- ------------------------
-- A clean, self-contained subset of your real production schema --
-- just the tables this chatbot project actually touches, with their
-- REAL full column names (not the trimmed 10-column test version).
-- Built in correct dependency order so it runs without the cascading
-- errors you hit running the entire 12,000+ line full script.

-- Drop and recreate the WHOLE database fresh, rather than dropping
-- individual tables one by one. This is immune to leftover objects
-- from anything else that may have ended up in this database (e.g.
-- the stray "ItemViewItemMgmtBKUP2" view that blocked the old approach)
-- -- it doesn't matter what's in there, this always starts clean.
USE master;
GO
IF EXISTS (SELECT name FROM sys.databases WHERE name = 'TCubeRealSchema')
BEGIN
    ALTER DATABASE TCubeRealSchema SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE TCubeRealSchema;
END
GO
CREATE DATABASE TCubeRealSchema;
GO

USE TCubeRealSchema;
GO

-- ===== Asset_Status (real columns) =====
CREATE TABLE [dbo].[Asset_Status](
    [Asset_Status_ID] [int] IDENTITY(1,1) NOT NULL,
    [Display_ID] [varchar](50) NULL,
    [Creator] [varchar](50) NULL,
    [Creation_Time] [datetime] NULL,
    [Edit_Time] [datetime] NULL,
    [Availability] [int] NULL,
    [Status] [nvarchar](255) NULL,
    [Name] [nvarchar](255) NULL,
    [Label] [varchar](300) NULL,
    [IsDelete] [bit] NULL,
    [DeletedBy] [int] NULL,
    [DeletedOn] [datetime] NULL,
    PRIMARY KEY CLUSTERED ([Asset_Status_ID] ASC)
);
GO

-- ===== Asset_Location (real columns, including Hierarchy) =====
CREATE TABLE [dbo].[Asset_Location](
    [Asset_Location_ID] [int] IDENTITY(1,1) NOT NULL,
    [Display_ID] [varchar](50) NULL,
    [Creator] [varchar](50) NULL,
    [Creation_Time] [datetime] NULL,
    [Edit_Time] [datetime] NULL,
    [Availability] [int] NULL,
    [Status] [nvarchar](255) NULL,
    [Location] [nvarchar](255) NULL,
    [IsDelete] [bit] NULL,
    [DeletedOn] [datetime] NULL,
    [DeletedBy] [varchar](50) NULL,
    [Parent] [int] NULL,
    [TierLevel] [int] NOT NULL DEFAULT 0,
    [Hierarchy] [nvarchar](2000) NULL,
    PRIMARY KEY CLUSTERED ([Asset_Location_ID] ASC)
);
GO

-- ===== UDL (used by Asset's Remarks/Description2/3 fields -- not seeded, just present) =====
CREATE TABLE [dbo].[UDL](
    [UDLID] [int] IDENTITY(1,1) NOT NULL,
    [UDLKey] [nvarchar](100) NOT NULL,
    [UDLValue] [nvarchar](500) NOT NULL,
    [IsDefault] [bit] NOT NULL DEFAULT 0,
    [DtAdded] [datetime] NOT NULL DEFAULT GETDATE(),
    [Status] [bit] NOT NULL DEFAULT 1,
    [UDLIDKey] AS (CONCAT([UDLKey], '::', [UDLID])) PERSISTED NOT NULL,
    [IsDelete] [bit] NULL,
    [DeletedOn] [datetime] NULL,
    [DeletedBy] [varchar](50) NULL,
    [Parent] [int] NULL,
    [TierLevel] [int] NOT NULL DEFAULT 0,
    [Creator] [varchar](50) NULL,
    PRIMARY KEY CLUSTERED ([UDLID] ASC)
);
GO

-- ===== Asset (real columns -- all 58, most left NULL by our seed data) =====
CREATE TABLE [dbo].[Asset](
    [Asset_ID] [int] IDENTITY(1,1) NOT NULL,
    [Display_ID] [varchar](50) NULL,
    [Creator] [varchar](50) NULL,
    [Creation_Time] [datetime] NULL,
    [Edit_Time] [datetime] NULL,
    [Availability] [int] NULL,
    [Status] [nvarchar](255) NULL,
    [Asset_No] [nvarchar](255) NULL,
    [Description] [nvarchar](500) NULL,
    [EPC_ID] [nvarchar](255) NULL,
    [Date_of_Purchase] [datetime] NULL,
    [Asset_Status_ID] [int] NULL,
    [Date_of_Scrap] [datetime] NULL,
    [Cost] [float] NULL,
    [Asset_Location_ID] [int] NULL,
    [PIC] [nvarchar](255) NULL,
    [Yearly_Depreciation] [float] NULL,
    [Current_Value] [float] NULL,
    [Remarks] [nvarchar](255) NULL,
    [Ref_No] [nvarchar](255) NULL,
    [IsIndividual] [bit] NULL,
    [Category] [nvarchar](255) NULL,
    [Minor_Category] [nvarchar](255) NULL,
    [Vendor_Name] [nvarchar](255) NULL,
    [Vendor_Invoice] [nvarchar](255) NULL,
    [SKU] [nvarchar](100) NULL,
    [Useful_Life] [float] NULL,
    [Cost_BF] [float] NULL,
    [Cost_Addition] [float] NULL,
    [Cost_Disposal] [float] NULL,
    [Cost_CF] [float] NULL,
    [Final_Depreciation] [float] NULL,
    [AccDep_BF] [float] NULL,
    [CarryingVaue_BF] [float] NULL,
    [CarryingVaue_CF] [float] NULL,
    [AccDep_Disposal] [float] NULL,
    [AccDep_Addition] [float] NULL,
    [AccDep_CF] [float] NULL,
    [UOM] [nvarchar](100) NULL,
    [BatchNo] [nvarchar](100) NULL,
    [Description2] [nvarchar](255) NULL,
    [Description3] [nvarchar](255) NULL,
    [Warranty_Expiry_Date] [datetime] NULL,
    [Calibration_Date] [datetime] NULL,
    [Remarks2] [nvarchar](255) NULL,
    [ImageName] [nvarchar](255) NULL,
    [Date_of_Expire] [datetime] NULL,
    [LastBal] [float] NULL DEFAULT 0,
    [Remarks3] [nvarchar](255) NULL,
    [Remarks4] [nvarchar](255) NULL,
    [IsPrint] [bit] NOT NULL DEFAULT 0,
    [Container_ID] [int] NULL,
    [Container_Int_Loc] [nvarchar](50) NULL,
    [IsDelete] [bit] NULL,
    [DeletedOn] [datetime] NULL,
    [DeletedBy] [varchar](50) NULL,
    [LastDataChanges] [datetime] NULL,
    [Remarks7] [nvarchar](255) NULL,
    [Remarks8] [nvarchar](255) NULL,
    [Remarks9] [nvarchar](255) NULL,
    [Remarks10] [nvarchar](255) NULL,
    [Date_Of_Entry] [datetime] NULL,
    PRIMARY KEY CLUSTERED ([Asset_ID] ASC)
);
GO

-- ===== Asset_Flow_History (real columns) =====
CREATE TABLE [dbo].[Asset_Flow_History](
    [Asset_Flow_History_ID] [int] IDENTITY(1,1) NOT NULL,
    [Display_ID] [varchar](50) NULL,
    [Creator] [varchar](50) NULL,
    [Creation_Time] [datetime] NULL,
    [Edit_Time] [datetime] NULL,
    [Availability] [int] NULL,
    [Status] [nvarchar](255) NULL,
    [Date] [datetime] NULL,
    [Qty_In] [float] NULL,
    [Qty_Out] [float] NULL,
    [Person_In_Charge] [nvarchar](255) NULL,
    [Remarks] [nvarchar](255) NULL,
    [Asset_ID] [int] NULL,
    [Balance] [float] NULL,
    [FIFO] [bit] NULL DEFAULT 1,
    [Doc_No] [varchar](50) NULL,
    [AdditionalData] [nvarchar](max) NULL,
    [Location_Id] [int] NULL,
    PRIMARY KEY CLUSTERED ([Asset_Flow_History_ID] ASC)
);
GO

ALTER TABLE [dbo].[Asset_Flow_History]
    ADD CONSTRAINT FK_Asset_Flow_History_Asset
    FOREIGN KEY (Asset_ID) REFERENCES [dbo].[Asset] (Asset_ID);
GO

-- ===== The two simple, safe views (ItemViewItemMgmt deliberately skipped -- see note above) =====
CREATE VIEW [dbo].[Asset_Readable_View] AS
SELECT a.Asset_No, a.Display_ID, a.EPC_ID AS Tag_ID, a.Description, a.Category,
       a.IsIndividual,                    -- raw 0/1, exactly as in the real system
       s.Label AS Asset_Status, l.Location,
       a.Date_of_Purchase, a.Date_of_Expire, a.LastBal, a.Cost, a.SKU, a.PIC,
       a.Remarks, a.IsDelete
FROM dbo.Asset a
JOIN dbo.Asset_Status s   ON a.Asset_Status_ID = s.Asset_Status_ID
JOIN dbo.Asset_Location l ON a.Asset_Location_ID = l.Asset_Location_ID;
GO

CREATE VIEW [dbo].[Flow_History_View] AS
SELECT dbo.Asset.Asset_No, dbo.Asset.Description, dbo.Asset.EPC_ID, dbo.Asset_Flow_History.Date,
       dbo.Asset_Flow_History.Qty_In, dbo.Asset_Flow_History.Qty_Out, dbo.Asset_Flow_History.Person_In_Charge,
       dbo.Asset_Flow_History.Remarks, dbo.Asset_Flow_History.Doc_No, dbo.Asset_Flow_History.Balance
FROM dbo.Asset_Flow_History
INNER JOIN dbo.Asset ON dbo.Asset_Flow_History.Asset_ID = dbo.Asset.Asset_ID;
GO

CREATE VIEW [dbo].[Stock_Balance_View] AS
SELECT dbo.Asset.Description, dbo.Asset.Category, dbo.Asset_Location.Location, SUM(dbo.Asset.LastBal) AS StockBalance
FROM dbo.Asset
INNER JOIN dbo.Asset_Location ON dbo.Asset.Asset_Location_ID = dbo.Asset_Location.Asset_Location_ID
GROUP BY dbo.Asset.Description, dbo.Asset.Category, dbo.Asset_Location.Location;
GO

-- ===== Seed data -- same content as earlier test DB, now in the real schema =====
SET IDENTITY_INSERT [dbo].[Asset_Status] ON;
INSERT INTO [dbo].[Asset_Status] (Asset_Status_ID, Name, Label) VALUES
    (1, 'Available', 'Available'),
    (2, 'NotAvailable', 'Not Available'),
    (3, 'Scrapped', 'Discarded'),
    (4, 'On Loan', 'On Loan'),
    (5, 'In-Transit', 'In-Transit');
SET IDENTITY_INSERT [dbo].[Asset_Status] OFF;

SET IDENTITY_INSERT [dbo].[Asset_Location] ON;
INSERT INTO [dbo].[Asset_Location] (Asset_Location_ID, Location, TierLevel) VALUES
    (1, 'Warehouse A', 0), (2, 'Warehouse B', 0), (3, 'Site Office', 0), (4, 'Workshop', 0);
SET IDENTITY_INSERT [dbo].[Asset_Location] OFF;

SET IDENTITY_INSERT [dbo].[Asset] ON;
INSERT INTO [dbo].[Asset] (Asset_ID, Display_ID, Asset_No, EPC_ID, Description, Category,
                           Asset_Status_ID, Asset_Location_ID, PIC, IsDelete,
                           SKU, IsIndividual, Date_of_Purchase, Warranty_Expiry_Date,
                           Calibration_Date, Date_of_Scrap, Cost, Current_Value,
                           Yearly_Depreciation, Final_Depreciation, Creator, Creation_Time, Edit_Time,
                           Remarks, LastBal, Date_of_Expire) VALUES
    (1,  'A-0001', 'AST-001', 'E2003411FE0E1001', 'Dell Laptop',          'IT Equipment',     4, 1, 'John Tan',    0,
         'SKU-LAP-001', 1, '2024-01-15', '2027-01-15', NULL,        NULL, 1800.00, 1200.00, 360.00, 0.00, 'admin', '2024-01-15', '2026-05-03',
         'Issued to fieldwork team', 1, NULL),
    (2,  'A-0002', 'AST-002', 'e2003411fe0e1002', 'Toyota Forklift',      'Machinery',        1, 2, 'Mary Lim',    0,
         'SKU-FORK-002', 0, '2022-06-01', NULL,        '2026-06-01', NULL, 25000.00, 18000.00, 2500.00, 0.00, 'admin', '2022-06-01', '2026-05-15',
         'Heavy machinery - handle with care', 1, NULL),
    (3,  'A-0003', 'AST-003', 'E2003411FE0E1003', 'Zebra Barcode Scanner','IT Equipment',     1, 1, 'John Tan',    0,
         'SKU-SCAN-003', 1, '2023-03-10', '2025-03-10', NULL,        NULL, 450.00, 200.00, 90.00, 0.00, 'admin', '2023-03-10', '2026-01-10',
         'Calibrated annually', 1, NULL),
    (4,  'A-0004', 'AST-004', 'E2003411FE0E1004', 'iPad Tablet',          'IT Equipment',     4, 3, 'Ahmad Rizal', 0,
         'SKU-TAB-004', 1, '2024-08-20', '2026-08-20', NULL,        NULL, 900.00, 700.00, 180.00, 0.00, 'admin', '2024-08-20', '2026-04-20',
         'Used for inventory checks', 1, NULL),
    (5,  'A-0005', 'AST-005', 'e2003411fe0e1005', 'Honda Generator',      'Machinery',        2, 4, 'Mary Lim',    0,
         'SKU-GEN-005', 0, '2021-11-05', NULL,        '2026-05-18', NULL, 5000.00, 2000.00, 800.00, 0.00, 'admin', '2021-11-05', '2026-05-18',
         'Backup power unit', 1, NULL),
    (6,  'A-0006', 'AST-006', 'E2003411FE0E1006', 'Office Chair',         'Furniture',        1, 3, 'Ahmad Rizal', 0,
         'SKU-CHR-006', 1, '2023-09-01', NULL,        NULL,        NULL, 150.00, 90.00, 30.00, 0.00, 'admin', '2023-09-01', '2026-02-01',
         'Ergonomic chair', 1, NULL),
    (7,  'A-0007', 'AST-007', 'E2003411FE0E1007', 'Pallet Jack',          'Machinery',        4, 2, 'John Tan',    0,
         'SKU-PJ-007', 1, '2022-02-14', '2025-02-14', NULL,        NULL, 600.00, 300.00, 120.00, 0.00, 'admin', '2022-02-14', '2026-05-20',
         'Warehouse equipment', 1, NULL),
    (8,  'A-0008', 'AST-008', 'E2003411FE0E1008', 'Safety Helmet Set',    'Safety Equipment', 1, 4, 'Mary Lim',    0,
         'SKU-HEL-008', 0, '2024-04-01', NULL,        NULL,        NULL, 80.00, 60.00, 16.00, 0.00, 'admin', '2024-04-01', '2026-05-22',
         'Bulk safety stock', 12, '2027-04-01'),
    (9,  'A-0009', 'AST-009', 'E2003411FE0E1009', 'Old Printer',          'IT Equipment',     3, 4, 'Ahmad Rizal', 1,
         'SKU-PRN-009', 1, '2018-01-01', '2020-01-01', NULL,        '2026-01-01', 300.00, 0.00, 60.00, 300.00, 'admin', '2018-01-01', '2026-01-01',
         'Decommissioned', 0, NULL),
    (10, 'A-0010', 'AST-010', 'E2003411FE0E1010', 'Hand Drill',           'Tools',            5, 4, 'John Tan',    0,
         'SKU-DRL-010', 1, '2023-07-07', '2025-07-07', NULL,        NULL, 200.00, 130.00, 40.00, 0.00, 'admin', '2023-07-07', '2025-12-01',
         'Tool room item', 1, NULL);
SET IDENTITY_INSERT [dbo].[Asset] OFF;

SET IDENTITY_INSERT [dbo].[Asset_Flow_History] ON;
INSERT INTO [dbo].[Asset_Flow_History] (Asset_Flow_History_ID, Date, Qty_In, Qty_Out, Person_In_Charge,
                                          Remarks, Asset_ID, Balance, Doc_No, Location_Id) VALUES
    (1, '2026-05-01', 1, 0, 'John Tan',    'Issued for fieldwork',    1, 1, 'DOC-1001', 1),
    (2, '2026-05-03', 0, 1, 'John Tan',    'Checked out to site',     1, 0, 'DOC-1002', 2),
    (3, '2026-05-10', 1, 0, 'Mary Lim',    'Returned to warehouse',   2, 1, 'DOC-1003', 2),
    (4, '2026-05-15', 0, 1, 'Mary Lim',    'Sent to client site',     2, 0, 'DOC-1004', 2),
    (5, '2026-05-18', 1, 0, 'Ahmad Rizal', 'Maintenance completed',   5, 1, 'DOC-1005', 4),
    (6, '2026-05-20', 0, 1, 'John Tan',    'Picked for project A',    7, 0, 'DOC-1006', 2),
    (7, '2026-05-22', 1, 0, 'Mary Lim',    'Stock take adjustment',   8, 1, 'DOC-1007', 4),
    (8, '2026-05-25', 0, 1, 'Ahmad Rizal', 'Issued to workshop',      6, 0, 'DOC-1008', 3);
SET IDENTITY_INSERT [dbo].[Asset_Flow_History] OFF;
GO

-- using the readable view, should return 9 rows (AST-009 excluded) =====
SELECT * FROM [dbo].[Asset_Readable_View] WHERE IsDelete = 0 ORDER BY Asset_No;