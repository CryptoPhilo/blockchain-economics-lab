-- Migration: append_ethena_usde_aliases
-- Date: 2026-05-03
-- Description: Map CMC USDe snapshot slugs back to the canonical Ethena project.

UPDATE tracked_projects
SET aliases = COALESCE(aliases, '{}'::text[]) || ARRAY(
  SELECT alias
  FROM unnest(ARRAY['ethena-usde', 'usde']::text[]) AS alias
  WHERE NOT alias = ANY(COALESCE(aliases, '{}'::text[]))
)
WHERE slug = 'ethena';
