-- Strengthen ENS slide matching for localized ECON/MAT decks whose body text
-- uses translated project names and may mention comparison projects.

UPDATE public.tracked_projects AS tp
SET
  aliases = (
    SELECT ARRAY(
      SELECT DISTINCT alias
      FROM unnest(
        COALESCE(tp.aliases, '{}'::text[])
        || ARRAY[
          'ens',
          'ens 이더리움 네임 서비스',
          '이더리움 네임 서비스',
          'ens イーサリアムネームサービス',
          'イーサリアムネームサービス',
          'ens 以太坊名称服务',
          '以太坊名称服务'
        ]::text[]
      ) AS alias
      WHERE alias IS NOT NULL AND btrim(alias) <> ''
      ORDER BY alias
    )
  ),
  updated_at = now()
WHERE tp.slug = 'ethereum-name-service';
