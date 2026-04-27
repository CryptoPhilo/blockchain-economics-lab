import { SlideReportPage } from '../_components/SlideReportPage'

interface Props {
  params: Promise<{ locale: string; slug: string }>
}

export default async function EconReportPage({ params }: Props) {
  const { locale, slug } = await params
  return <SlideReportPage locale={locale} slug={slug} reportType="econ" />
}
