interface Props { params: Promise<{ locale: string }> }

export default async function TermsPage({ params }: Props) {
  const { locale } = await params
  const isKo = locale === 'ko'

  return (
    <div className="max-w-3xl mx-auto px-6 py-16">
      <h1 className="text-3xl font-bold text-white mb-2">
        {isKo ? '이용약관' : 'Terms of Service'}
      </h1>
      <p className="text-sm text-gray-500 mb-10">
        {isKo ? '최종 업데이트: 2026년 4월 12일' : 'Last updated: April 12, 2026'}
      </p>

      <div className="space-y-8 text-gray-400 text-sm leading-relaxed">
        <section>
          <h2 className="text-lg font-semibold text-white mb-3">{isKo ? '1. 서비스 개요' : '1. Service Overview'}</h2>
          <p>{isKo
            ? 'Blockchain Economics Lab(BCE Lab, bcelab.xyz)은 AI 기반 블록체인 경제 리서치 보고서를 제공합니다. 서비스에는 단건 보고서 구매, 프로젝트 구독, 무료 뉴스레터가 포함됩니다.'
            : 'Blockchain Economics Lab (BCE Lab, bcelab.xyz) provides AI-powered blockchain economic research reports. Services include single report purchases, project subscriptions, and free newsletters.'}</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-3">{isKo ? '2. 면책 조항' : '2. Disclaimer'}</h2>
          <p>{isKo
            ? 'BCE Lab이 제공하는 모든 콘텐츠는 정보 제공 및 교육 목적으로만 작성됩니다. 금융, 투자 또는 거래 조언을 구성하지 않으며, 그렇게 해석되어서도 안 됩니다. 암호화폐 시장에는 원금 손실을 포함한 상당한 위험이 따릅니다.'
            : 'All content provided by BCE Lab is for informational and educational purposes only. It does not constitute, and should not be construed as, financial, investment, or trading advice. Cryptocurrency markets carry significant risk, including potential loss of principal.'}</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-3">{isKo ? '3. 결제 및 환불' : '3. Payments & Refunds'}</h2>
          <p>{isKo
            ? '보고서 구매 시 결제는 즉시 처리됩니다. 디지털 콘텐츠의 특성상, 다운로드/열람 후에는 환불이 불가합니다. 구독은 언제든 취소 가능하며, 현재 결제 기간 종료 시까지 서비스를 이용하실 수 있습니다.'
            : 'Payment is processed immediately upon purchase. Due to the digital nature of our content, refunds are not available after download or viewing. Subscriptions can be cancelled at any time, and service continues until the end of the current billing period.'}</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-3">{isKo ? '4. 지적 재산권' : '4. Intellectual Property'}</h2>
          <p>{isKo
            ? 'BCE Lab의 모든 보고서, 분석, 데이터 시각화는 저작권으로 보호됩니다. 구매한 보고서는 개인적 사용 목적으로만 허용되며, 재배포, 재판매, 공개 게시는 금지됩니다.'
            : 'All BCE Lab reports, analyses, and data visualizations are protected by copyright. Purchased reports are licensed for personal use only. Redistribution, resale, or public posting is prohibited.'}</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-3">{isKo ? '5. AI 생성 콘텐츠' : '5. AI-Generated Content'}</h2>
          <p>{isKo
            ? 'BCE Lab의 보고서는 AI 연구 에이전트의 도움으로 생성되며, 인간 전문가의 검수를 거칩니다. AI 생성 콘텐츠의 특성상 오류가 포함될 수 있으며, BCE Lab은 콘텐츠의 정확성에 대해 보증하지 않습니다.'
            : 'BCE Lab reports are generated with the assistance of AI research agents and undergo human expert review. Due to the nature of AI-generated content, errors may occur. BCE Lab does not guarantee the accuracy of any content.'}</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-3">{isKo ? '6. 제3자 링크' : '6. Third-Party Links'}</h2>
          <p>{isKo
            ? '본 서비스에는 제3자 웹사이트(거래소 등)로의 링크가 포함될 수 있습니다. BCE Lab은 제3자 서비스에 대해 보증하거나 책임을 지지 않습니다. 사용자는 자신의 관할권에서 관련 법규를 확인할 책임이 있습니다.'
            : 'Our service may contain links to third-party websites (such as exchanges). BCE Lab does not endorse or accept responsibility for third-party services. Users are responsible for verifying applicable regulations in their jurisdiction.'}</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-3">{isKo ? '7. 연락처' : '7. Contact'}</h2>
          <p>{isKo
            ? '이용약관 관련 문의: legal@bcelab.xyz'
            : 'For terms-related inquiries: legal@bcelab.xyz'}</p>
        </section>
      </div>
    </div>
  )
}
