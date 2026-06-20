-- ============================================================
-- Migration: Referral Tracking + Newsletter Infrastructure
-- Date: 2026-04-12
-- Referenced by: OPS-001, MKT-003, RES-002
-- ============================================================

-- 1. Exchange Referral Links Management
CREATE TABLE IF NOT EXISTS exchange_referrals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  exchange TEXT NOT NULL,
  referral_code TEXT NOT NULL,
  referral_url TEXT NOT NULL,
  revshare_pct NUMERIC(5,2),
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'suspended')),
  applied_at TIMESTAMPTZ,
  approved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Referral Click Tracking
CREATE TABLE IF NOT EXISTS referral_clicks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  exchange TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('report', 'newsletter', 'web', 'telegram', 'twitter', 'score_lookup')),
  content_id UUID,
  content_type TEXT CHECK (content_type IN ('report', 'newsletter', 'trade_thesis', 'forensic_alert', 'score_page')),
  ip_country TEXT,
  geo_blocked BOOLEAN DEFAULT false,
  clicked_at TIMESTAMPTZ DEFAULT now()
);

-- 3. Monthly Referral Earnings
CREATE TABLE IF NOT EXISTS referral_earnings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  exchange TEXT NOT NULL,
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  referred_users INT DEFAULT 0,
  active_traders INT DEFAULT 0,
  total_volume_usd NUMERIC(18,2) DEFAULT 0,
  commission_usd NUMERIC(10,2) DEFAULT 0,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'paid')),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 4. Email Subscribers
CREATE TABLE IF NOT EXISTS subscribers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  locale TEXT DEFAULT 'en' CHECK (locale IN ('en', 'ko', 'fr', 'es', 'de', 'ja', 'zh')),
  source TEXT CHECK (source IN ('website', 'report_download', 'referral', 'score_lookup', 'telegram', 'twitter')),
  opted_in BOOLEAN DEFAULT false,
  opt_in_token TEXT,
  opt_in_sent_at TIMESTAMPTZ,
  confirmed_at TIMESTAMPTZ,
  unsubscribed BOOLEAN DEFAULT false,
  unsubscribed_at TIMESTAMPTZ,
  ip_country TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 5. Newsletter Publications
CREATE TABLE IF NOT EXISTS newsletters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type TEXT NOT NULL CHECK (type IN ('market_pulse', 'deep_dive', 'forensic_alert', 'trade_thesis')),
  title_en TEXT NOT NULL,
  title_ko TEXT,
  content_md TEXT NOT NULL,
  content_html TEXT,
  status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'review', 'approved', 'sending', 'sent')),
  scheduled_at TIMESTAMPTZ,
  sent_at TIMESTAMPTZ,
  total_recipients INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 6. Newsletter Delivery Events (Webhook-populated)
CREATE TABLE IF NOT EXISTS newsletter_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  newsletter_id UUID REFERENCES newsletters(id) ON DELETE CASCADE,
  subscriber_id UUID REFERENCES subscribers(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL CHECK (event_type IN ('delivered', 'opened', 'clicked', 'bounced', 'unsubscribed')),
  metadata JSONB,
  occurred_at TIMESTAMPTZ DEFAULT now()
);

-- 7. ALTER existing products table for freemium
ALTER TABLE products ADD COLUMN IF NOT EXISTS free_content_md TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS free_content_html TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS paywall_message_en TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS paywall_message_ko TEXT;

-- 8. ALTER project_reports for free version file
ALTER TABLE project_reports ADD COLUMN IF NOT EXISTS gdrive_url_free TEXT;

-- 9. BCE Maturity Score breakdown (7-axis)
ALTER TABLE tracked_projects ADD COLUMN IF NOT EXISTS score_technology NUMERIC(5,1);
ALTER TABLE tracked_projects ADD COLUMN IF NOT EXISTS score_business NUMERIC(5,1);
ALTER TABLE tracked_projects ADD COLUMN IF NOT EXISTS score_tokenomics NUMERIC(5,1);
ALTER TABLE tracked_projects ADD COLUMN IF NOT EXISTS score_governance NUMERIC(5,1);
ALTER TABLE tracked_projects ADD COLUMN IF NOT EXISTS score_community NUMERIC(5,1);
ALTER TABLE tracked_projects ADD COLUMN IF NOT EXISTS score_compliance NUMERIC(5,1);
ALTER TABLE tracked_projects ADD COLUMN IF NOT EXISTS score_narrative NUMERIC(5,1);
ALTER TABLE tracked_projects ADD COLUMN IF NOT EXISTS threat_level TEXT DEFAULT 'clear' CHECK (threat_level IN ('clear', 'watch', 'caution', 'warning', 'critical'));

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_referral_clicks_exchange ON referral_clicks(exchange, clicked_at);
CREATE INDEX IF NOT EXISTS idx_referral_clicks_source ON referral_clicks(source, clicked_at);
CREATE INDEX IF NOT EXISTS idx_referral_clicks_country ON referral_clicks(ip_country) WHERE geo_blocked = false;
CREATE INDEX IF NOT EXISTS idx_subscribers_active ON subscribers(locale) WHERE opted_in = true AND unsubscribed = false;
CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email);
CREATE INDEX IF NOT EXISTS idx_newsletters_status ON newsletters(status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_newsletter_events_type ON newsletter_events(event_type, occurred_at);
CREATE INDEX IF NOT EXISTS idx_referral_earnings_period ON referral_earnings(exchange, period_start);

-- ============================================================
-- RLS POLICIES
-- ============================================================

ALTER TABLE exchange_referrals ENABLE ROW LEVEL SECURITY;
ALTER TABLE referral_clicks ENABLE ROW LEVEL SECURITY;
ALTER TABLE referral_earnings ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;
ALTER TABLE newsletters ENABLE ROW LEVEL SECURITY;
ALTER TABLE newsletter_events ENABLE ROW LEVEL SECURITY;

-- Public can insert subscriber (sign up)
CREATE POLICY "Anyone can subscribe" ON subscribers FOR INSERT WITH CHECK (true);
-- Users can see own subscription
CREATE POLICY "Users see own subscription" ON subscribers FOR SELECT USING (email = current_setting('request.jwt.claims', true)::json->>'email');

-- Newsletters: public can read sent newsletters
CREATE POLICY "Public reads sent newsletters" ON newsletters FOR SELECT USING (status = 'sent');

-- Admin-only tables (service role access)
CREATE POLICY "Service role manages referral_clicks" ON referral_clicks FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role manages referral_earnings" ON referral_earnings FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role manages exchange_referrals" ON exchange_referrals FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role manages newsletter_events" ON newsletter_events FOR ALL USING (auth.role() = 'service_role');
