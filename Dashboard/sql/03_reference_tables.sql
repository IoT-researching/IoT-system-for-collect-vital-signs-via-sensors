/* =====================================================================
   TV4 - 03_reference_tables.sql : bảng dữ liệu tham chiếu (BIDMC) và HR ước lượng (Ngày 22, 24)
   ===================================================================== */
USE HRSpO2Db;
GO

IF OBJECT_ID(N'dbo.reference_records', N'U') IS NULL
CREATE TABLE dbo.reference_records (
    record_id    NVARCHAR(30)  NOT NULL CONSTRAINT PK_reference_records PRIMARY KEY,  -- ví dụ bidmc01
    source       NVARCHAR(30)  NOT NULL,                                              -- BIDMC | SYNTHETIC
    duration_s   INT           NULL,
    notes        NVARCHAR(500) NULL,
    imported_at  DATETIME2(3)  NOT NULL CONSTRAINT DF_refrec_imported DEFAULT SYSUTCDATETIME()
);
GO

IF OBJECT_ID(N'dbo.reference_signals', N'U') IS NULL
CREATE TABLE dbo.reference_signals (
    id                BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_reference_signals PRIMARY KEY,
    record_id         NVARCHAR(30) NOT NULL CONSTRAINT FK_refsig_record REFERENCES dbo.reference_records(record_id),
    t_sec             FLOAT NOT NULL,        -- giây tính từ đầu bản ghi
    hr_ecg_ref_bpm    FLOAT NULL,            -- numerics HR (suy ra từ ECG)
    pr_ppg_ref_bpm    FLOAT NULL,            -- numerics PULSE (suy ra từ PPG)
    spo2_ref_percent  FLOAT NULL,
    CONSTRAINT UQ_refsig_record_t UNIQUE (record_id, t_sec)
);
GO

IF OBJECT_ID(N'dbo.hr_estimates', N'U') IS NULL
CREATE TABLE dbo.hr_estimates (
    id          BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_hr_estimates PRIMARY KEY,
    record_id   NVARCHAR(30) NOT NULL CONSTRAINT FK_hrest_record REFERENCES dbo.reference_records(record_id),
    t_sec       FLOAT NOT NULL,              -- thời điểm kết thúc cửa sổ 4 s, tính từ đầu bản ghi
    hr_est_bpm  FLOAT NULL,                  -- NULL khi cửa sổ không hợp lệ
    is_valid    BIT   NOT NULL,
    CONSTRAINT UQ_hrest_record_t UNIQUE (record_id, t_sec)
);
GO
