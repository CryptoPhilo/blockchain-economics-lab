'use client'

import { useState } from 'react'
import { useTranslations, useLocale } from 'next-intl'
import { createClient } from '@/lib/supabase-client'

/**
 * OPS-011-T07: /auth page redesign
 *
 * Split-layout with login form on left and membership benefits on right.
 * Supports: email/password + Google OAuth + GitHub OAuth
 * Includes optional referral_code field for member referrals (Phase 4).
 */

export default function AuthPage() {
  const t = useTranslations('common')
  const locale = useLocale()
  const isKo = locale === 'ko'

  const [mode, setMode] = useState<'signin' | 'signup'>('signup')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [referralCode, setReferralCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState<'success' | 'error'>('error')

  const supabase = createClient()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setMessage('')

    try {
      if (mode === 'signup') {
        const { error } = await supabase.auth.signUp({
          email,
          password,
          options: {
            emailRedirectTo: `${window.location.origin}/${locale}/dashboard`,
            data: {
              referral_code: referralCode || undefined,
              locale,
            },
          },
        })
        if (error) throw error
        setMessageType('success')
        setMessage(isKo ? '확인 이메일을 보냈습니다! 이메일을 확인해주세요.' : 'Check your email for a confirmation link!')
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
        window.location.href = `/${locale}/dashboard`
      }
    } catch (err) {
      setMessageType('error')
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      setMessage((err as any).message)
    } finally {
      setLoading(false)
    }
  }

  async function handleOAuth(provider: 'google' | 'github') {
    setLoading(true)
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: `${window.location.origin}/${locale}/dashboard`,
      },
    })
    if (error) {
      setMessageType('error')
      setMessage(error.message)
      setLoading(false)
    }
  }

  const benefits = isKo
    ? [
        { icon: '📊', text: '전체 등급표 열람' },
        { icon: '📄', text: 'Executive Summary 무제한 다운로드' },
        { icon: '📈', text: '포트폴리오 추적 (5개 프로젝트)' },
        { icon: '🔗', text: '추천 코드 발급 & 리워드' },
        { icon: '📋', text: '개인 대시보드 & 구매 이력' },
        { icon: '🎁', text: '첫 구매 20% 할인 쿠폰' },
      ]
    : [
        { icon: '📊', text: 'Full maturity score rankings' },
        { icon: '📄', text: 'Unlimited Executive Summary downloads' },
        { icon: '📈', text: 'Portfolio tracking (5 projects)' },
        { icon: '🔗', text: 'Referral code & rewards' },
        { icon: '📋', text: 'Personal dashboard & order history' },
        { icon: '🎁', text: '20% off your first purchase' },
      ]

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-6 py-16">
      <div className="max-w-4xl w-full grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-center">

        {/* Left: Auth Form */}
        <div className="order-2 lg:order-1">
          <div className="text-center lg:text-left mb-8">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-xl mx-auto lg:mx-0 mb-4">
              B
            </div>
            <h1 className="text-2xl font-bold">
              {mode === 'signin'
                ? t('signIn')
                : (isKo ? '무료 회원 가입' : 'Create Free Account')}
            </h1>
            <p className="text-gray-500 text-sm mt-2">
              {mode === 'signin'
                ? 'Blockchain Economics Lab'
                : (isKo ? '5분이면 시작합니다' : 'Get started in under 5 minutes')}
            </p>
          </div>

          {/* Social Login Buttons */}
          <div className="space-y-3 mb-6">
            <button
              onClick={() => handleOAuth('google')}
              disabled={loading}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-white font-medium transition-all disabled:opacity-50"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              {isKo ? 'Google로 계속하기' : 'Continue with Google'}
            </button>

            <button
              onClick={() => handleOAuth('github')}
              disabled={loading}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-white font-medium transition-all disabled:opacity-50"
            >
              <svg className="w-5 h-5" fill="white" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
              </svg>
              {isKo ? 'GitHub로 계속하기' : 'Continue with GitHub'}
            </button>
          </div>

          {/* Divider */}
          <div className="flex items-center gap-3 mb-6">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-xs text-gray-500 uppercase">{isKo ? '또는' : 'or'}</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          {/* Email/Password Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={isKo ? '이메일 주소' : 'Email address'}
              required
              className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/25 transition-all"
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={isKo ? '비밀번호 (6자 이상)' : 'Password (6+ characters)'}
              required
              minLength={6}
              className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/25 transition-all"
            />

            {/* Referral code field (signup only) */}
            {mode === 'signup' && (
              <input
                type="text"
                value={referralCode}
                onChange={(e) => setReferralCode(e.target.value)}
                placeholder={isKo ? '추천 코드 (선택)' : 'Referral code (optional)'}
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/25 transition-all"
              />
            )}

            {message && (
              <p className={`text-sm ${messageType === 'success' ? 'text-green-400' : 'text-red-400'}`}>
                {message}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-600/50 text-white font-semibold rounded-xl transition-all shadow-lg shadow-indigo-500/25"
            >
              {loading
                ? t('loading')
                : mode === 'signin'
                  ? t('signIn')
                  : (isKo ? '무료 가입하기' : 'Sign Up Free')}
            </button>
          </form>

          {/* Mode toggle */}
          <div className="mt-6 text-center">
            <button
              onClick={() => { setMode(mode === 'signin' ? 'signup' : 'signin'); setMessage('') }}
              className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              {mode === 'signin'
                ? (isKo ? '계정이 없으신가요? 무료 가입' : "Don't have an account? Sign up free")
                : (isKo ? '이미 계정이 있으신가요? 로그인' : 'Already have an account? Sign in')}
            </button>
          </div>
        </div>

        {/* Right: Benefits Sidebar */}
        <div className="order-1 lg:order-2">
          <div className="p-8 rounded-2xl bg-gradient-to-br from-indigo-500/5 to-purple-500/5 border border-indigo-500/10">
            <h2 className="text-xl font-bold text-white mb-2">
              {isKo ? '무료 회원 혜택' : 'Free Member Benefits'}
            </h2>
            <p className="text-sm text-gray-400 mb-6">
              {isKo
                ? '가입 즉시 모든 무료 기능을 이용하세요'
                : 'Get instant access to all free features'}
            </p>

            <div className="space-y-4">
              {benefits.map((b, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-lg">{b.icon}</span>
                  <span className="text-sm text-gray-300">{b.text}</span>
                </div>
              ))}
            </div>

            {/* Social proof */}
            <div className="mt-8 pt-6 border-t border-white/5">
              <div className="flex items-center gap-3">
                <div className="flex -space-x-2">
                  {['bg-indigo-500', 'bg-purple-500', 'bg-blue-500', 'bg-green-500'].map((bg, i) => (
                    <div key={i} className={`w-8 h-8 rounded-full ${bg} border-2 border-gray-950 flex items-center justify-center text-white text-xs font-bold`}>
                      {String.fromCharCode(65 + i)}
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-500">
                  {isKo
                    ? '전문 리서처들이 이용하고 있습니다'
                    : 'Trusted by professional researchers'}
                </p>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}
