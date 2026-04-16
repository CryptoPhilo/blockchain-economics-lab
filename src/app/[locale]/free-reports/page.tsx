import LeadMagnetGate from '@/components/LeadMagnetGate'

/**
 * OPS-011-T06: Free sample reports landing page (Lead Magnets)
 *
 * Offers 3 free sample reports gated behind email collection.
 * These serve as TOFU lead magnets in the membership funnel.
 */

const FREE_SAMPLES = [
  {
    id: 'sample-econ',
    icon: '📊',
    type: 'ECON',
    color: 'from-blue-500/10 to-blue-600/5 border-blue-500/20',
    title: { en: 'Sample: Bitcoin Economic Design Analysis', ko: '샘플: 비트코인 경제 설계 분석' },
    desc: {
      en: 'A comprehensive look at Bitcoin\'s tokenomics, supply schedule, miner incentive design, and long-term value accrual mechanisms. Includes Monte Carlo scenario modeling.',
      ko: '비트코인의 토큰노믹스, 공급 일정, 채굴자 인센티브 설계, 장기 가치 축적 메커니즘에 대한 종합적 분석. 몬테카를로 시나리오 모델링 포함.',
    },
    pages: 24,
  },
  {
    id: 'sample-maturity',
    icon: '📈',
    type: 'MAT',
    color: 'from-green-500/10 to-green-600/5 border-green-500/20',
    title: { en: 'Sample: Ethereum Maturity Assessment', ko: '샘플: 이더리움 성숙도 평가' },
    desc: {
      en: 'BCE Maturity Score™ deep-dive on Ethereum. 7-axis analysis covering technology, business model, tokenomics, governance, community, compliance, and narrative health.',
      ko: '이더리움에 대한 BCE Maturity Score™ 심층 분석. 기술, 비즈니스 모델, 토큰노믹스, 거버넌스, 커뮤니티, 규정 준수, 내러티브 건강도 7축 분석.',
    },
    pages: 18,
  },
  {
    id: 'sample-forensic',
    icon: '🔍',
    type: 'FOR',
    color: 'from-red-500/10 to-red-600/5 border-red-500/20',
    title: { en: 'Sample: DeFi Protocol Forensic Risk Report', ko: '샘플: DeFi 프로토콜 포렌식 리스크 보고서' },
    desc: {
      en: 'On-chain forensic analysis of a top DeFi protocol. Covers fund flow tracing, smart contract risk, whale movement patterns, and 5-level threat assessment methodology.',
      ko: '상위 DeFi 프로토콜의 온체인 포렌식 분석. 자금 흐름 추적, 스마트 컨트랙트 리스크, 고래 이동 패턴, 5단계 위협 평가 방법론을 다룹니다.',
    },
    pages: 16,
  },
]

export default async function FreeReportsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params
  const isKo = locale === 'ko'

  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="text-center mb-12">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-sm mb-6">
          <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
          {isKo ? '무료 리서치' : 'Free Research'}
        </div>
        <h1 className="text-4xl font-bold mb-4">
          {isKo ? '무료 샘플 리포트' : 'Free Sample Reports'}
        </h1>
        <p className="text-gray-400 max-w-xl mx-auto">
          {isKo
            ? '이메일을 입력하시면 3건의 샘플 리포트를 무료로 다운로드할 수 있습니다. 유료 보고서의 품질을 직접 확인해보세요.'
            : 'Enter your email to download 3 free sample reports. Experience the quality of our paid research firsthand.'}
        </p>
      </div>

      {/* Sample reports */}
      <div className="space-y-6">
        {FREE_SAMPLES.map((sample) => {
          const title = sample.title[locale as 'en' | 'ko'] || sample.title.en
          const desc = sample.desc[locale as 'en' | 'ko'] || sample.desc.en

          return (
            <LeadMagnetGate
              key={sample.id}
              gateId={sample.id}
              sourceId={sample.id}
              source="lead_magnet"
              locale={locale}
              variant="inline"
              teaser={
                <div className={`p-6 rounded-xl bg-gradient-to-br ${sample.color} border`}>
                  <div className="flex items-start gap-4">
                    <span className="text-3xl">{sample.icon}</span>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-mono text-gray-500">{sample.type}</span>
                        <span className="text-xs text-gray-600">·</span>
                        <span className="text-xs text-gray-500">{sample.pages} {isKo ? '페이지' : 'pages'}</span>
                      </div>
                      <h3 className="font-bold text-white text-lg mb-2">{title}</h3>
                      <p className="text-sm text-gray-400 leading-relaxed">{desc}</p>
                    </div>
                  </div>
                </div>
              }
            >
              {/* Unlocked state: show download link */}
              <div className={`p-6 rounded-xl bg-gradient-to-br ${sample.color} border`}>
                <div className="flex items-start gap-4">
                  <span className="text-3xl">{sample.icon}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-mono text-gray-500">{sample.type}</span>
                      <span className="text-xs text-gray-600">·</span>
                      <span className="text-xs text-gray-500">{sample.pages} {isKo ? '페이지' : 'pages'}</span>
                      <span className="text-xs text-green-400 ml-auto">✓ {isKo ? '잠금 해제됨' : 'Unlocked'}</span>
                    </div>
                    <h3 className="font-bold text-white text-lg mb-2">{title}</h3>
                    <p className="text-sm text-gray-400 leading-relaxed mb-4">{desc}</p>
                    <div className="flex gap-3">
                      <span className="px-4 py-2 bg-indigo-500/10 text-indigo-400 text-sm font-medium rounded-lg border border-indigo-500/20">
                        📥 {isKo ? '확인 이메일에서 다운로드 링크를 받으세요' : 'Download link will be in your confirmation email'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </LeadMagnetGate>
          )
        })}
      </div>

      {/* Bottom CTA */}
      <div className="mt-12 text-center">
        <p className="text-gray-500 text-sm mb-4">
          {isKo ? '전문 보고서가 더 필요하신가요?' : 'Need more in-depth research?'}
        </p>
        <a
          href={`/${locale}/products`}
          className="inline-flex px-6 py-3 bg-white/5 hover:bg-white/10 text-white font-medium rounded-xl border border-white/10 transition-all"
        >
          {isKo ? '전체 보고서 카탈로그 보기' : 'Browse Full Report Catalog'} →
        </a>
      </div>
    </div>
  )
}
