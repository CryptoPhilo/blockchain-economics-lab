-- Migration: add_tracked_projects_and_project_subscriptions
-- Date: 2026-04-09
-- Description: Adds tables for project tracking, report production pipeline,
--              forensic monitoring, and per-project subscription model.
-- Directive: STR-002, STR-003

-- 1. tracked_projects
CREATE TYPE project_status AS ENUM ('discovered', 'under_review', 'active', 'monitoring_only', 'suspended', 'archived');

CREATE TABLE tracked_projects (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name            text NOT NULL,
  slug            text UNIQUE NOT NULL,
  symbol          text NOT NULL,
  chain           text,
  category        text,
  status          project_status NOT NULL DEFAULT 'discovered',
  discovered_at   timestamptz NOT NULL DEFAULT now(),
  discovered_by   text,
  discovery_source text,
  market_cap_usd  bigint,
  tvl_usd         bigint,
  coingecko_id    text,
  website_url     text,
  last_econ_report_at     timestamptz,
  last_maturity_report_at timestamptz,
  last_forensic_report_at timestamptz,
  next_econ_due_at        timestamptz,
  next_maturity_due_at    timestamptz,
  forensic_monitoring     boolean NOT NULL DEFAULT false,
  last_forensic_check_at  timestamptz,
  maturity_score          numeric(5,2),
  maturity_stage          text,
  primary_analyst_id      text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

-- 2. project_reports
CREATE TYPE report_type AS ENUM ('econ', 'maturity', 'forensic');
CREATE TYPE report_status AS ENUM ('assigned', 'in_progress', 'in_review', 'approved', 'published', 'cancelled');

CREATE TABLE project_reports (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id      uuid NOT NULL REFERENCES tracked_projects(id) ON DELETE CASCADE,
  product_id      uuid REFERENCES products(id),
  report_type     report_type NOT NULL,
  version         integer NOT NULL DEFAULT 1,
  status          report_status NOT NULL DEFAULT 'assigned',
  assigned_to     text,
  assigned_at     timestamptz NOT NULL DEFAULT now(),
  started_at      timestamptz,
  review_at       timestamptz,
  approved_at     timestamptz,
  published_at    timestamptz,
  trigger_reason  text,
  risk_level      text,
  file_url        text,
  page_count      integer,
  task_id         text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

-- 3. forensic_monitoring_logs
CREATE TABLE forensic_monitoring_logs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id      uuid NOT NULL REFERENCES tracked_projects(id) ON DELETE CASCADE,
  check_date      date NOT NULL,
  price_change_24h    numeric(8,2),
  volume_ratio        numeric(8,2),
  whale_movement_pct  numeric(8,4),
  exchange_netflow_pct numeric(8,4),
  insider_activity    text,
  total_flags     integer NOT NULL DEFAULT 0,
  flag_details    jsonb,
  action          text NOT NULL DEFAULT 'log_only',
  analyst_id      text,
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE(project_id, check_date)
);

-- 4. project_subscriptions
CREATE TYPE project_sub_tier AS ENUM ('single', 'triple', 'five', 'all');

CREATE TABLE project_subscriptions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  tier            project_sub_tier NOT NULL DEFAULT 'single',
  status          subscription_status NOT NULL DEFAULT 'active',
  payment_method  payment_method NOT NULL,
  price_usd_cents integer NOT NULL,
  interval        text NOT NULL DEFAULT 'monthly',
  current_period_start timestamptz,
  current_period_end   timestamptz,
  crypto_wallet_address text,
  cancelled_at    timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

-- 5. project_subscription_items
CREATE TABLE project_subscription_items (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_subscription_id uuid NOT NULL REFERENCES project_subscriptions(id) ON DELETE CASCADE,
  project_id              uuid NOT NULL REFERENCES tracked_projects(id) ON DELETE CASCADE,
  added_at                timestamptz NOT NULL DEFAULT now(),
  UNIQUE(project_subscription_id, project_id)
);

-- 6. Indexes
CREATE INDEX idx_tracked_projects_status ON tracked_projects(status);
CREATE INDEX idx_tracked_projects_slug ON tracked_projects(slug);
CREATE INDEX idx_tracked_projects_next_econ ON tracked_projects(next_econ_due_at) WHERE status = 'active';
CREATE INDEX idx_tracked_projects_next_mat ON tracked_projects(next_maturity_due_at) WHERE status = 'active';
CREATE INDEX idx_tracked_projects_forensic ON tracked_projects(forensic_monitoring) WHERE forensic_monitoring = true;
CREATE INDEX idx_project_reports_project ON project_reports(project_id);
CREATE INDEX idx_project_reports_type_status ON project_reports(report_type, status);
CREATE INDEX idx_project_reports_published ON project_reports(published_at DESC) WHERE status = 'published';
CREATE INDEX idx_forensic_logs_project_date ON forensic_monitoring_logs(project_id, check_date DESC);
CREATE INDEX idx_forensic_logs_flags ON forensic_monitoring_logs(total_flags) WHERE total_flags > 0;
CREATE INDEX idx_project_subs_user ON project_subscriptions(user_id);
CREATE INDEX idx_project_sub_items_project ON project_subscription_items(project_id);

-- 7. RLS
ALTER TABLE tracked_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE forensic_monitoring_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_subscription_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public can view active projects" ON tracked_projects FOR SELECT USING (status = 'active' OR status = 'monitoring_only');
CREATE POLICY "Public can view published reports" ON project_reports FOR SELECT USING (status = 'published');
CREATE POLICY "No public access to forensic logs" ON forensic_monitoring_logs FOR SELECT USING (false);
CREATE POLICY "Users can view own project subscriptions" ON project_subscriptions FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own project subscriptions" ON project_subscriptions FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can view own subscription items" ON project_subscription_items FOR SELECT USING (project_subscription_id IN (SELECT id FROM project_subscriptions WHERE user_id = auth.uid()));

-- 8. Extend products table
ALTER TABLE products ADD COLUMN IF NOT EXISTS project_id uuid REFERENCES tracked_projects(id);
ALTER TABLE products ADD COLUMN IF NOT EXISTS report_type text;
ALTER TABLE products ADD COLUMN IF NOT EXISTS report_version integer;
CREATE INDEX idx_products_project ON products(project_id) WHERE project_id IS NOT NULL;

-- 9. Extend product_type enum
ALTER TYPE product_type ADD VALUE IF NOT EXISTS 'project_subscription';
