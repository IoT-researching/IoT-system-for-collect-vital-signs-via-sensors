/* =====================================================================
   TV4 - Database/Dashboard | Microsoft SQL Server
   01_create_schema.sql : tạo CSDL, bảng devices và measurements
   Chạy lại nhiều lần an toàn (chỉ tạo nếu chưa có).
   Quy ước: thời gian lưu UTC; số đo không hợp lệ = NULL (không dùng 0).
   ===================================================================== */
IF DB_ID(N'HRSpO2Db') IS NULL CREATE DATABASE HRSpO2Db;
GO
USE HRSpO2Db;
GO

IF OBJECT_ID(N'dbo.devices', N'U') IS NULL
CREATE TABLE dbo.devices (
    device_id     NVARCHAR(50)  NOT NULL CONSTRAINT PK_devices PRIMARY KEY,
    display_name  NVARCHAR(100) NULL,
    created_at    DATETIME2(3)  NOT NULL CONSTRAINT DF_devices_created DEFAULT SYSUTCDATETIME()
);
GO

IF OBJECT_ID(N'dbo.measurements', N'U') IS NULL
CREATE TABLE dbo.measurements (
    id                 BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_measurements PRIMARY KEY,
    device_id          NVARCHAR(50)  NOT NULL
                       CONSTRAINT FK_measurements_devices REFERENCES dbo.devices(device_id),
    measured_at        DATETIME2(3)  NOT NULL,                       -- JSON "timestamp" (UTC, đồng hồ thiết bị)
    received_at        DATETIME2(3)  NOT NULL
                       CONSTRAINT DF_measurements_received DEFAULT SYSUTCDATETIME(), -- UTC, đồng hồ server
    heart_rate_bpm     FLOAT         NULL,                           -- bpm; NULL khi không hợp lệ
    spo2_percent       FLOAT         NULL,                           -- %; NULL khi không hợp lệ (giá trị MÔ PHỎNG)
    signal_quality     NVARCHAR(20)  NOT NULL,                       -- good | fair | poor | no_signal
    measurement_valid  BIT           NOT NULL,
    sequence           BIGINT        NOT NULL,
    error_code         INT           NULL,                           -- tùy chọn: mã lỗi thuật toán TV1 (0 = không lỗi)
    CONSTRAINT UQ_measurements_device_seq UNIQUE (device_id, sequence),   -- chống ghi trùng bản tin
    CONSTRAINT CK_measurements_hr   CHECK (heart_rate_bpm IS NULL OR (heart_rate_bpm >= 40 AND heart_rate_bpm <= 200)),
    CONSTRAINT CK_measurements_spo2 CHECK (spo2_percent  IS NULL OR (spo2_percent  >= 70 AND spo2_percent  <= 100)),
    CONSTRAINT CK_measurements_invalid_null
               CHECK (measurement_valid = 1 OR (heart_rate_bpm IS NULL AND spo2_percent IS NULL))
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_measurements_device_time'
               AND object_id = OBJECT_ID(N'dbo.measurements'))
CREATE INDEX IX_measurements_device_time ON dbo.measurements (device_id, measured_at DESC)
    INCLUDE (heart_rate_bpm, spo2_percent, signal_quality, measurement_valid, sequence, received_at);
GO
