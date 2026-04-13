import DisclaimerBanner from '@/components/DisclaimerBanner'

interface Props {
  params: Promise<{ locale: string }>
}

export default async function DisclaimerPage({ params }: Props) {
  const { locale } = await params
  const isKo = locale === 'ko'

  return (
    <div className="max-w-3xl mx-auto px-6 py-16">
      <h1 className="text-3xl font-bold text-white mb-8">
        {isKo ? '면책 조항' : 'Disclaimer'}
      </h1>

      <div className="prose prose-invert prose-sm max-w-none space-y-6">
        <section>
          <h2 className="text-xl font-semibold text-white mb-3">
            {isKo ? '일반 면책 조항' : 'General Disclaimer'}
          </h2>
          <p className="text-gray-400 leading-relaxed">
            {isKo
              ? '블록체인 경제 연구소(Blockchain Economics Lab, bcelab.xyz)가 제공하는 모든 콘텐츠는 정보 제공 및 교육 목적으로만 작성됩니다. 본 콘텐츠는 금융, 투자, 거래 또는 법률 자문을 구성하지 않으며, 그렇게 해석되어서도 안 됩니다.'
              : 'All content provided by Blockchain Economics Lab (bcelab.xyz) is created for informational and educational purposes only. This content does not constitute, and should not be construed as, financial, investment, trading, or legal advice.'}
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-white mb-3">
            {isKo ? '투자 위험' : 'Investment Risk'}
          </h2>
          <p className="text-gray-400 leading-relaxed">
            {isKo
              ? '암호화폐 및 디지털 자산 시장에는 원금 손실을 포함한 상당한 위험이 따릅니다. 과거의 성과가 미래의 결과를 보장하지 않습니다. 투자 결정을 내리기 전에 자격을 갖춘 금융 자문가와 상담하십시오.'
              : 'Cryptocurrency and digital asset markets carry significant risk, including the potential loss of principal. Past performance does not guarantee future results. Consult a qualified financial advisor before making any investment decisions.'}
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-white mb-3">
            {isKo ? '제3자 링크' : 'Third-Party Links'}
          </h2>
          <p className="text-gray-400 leading-relaxed">
            {isKo
              ? '본 웹사이트에는 제3자 웹사이트로의 링크가 포함될 수 있습니다. 이러한 링크는 편의를 위해 제공되며, BCE Lab은 제3자 콘텐츠에 대해 보증하거나 책임을 지지 않습니다. 사용자는 자신의 관할권에서 거래소 라이선스 요건을 확인해야 합니다.'
              : 'This website may contain links to third-party websites. These links are provided for convenience, and BCE Lab does not endorse or accept responsibility for third-party content. Users should verify exchange licensing requirements in their jurisdiction.'}
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-white mb-3">
            {isKo ? 'AI 생성 콘텐츠' : 'AI-Generated Content'}
          </h2>
          <p className="text-gray-400 leading-relaxed">
            {isKo
              ? 'BCE Lab의 보고서와 분석은 AI 연구 에이전트의 도움으로 생성됩니다. 모든 콘텐츠는 인간 전문가의 검수를 거치지만, AI 생성 콘텐츠의 특성상 오류가 포함될 수 있습니다. 항상 독립적인 검증을 수행하십시오.'
              : 'BCE Lab reports and analyses are generated with the assistance of AI research agents. All content undergoes human expert review, but AI-generated content may contain errors by nature. Always perform independent verification.'}
          </p>
        </section>

        <section>
          <h2 className="text-xl font-semibold text-white mb-3">
            {isKo ? '관할권 고지' : 'Jurisdictional Notice'}
          </h2>
          <p className="text-gray-400 leading-relaxed">
            {isKo
              ? '일부 관할권에서는 암호화폐 거래 및 관련 서비스에 대한 규제가 다를 수 있습니다. 사용자는 자신의 거주 지역 법률을 확인하고 준수할 책임이 있습니다. BCE Lab은 특정 국가나 지역에서의 서비스 이용 가능성을 보장하지 않습니다.'
              : 'Regulations regarding cryptocurrency trading and related services may vary across jurisdictions. Users are responsible for verifying and complying with the laws of their place of residence. BCE Lab does not guarantee service availability in any specific country or region.'}
          </p>
        </section>
      </div>

      <div className="mt-12">
        <DisclaimerBanner />
      </div>
    </div>
  )
}
