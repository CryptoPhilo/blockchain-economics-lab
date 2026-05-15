import { SlideReportPage } from '../_components/SlideReportPage'

export const dynamic = 'force-dynamic'
export const revalidate = 0

interface Props {
  params: Promise<{ locale: string; slug: string }>
}

export default async function MaturityReportPage({ params }: Props) {
  const { locale, slug } = await params
  return <SlideReportPage locale={locale} slug={slug} reportType="maturity" />
}
