-- OPS-007: FOR (Forensic) Report Pipeline
-- Adds 'coming_soon' status for reports waiting for draft creation
-- Adds forensic_triggers table for anomaly detection log

-- 1. Extend report_status enum with 'coming_soon'
ALTER TYPE report_status ADD VALUE IF NOT EXISTS 'coming_soon' BEFORE 'assigned';

-- 2. Add trigger_reason column to project_reports (for FOR reports)
ALTER TABLE project_reports
  ADD COLUMN IF NOT EXISTS trigger_reason text,
  ADD COLUMN IF NOT EXISTS trigger_data jsonb,
  ADD COLUMN IF NOT EXISTS triggered_at timestamptz;

-- 3. forensic_triggers — anomaly detection log (6h scan results)
CREATE TABLE IF NOT EXISTS forensic_triggers (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id      uuid REFERENCES tracked_projects(id),
  slug            text NOT NULL,
  symbol          text,
  scan_timestamp  timestamptz NOT NULL DEFAULT now(),

  -- Market data at trigger time
  price_usd       numeric,
  price_change_24h numeric,
  market_avg_change_24h numeric,
  relative_deviation numeric,  -- |token_change - market_avg|
  volume_24h      numeric,
  market_cap      numeric,

  -- Trigger evaluation
  triggered       boolean NOT NULL DEFAULT false,
  risk_level      text,  -- critical/high/elevated/moderate/low
  trigger_reasons jsonb, -- array of reason strings

  -- Report linkage
  report_id       uuid REFERENCES project_reports(id),
  status          text NOT NULL DEFAULT 'detected',  -- detected/notified/draft_pending/processing/published/dismissed

  created_at      timestamptz NOT NULL DEFAULT now()
);

-- Index for efficient polling
CREATE INDEX IF NOT EXISTS idx_forensic_triggers_status
  ON forensic_triggers(status) WHERE triggered = true;

CREATE INDEX IF NOT EXISTS idx_forensic_triggers_scan
  ON forensic_triggers(scan_timestamp DESC);

-- 4. RLS policies
ALTER TABLE forensic_triggers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "forensic_triggers_read_all"
  ON forensic_triggers FOR SELECT
  USING (true);

CREATE POLICY "forensic_triggers_insert_service"
  ON forensic_triggers FOR INSERT
  WITH CHECK (true);

CREATE POLICY "forensic_triggers_update_service"
  ON forensic_triggers FOR UPDATE
  USING (true);
