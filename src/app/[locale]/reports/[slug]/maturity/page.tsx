import { SlideReportPage } from '../_components/SlideReportPage'
import { getReportVersionParam } from '@/lib/report-versioning'

export const dynamic = 'force-dynamic'
export const revalidate = 0

interface Props {
  params: Promise<{ locale: string; slug: string }>
  searchParams?: Promise<{ version?: string; lang?: string }>
}

export default async function MaturityReportPage({ params, searchParams }: Props) {
  const { locale, slug } = await params
  const { version, lang } = searchParams ? await searchParams : {}
  return (
    <SlideReportPage
      locale={locale}
      slug={slug}
      reportType="maturity"
      requestedVersion={getReportVersionParam(version)}
      requestedLanguage={lang}
    />
  )
}
