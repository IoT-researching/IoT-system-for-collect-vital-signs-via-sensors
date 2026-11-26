/* =====================================================================
   TV4 - 02_views_and_queries.sql : view phục vụ dashboard / báo cáo
   Ngưỡng trong view là giá trị mặc định (10 s / 60 s / 5 s); dashboard Streamlit
   tính theo cấu hình trong .env nên có thể khác nếu bạn đổi cấu hình.
   ===================================================================== */
USE HRSpO2Db;
GO

-- Bản tin mới nhất của từng thiết bị
CREATE OR ALTER VIEW dbo.vw_latest_measurement AS
SELECT device_id, measured_at, received_at, heart_rate_bpm, spo2_percent,
       signal_quality, measurement_valid, sequence
FROM (SELECT m.*, ROW_NUMBER() OVER (PARTITION BY device_id ORDER BY measured_at DESC, sequence DESC) AS rn
      FROM dbo.measurements AS m) AS x
WHERE rn = 1;
GO

-- Trạng thái node: online (<= 10 s) / stale (<= 60 s) / offline
CREATE OR ALTER VIEW dbo.vw_node_status AS
SELECT device_id,
       last_received_at,
       DATEDIFF(SECOND, last_received_at, SYSUTCDATETIME()) AS age_seconds,
       CASE WHEN DATEDIFF(SECOND, last_received_at, SYSUTCDATETIME()) <= 10 THEN N'online'
            WHEN DATEDIFF(SECOND, last_received_at, SYSUTCDATETIME()) <= 60 THEN N'stale'
            ELSE N'offline' END AS node_status
FROM (SELECT device_id, MAX(received_at) AS last_received_at
      FROM dbo.measurements GROUP BY device_id) AS t;
GO

-- Chất lượng dữ liệu theo giờ: tỷ lệ hợp lệ và số bản tin thiếu (theo sequence)
CREATE OR ALTER VIEW dbo.vw_data_quality_hourly AS
SELECT device_id,
       DATEADD(HOUR, DATEDIFF(HOUR, 0, measured_at), 0) AS hour_start,
       COUNT(*)                                          AS total_records,
       SUM(CASE WHEN measurement_valid = 1 THEN 1 ELSE 0 END) AS valid_records,
       SUM(CASE WHEN measurement_valid = 0 THEN 1 ELSE 0 END) AS invalid_records,
       CAST(100.0 * SUM(CASE WHEN measurement_valid = 1 THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(5,1)) AS pct_valid,
       (MAX(sequence) - MIN(sequence) + 1) - COUNT(DISTINCT sequence) AS missing_by_sequence
FROM dbo.measurements
GROUP BY device_id, DATEADD(HOUR, DATEDIFF(HOUR, 0, measured_at), 0);
GO

-- Khoảng KHÔNG HỢP LỆ liên tiếp (kỹ thuật gaps-and-islands)
CREATE OR ALTER VIEW dbo.vw_invalid_intervals AS
WITH x AS (
    SELECT device_id, measured_at, measurement_valid,
           ROW_NUMBER() OVER (PARTITION BY device_id ORDER BY measured_at, sequence) AS rn_all,
           ROW_NUMBER() OVER (PARTITION BY device_id, measurement_valid ORDER BY measured_at, sequence) AS rn_grp
    FROM dbo.measurements)
SELECT device_id, MIN(measured_at) AS start_at, MAX(measured_at) AS end_at, COUNT(*) AS n_records
FROM x
WHERE measurement_valid = 0
GROUP BY device_id, rn_all - rn_grp;
GO

-- Khoảng MẤT DỮ LIỆU: hai bản tin liên tiếp cách nhau > 5 s (= 2.5 x chu kỳ 2 s)
CREATE OR ALTER VIEW dbo.vw_gaps AS
SELECT device_id, prev_at AS gap_start, measured_at AS gap_end,
       DATEDIFF(SECOND, prev_at, measured_at) AS gap_seconds,
       sequence - prev_seq - 1 AS missing_by_sequence
FROM (SELECT device_id, measured_at, sequence,
             LAG(measured_at) OVER (PARTITION BY device_id ORDER BY measured_at, sequence) AS prev_at,
             LAG(sequence)    OVER (PARTITION BY device_id ORDER BY measured_at, sequence) AS prev_seq
      FROM dbo.measurements) AS t
WHERE prev_at IS NOT NULL
  AND (DATEDIFF(MILLISECOND, prev_at, measured_at) > 5000 OR sequence - prev_seq > 1);
GO

/* ---- Truy vấn mẫu --------------------------------------------------
-- Lịch sử 1 giờ gần nhất của node_01 (UTC)
SELECT measured_at, heart_rate_bpm, spo2_percent, signal_quality, measurement_valid, sequence
FROM dbo.measurements
WHERE device_id = N'node_01' AND measured_at >= DATEADD(HOUR, -1, SYSUTCDATETIME())
ORDER BY measured_at;

-- Chỉ số hợp lệ để vẽ biểu đồ
SELECT measured_at, heart_rate_bpm, spo2_percent FROM dbo.measurements
WHERE device_id = N'node_01' AND measurement_valid = 1 ORDER BY measured_at;
------------------------------------------------------------------------ */
