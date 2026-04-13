interface Props { params: Promise<{ locale: string }> }

export default async function PrivacyPage({ params }: Props) {
  const { locale } = await params
  const isKo = locale === 'ko'

  return (
    <div className="max-w-3xl mx-auto px-6 py-16">
      <h1 className="text-3xl font-bold text-white mb-2">
        {isKo ? '개인정보보호정책' : 'Privacy Policy'}
      </h1>
      <p className="text-sm text-gray-500 mb-10">
        {isKo ? '최종 업데이트: 2026년 4월 12일' : 'Last updated: April 12, 2026'}
      </p>

      <div className="space-y-8 text-gray-400 text-sm leading-relaxed">
        <section>
          <h2 className="text-lg font-semibold text-white mb-3">{isKo ? '1. 수집하는 정보' : '1. Information We Collect'}</h2>
          <p>{isKo
            ? 'BCE Lab은 서비스 제공을 위해 다음 정보를 수집합니다: 이메일 주소(뉴스레터 구독 시), 결제 정보(Stripe을 통해 처리, BCE Lab은 카드 정보를 직접 저장하지 않음), 이용 데이터(방문 페이지, 클릭 등 익명화된 분석 데이터), IP 주소(지역 기반 서비스 및 컴플라이언스 목적).'
            : 'BCE Lab collects the following information to provide our services: email address (when subscribing to our newsletter), payment information (processed via Stripe — we do not store card details directly), usage data (anonymized analytics such as pages visited and clicks), and IP address (for geo-based services and compliance purposes).'}</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-3">{isKo ? '2. 정보 사용 목적' : '2. How We Use Your Information'}</h2>
          <p>{isKo
            ? '수집된 정보는 리서치 보고서 제공, 뉴스레터 발송, 결제 처리, 서비스 개선, 법적 의무 준수를 위해 사용됩니다. 마케팅 목적의 제3자 데이터 판매는 절대 하지 않습니다.'
            : 'Collected information is used to deliver research reports, send newsletters, process payments, improve our services, and comply with legal obligations. We never sell your data to third parties for marketing purposes.'}</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-3">{isKo ? '3. 데이터 보안' : '3. Data Security'}</h2>
          <p>{isKo
            ? '모든 데이터는 암호화된 연결(TLS/SSL)을 통해 전송되며, Supabase의 Row Level Security를 적용하여 무단 접근을 방지합니다.'
            : 'All data is transmitted via encrypted connections (TLS/SSL). We use Supabase Row Level Security to prevent unauthorized access to user data.'}</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-3">{isKo ? '4. 쿠키' : '4. Cookies'}</h2>
          <p>{isKo
            ? 'BCE Lab은 인증 세션 유지와 언어 설정을 위한 필수 쿠키만 사용합니다. 광고 목적의 쿠키는 사용하지 않습니다.'
            : 'BCE Lab uses only essential cookies for maintaining authentication sessions and language preferences. We do not use advertising cookies.'}</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-3">{isKo ? '5. 사용자 권리 (GDPR)' : '5. Your Rights (GDPR)'}</h2>
          <p>{isKo
            ? '사용자는 자신의 데이터에 대한 접근, 수정, 삭제 권리를 가집니다. 뉴스레터 수신 거부는 이메일 하단의 "Unsubscribe" 링크를 통해 즉시 가능합니다. 데이터 관련 요청은 privacy@bcelab.xyz로 연락해주세요.'
            : 'You have the right to access, correct, and delete your data. You can unsubscribe from newsletters at any time using the "Unsubscribe" link at the bottom of any email. For data-related requests, contact privacy@bcelab.xyz.'}</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold text-white mb-3">{isKo ? '6. 연락처' : '6. Contact'}</h2>
          <p>{isKo
            ? '개인정보 관련 문의: privacy@bcelab.xyz'
            : 'For privacy inquiries: privacy@bcelab.xyz'}</p>
        </section>
      </div>
    </div>
  )
}
