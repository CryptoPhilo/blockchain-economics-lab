import { randomBytes } from 'crypto'
import type { SupabaseClient } from '@supabase/supabase-js'

export type YouTubeMembershipStatus = 'pending' | 'active' | 'inactive' | 'expired' | 'error'

export interface YouTubeMembershipLink {
  id: string
  user_id: string
  youtube_channel_id: string
  youtube_channel_title?: string | null
  youtube_channel_url?: string | null
  verification_code: string
  status: YouTubeMembershipStatus
  membership_level_id?: string | null
  membership_level_name?: string | null
  member_since?: string | null
  last_verified_at?: string | null
  access_expires_at?: string | null
  last_error?: string | null
  created_at?: string
  updated_at?: string
}

interface ResolvedYouTubeChannel {
  id: string
  title: string | null
  url: string
  description: string
}

interface MembershipVerificationResult {
  isMember: boolean
  levelId: string | null
  levelName: string | null
  memberSince: string | null
}

const YOUTUBE_API_BASE_URL = 'https://www.googleapis.com/youtube/v3'
const GOOGLE_OAUTH_TOKEN_URL = 'https://oauth2.googleapis.com/token'
const ACCESS_TTL_DAYS = 7

function getPublicApiKey() {
  return process.env.YOUTUBE_API_KEY || process.env.NEXT_PUBLIC_YOUTUBE_API_KEY || ''
}

function getCreatorOAuthConfig() {
  return {
    clientId: process.env.YOUTUBE_MEMBERS_OAUTH_CLIENT_ID || process.env.YOUTUBE_OAUTH_CLIENT_ID || '',
    clientSecret: process.env.YOUTUBE_MEMBERS_OAUTH_CLIENT_SECRET || process.env.YOUTUBE_OAUTH_CLIENT_SECRET || '',
    refreshToken: process.env.YOUTUBE_MEMBERS_REFRESH_TOKEN || process.env.YOUTUBE_OAUTH_REFRESH_TOKEN || '',
  }
}

export function isYouTubeMembershipConfigured() {
  const oauth = getCreatorOAuthConfig()
  return Boolean(getPublicApiKey() && oauth.clientId && oauth.clientSecret && oauth.refreshToken)
}

export function hasActiveYouTubeMembership(link: YouTubeMembershipLink | null | undefined) {
  if (!link || link.status !== 'active') return false
  if (!link.access_expires_at) return false
  return new Date(link.access_expires_at).getTime() > Date.now()
}

export async function getUserYouTubeMembershipLink(
  supabase: SupabaseClient,
  userId: string,
): Promise<YouTubeMembershipLink | null> {
  const { data, error } = await supabase
    .from('youtube_membership_links')
    .select('*')
    .eq('user_id', userId)
    .maybeSingle()

  if (error) throw error
  return data as YouTubeMembershipLink | null
}

export async function userHasActiveYouTubeMembership(supabase: SupabaseClient, userId: string) {
  const link = await getUserYouTubeMembershipLink(supabase, userId)
  return hasActiveYouTubeMembership(link)
}

export async function startYouTubeMembershipLink(
  supabase: SupabaseClient,
  userId: string,
  channelInput: string,
) {
  if (!isYouTubeMembershipConfigured()) {
    throw new Error('YouTube membership verification is not configured')
  }

  const channel = await resolveYouTubeChannel(channelInput)
  const verificationCode = `BCELAB-${randomBytes(4).toString('hex').toUpperCase()}`
  const now = new Date().toISOString()

  const { data, error } = await supabase
    .from('youtube_membership_links')
    .upsert({
      user_id: userId,
      youtube_channel_id: channel.id,
      youtube_channel_title: channel.title,
      youtube_channel_url: channel.url,
      verification_code: verificationCode,
      status: 'pending',
      membership_level_id: null,
      membership_level_name: null,
      member_since: null,
      last_verified_at: null,
      access_expires_at: null,
      last_error: null,
      updated_at: now,
    }, { onConflict: 'user_id' })
    .select('*')
    .single()

  if (error) throw error
  return data as YouTubeMembershipLink
}

export async function verifyYouTubeMembershipLink(supabase: SupabaseClient, userId: string) {
  const link = await getUserYouTubeMembershipLink(supabase, userId)
  if (!link) throw new Error('No YouTube channel is linked')

  const channel = await resolveYouTubeChannel(link.youtube_channel_id)
  if (!channel.description.includes(link.verification_code)) {
    await markLinkError(supabase, userId, 'pending', 'Verification code was not found in the channel description')
    throw new Error('Verification code was not found in the channel description')
  }

  return refreshYouTubeMembershipLink(supabase, userId)
}

export async function refreshYouTubeMembershipLink(supabase: SupabaseClient, userId: string) {
  if (!isYouTubeMembershipConfigured()) {
    throw new Error('YouTube membership verification is not configured')
  }

  const link = await getUserYouTubeMembershipLink(supabase, userId)
  if (!link) throw new Error('No YouTube channel is linked')

  const membership = await fetchCreatorMembershipForChannel(link.youtube_channel_id)
  const now = new Date()
  const expiresAt = new Date(now.getTime() + ACCESS_TTL_DAYS * 24 * 60 * 60 * 1000)
  const nextStatus: YouTubeMembershipStatus = membership.isMember ? 'active' : 'inactive'
  const lastError = membership.isMember ? null : 'This channel is not an active paid member of the BCELAB YouTube channel'

  const { data, error } = await supabase
    .from('youtube_membership_links')
    .update({
      status: nextStatus,
      membership_level_id: membership.levelId,
      membership_level_name: membership.levelName,
      member_since: membership.memberSince,
      last_verified_at: now.toISOString(),
      access_expires_at: membership.isMember ? expiresAt.toISOString() : null,
      last_error: lastError,
      updated_at: now.toISOString(),
    })
    .eq('user_id', userId)
    .select('*')
    .single()

  if (error) throw error
  return data as YouTubeMembershipLink
}

async function markLinkError(
  supabase: SupabaseClient,
  userId: string,
  status: YouTubeMembershipStatus,
  message: string,
) {
  await supabase
    .from('youtube_membership_links')
    .update({
      status,
      last_error: message,
      updated_at: new Date().toISOString(),
    })
    .eq('user_id', userId)
}

async function resolveYouTubeChannel(input: string): Promise<ResolvedYouTubeChannel> {
  const parsed = parseYouTubeChannelInput(input)
  const apiKey = getPublicApiKey()
  if (!apiKey) throw new Error('YouTube API key is not configured')

  const params = new URLSearchParams({ part: 'snippet', key: apiKey })
  if (parsed.channelId) params.set('id', parsed.channelId)
  else if (parsed.handle) params.set('forHandle', parsed.handle)
  else throw new Error('Enter a YouTube channel ID, @handle, or /channel/ URL')

  const payload = await fetchYouTubeJson(`${YOUTUBE_API_BASE_URL}/channels?${params.toString()}`)
  const items = Array.isArray(payload.items) ? payload.items : []
  const first = items[0] as Record<string, unknown> | undefined
  if (!first || typeof first.id !== 'string') {
    throw new Error('YouTube channel could not be found')
  }

  const snippet = isRecord(first.snippet) ? first.snippet : {}
  const title = typeof snippet.title === 'string' ? snippet.title : null
  const description = typeof snippet.description === 'string' ? snippet.description : ''

  return {
    id: first.id,
    title,
    description,
    url: `https://www.youtube.com/channel/${first.id}`,
  }
}

function parseYouTubeChannelInput(input: string) {
  const trimmed = input.trim()
  if (!trimmed) return {}

  if (/^UC[\w-]{10,}$/i.test(trimmed)) return { channelId: trimmed }
  if (trimmed.startsWith('@')) return { handle: trimmed.slice(1) }

  try {
    const url = new URL(trimmed)
    const segments = url.pathname.split('/').filter(Boolean)
    const first = segments[0] || ''
    const second = segments[1] || ''
    if (first === 'channel' && second) return { channelId: second }
    if (first.startsWith('@')) return { handle: first.slice(1) }
  } catch {
    return { handle: trimmed.replace(/^@/, '') }
  }

  return {}
}

async function fetchCreatorMembershipForChannel(channelId: string): Promise<MembershipVerificationResult> {
  const accessToken = await fetchCreatorAccessToken()
  const params = new URLSearchParams({
    part: 'snippet',
    filterByMemberChannelId: channelId,
    maxResults: '1',
  })

  const response = await fetch(`${YOUTUBE_API_BASE_URL}/members?${params.toString()}`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      Accept: 'application/json',
    },
  })

  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(getGoogleApiErrorMessage(payload) || 'YouTube channel membership lookup failed')
  }

  const items = Array.isArray(payload.items) ? payload.items : []
  if (items.length === 0) {
    return { isMember: false, levelId: null, levelName: null, memberSince: null }
  }

  const snippet = isRecord((items[0] as Record<string, unknown>).snippet)
    ? (items[0] as Record<string, unknown>).snippet as Record<string, unknown>
    : {}
  const details = isRecord(snippet.membershipsDetails) ? snippet.membershipsDetails : {}
  const level = isRecord(details.highestAccessibleLevel) ? details.highestAccessibleLevel : {}

  return {
    isMember: true,
    levelId: typeof level.id === 'string' ? level.id : null,
    levelName: typeof level.displayName === 'string' ? level.displayName : null,
    memberSince: typeof snippet.memberSince === 'string' ? snippet.memberSince : null,
  }
}

async function fetchCreatorAccessToken() {
  const oauth = getCreatorOAuthConfig()
  if (!oauth.clientId || !oauth.clientSecret || !oauth.refreshToken) {
    throw new Error('YouTube creator OAuth credentials are not configured')
  }

  const response = await fetch(GOOGLE_OAUTH_TOKEN_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: oauth.clientId,
      client_secret: oauth.clientSecret,
      refresh_token: oauth.refreshToken,
      grant_type: 'refresh_token',
    }),
  })

  const payload = await response.json().catch(() => ({}))
  if (!response.ok || !isRecord(payload) || typeof payload.access_token !== 'string') {
    throw new Error(getGoogleApiErrorMessage(payload) || 'Could not refresh YouTube creator access token')
  }

  return payload.access_token
}

async function fetchYouTubeJson(url: string) {
  const response = await fetch(url, { headers: { Accept: 'application/json' } })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(getGoogleApiErrorMessage(payload) || 'YouTube API request failed')
  }
  return payload as Record<string, unknown>
}

function getGoogleApiErrorMessage(payload: unknown) {
  if (!isRecord(payload)) return ''
  if (!isRecord(payload.error)) return ''
  const message = payload.error.message
  return typeof message === 'string' ? message : ''
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}
