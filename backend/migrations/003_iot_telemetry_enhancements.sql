-- 003_iot_telemetry_enhancements.sql: Add server ingestion timestamp to raw telemetry
ALTER TABLE iot_readings ADD COLUMN ingested_at TEXT;
