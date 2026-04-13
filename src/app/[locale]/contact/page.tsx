interface Props { params: Promise<{ locale: string }> }

export default async function ContactPage({ params }: Props) {
  const { locale } = await params
  const isKo = locale === 'ko'

  return (
    <div className="max-w-3xl mx-auto px-6 py-16">
      <h1 className="text-3xl font-bold text-white mb-2">
        {isKo ? '문의하기' : 'Contact Us'}
      </h1>
      <p className="text-sm text-gray-500 mb-10">
        {isKo
          ? 'BCE Lab 팀에 문의사항이 있으시면 아래 이메일로 연락해주세요.'
          : 'Have questions? Reach out to the BCE Lab team via the channels below.'}
      </p>

      <div className="space-y-8">
        {/* General Inquiries */}
        <div className="p-6 rounded-2xl border border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center text-indigo-400 text-lg">
              @
            </div>
            <h2 className="text-lg font-semibold text-white">
              {isKo ? '일반 문의' : 'General Inquiries'}
            </h2>
          </div>
          <p className="text-gray-400 text-sm mb-2">
            {isKo
              ? '서비스, 보고서, 구독 등 일반적인 질문에 대해 답변드립니다.'
              : 'Questions about our services, reports, or subscriptions.'}
          </p>
          <a href="mailto:hello@bcelab.xyz" className="text-indigo-400 hover:text-indigo-300 text-sm font-medium transition-colors">
            hello@bcelab.xyz
          </a>
        </div>

        {/* Research & Partnerships */}
        <div className="p-6 rounded-2xl border border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center text-purple-400 text-lg">
              &amp;
            </div>
            <h2 className="text-lg font-semibold text-white">
              {isKo ? '리서치 & 파트너십' : 'Research & Partnerships'}
            </h2>
          </div>
          <p className="text-gray-400 text-sm mb-2">
            {isKo
              ? '프로젝트 분석 의뢰, 리서치 협업, B2B 파트너십 문의.'
              : 'Custom analysis requests, research collaboration, and B2B partnerships.'}
          </p>
          <a href="mailto:research@bcelab.xyz" className="text-purple-400 hover:text-purple-300 text-sm font-medium transition-colors">
            research@bcelab.xyz
          </a>
        </div>

        {/* Legal & Privacy */}
        <div className="p-6 rounded-2xl border border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center text-emerald-400 text-lg">
              !
            </div>
            <h2 className="text-lg font-semibold text-white">
              {isKo ? '법률 & 개인정보' : 'Legal & Privacy'}
            </h2>
          </div>
          <p className="text-gray-400 text-sm mb-2">
            {isKo
              ? '이용약관, 개인정보보호정책, GDPR 데이터 요청 관련 문의.'
              : 'Terms of service, privacy policy, and GDPR data requests.'}
          </p>
          <div className="flex flex-col gap-1">
            <a href="mailto:legal@bcelab.xyz" className="text-emerald-400 hover:text-emerald-300 text-sm font-medium transition-colors">
              legal@bcelab.xyz
            </a>
            <a href="mailto:privacy@bcelab.xyz" className="text-emerald-400 hover:text-emerald-300 text-sm font-medium transition-colors">
              privacy@bcelab.xyz
            </a>
          </div>
        </div>

        {/* Response Time */}
        <div className="text-center py-6">
          <p className="text-gray-500 text-sm">
            {isKo
              ? '영업일 기준 24시간 이내에 답변드리겠습니다.'
              : 'We typically respond within 24 business hours.'}
          </p>
        </div>

        {/* Social Links */}
        <div className="p-6 rounded-2xl border border-white/10 bg-white/[0.02] text-center">
          <h2 className="text-lg font-semibold text-white mb-4">
            {isKo ? '커뮤니티' : 'Community'}
          </h2>
          <div className="flex justify-center gap-6">
            <a href="https://x.com/bcelab" target="_blank" rel="noopener noreferrer"
              className="text-gray-400 hover:text-white text-sm font-medium transition-colors">
              X (Twitter)
            </a>
            <a href="https://t.me/bcelab" target="_blank" rel="noopener noreferrer"
              className="text-gray-400 hover:text-white text-sm font-medium transition-colors">
              Telegram
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
