import createNextIntlPlugin from 'next-intl/plugin'
import type { NextConfig } from 'next'

const withNextIntl = createNextIntlPlugin('./src/i18n/request.ts')

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: '/:locale/reports/:slug/forensic',
        destination: '/:locale/reports/forensic/:slug',
        permanent: false,
      },
    ]
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'wbqponoiyoeqlepxogcb.supabase.co',
        port: '',
        pathname: '/storage/v1/object/public/**',
        search: '',
      },
    ],
  },
}

export default withNextIntl(nextConfig)
