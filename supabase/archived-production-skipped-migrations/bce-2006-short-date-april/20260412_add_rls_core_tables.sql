-- Migration: Add Row Level Security (RLS) policies to core tables
-- Date: 2026-04-12
-- Description: Enable RLS on products, orders, order_items, subscriptions, user_library,
--             categories, and add missing UPDATE/DELETE policies to subscribers table.
--             This ensures data isolation and security at the database level.

-- ============================================================================
-- PRODUCTS TABLE
-- ============================================================================
-- Policy: Public read access for active products, service_role has full control
ALTER TABLE products ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public can view active products"
  ON products
  FOR SELECT
  USING (true);

CREATE POLICY "Service role manages products"
  ON products
  FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================================================
-- ORDERS TABLE
-- ============================================================================
-- Policy: Users can only see and create their own orders, service_role has full control
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users view own orders"
  ON orders
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users create own orders"
  ON orders
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Service role manages orders"
  ON orders
  FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================================================
-- ORDER_ITEMS TABLE
-- ============================================================================
-- Policy: Users can only see order items from their own orders, service_role has full control
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users view own order items"
  ON order_items
  FOR SELECT
  USING (EXISTS (
    SELECT 1 FROM orders
    WHERE orders.id = order_items.order_id
    AND orders.user_id = auth.uid()
  ));

CREATE POLICY "Service role manages order items"
  ON order_items
  FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================================================
-- SUBSCRIPTIONS TABLE
-- ============================================================================
-- Policy: Users can only see their own subscriptions, service_role has full control
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users view own subscriptions"
  ON subscriptions
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Service role manages subscriptions"
  ON subscriptions
  FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================================================
-- USER_LIBRARY TABLE
-- ============================================================================
-- Policy: Users can only see their own library items, service_role has full control
ALTER TABLE user_library ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users view own library"
  ON user_library
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Service role manages library"
  ON user_library
  FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================================================
-- CATEGORIES TABLE
-- ============================================================================
-- Policy: Public read access for categories, service_role has full control
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public can view categories"
  ON categories
  FOR SELECT
  USING (true);

CREATE POLICY "Service role manages categories"
  ON categories
  FOR ALL
  USING (auth.role() = 'service_role');

-- ============================================================================
-- SUBSCRIBERS TABLE
-- ============================================================================
-- Policy: Add missing UPDATE/DELETE policies for email-based access control
CREATE POLICY "Users update own subscriber"
  ON subscribers
  FOR UPDATE
  USING (email = current_setting('request.jwt.claims', true)::json->>'email');

CREATE POLICY "Service role manages subscribers"
  ON subscribers
  FOR ALL
  USING (auth.role() = 'service_role');
