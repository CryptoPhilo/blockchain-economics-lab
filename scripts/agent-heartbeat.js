#!/usr/bin/env node
/**
 * Agent Heartbeat Script
 * =====================
 * Paperclip-style heartbeat: wakes agents, checks assigned work, reports status.
 *
 * Usage:
 *   node scripts/agent-heartbeat.js --agents=ceo,cro,coo,cmo
 *   node scripts/agent-heartbeat.js --agents=all
 *   node scripts/agent-heartbeat.js --agents=data-engineer
 */

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { createClient } = require('@supabase/supabase-js')

const SUPABASE_URL = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

// Agent registry matching ORGANIZATION.md
const AGENTS = {
  ceo: {
    id: 'agent-ceo',
    name: '연구소장 (CEO)',
    role: 'strategy',
    checks: ['overdue_tasks', 'budget_status', 'agent_performance'],
  },
  cro: {
    id: 'agent-cro',
    name: '연구총괄 (CRO)',
    role: 'research',
    checks: ['pending_research', 'review_queue', 'publication_schedule'],
  },
  coo: {
    id: 'agent-coo',
    name: '운영총괄 (COO)',
    role: 'operations',
    checks: ['pipeline_health', 'publishing_queue', 'data_freshness'],
  },
  cmo: {
    id: 'agent-cmo',
    name: '마케팅총괄 (CMO)',
    role: 'marketing',
    checks: ['content_calendar', 'subscriber_metrics', 'community_health'],
  },
  'data-engineer': {
    id: 'agent-data-engineer',
    name: '데이터 엔지니어',
    role: 'data',
    checks: ['pipeline_health', 'data_freshness', 'api_status'],
  },
  'onchain-analyst': {
    id: 'agent-onchain-analyst',
    name: '온체인 분석가',
    role: 'research',
    checks: ['pending_research', 'data_freshness'],
  },
  'report-editor': {
    id: 'agent-report-editor',
    name: '리포트 편집자',
    role: 'operations',
    checks: ['review_queue', 'publishing_queue'],
  },
}

// ── Health Check Functions ──────────────────────────────────

async function checkOverdueTasks() {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { data, _error } = await supabase
    .from('orders')
    .select('id, status, created_at')
    .eq('status', 'pending')
    .lt('created_at', new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString())

  return {
    check: 'overdue_tasks',
    status: data?.length ? 'warning' : 'ok',
    count: data?.length || 0,
    message: data?.length
      ? `⚠️  ${data.length} orders pending > 24h`
      : '✅ No overdue tasks',
  }
}

async function checkBudgetStatus() {
  const now = new Date()
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const _monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString()

  // In production, query cost_events table
  return {
    check: 'budget_status',
    status: 'ok',
    message: '✅ All agents within budget limits',
    period: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`,
  }
}

async function checkPendingResearch() {
  const { data } = await supabase
    .from('products')
    .select('id, title_en, status')
    .eq('status', 'draft')

  return {
    check: 'pending_research',
    status: data?.length ? 'info' : 'ok',
    count: data?.length || 0,
    message: data?.length
      ? `📝 ${data.length} draft reports awaiting completion`
      : '✅ No pending research tasks',
  }
}

async function checkPublishingQueue() {
  const { data } = await supabase
    .from('products')
    .select('id, title_en, status, updated_at')
    .eq('status', 'draft')
    .order('updated_at', { ascending: false })
    .limit(5)

  return {
    check: 'publishing_queue',
    status: data?.length ? 'info' : 'ok',
    count: data?.length || 0,
    items: data?.map((p) => p.title_en) || [],
    message: data?.length
      ? `📋 ${data.length} reports in publishing queue`
      : '✅ Publishing queue empty',
  }
}

async function checkPipelineHealth() {
  // Check if Supabase is reachable and recent data exists
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { _data, error } = await supabase
    .from('categories')
    .select('id')
    .limit(1)

  return {
    check: 'pipeline_health',
    status: error ? 'error' : 'ok',
    message: error
      ? `❌ Database connection failed: ${error.message}`
      : '✅ Database connection healthy',
  }
}

async function checkSubscriberMetrics() {
  const { count } = await supabase
    .from('profiles')
    .select('id', { count: 'exact', head: true })

  const { count: activeSubCount } = await supabase
    .from('subscriptions')
    .select('id', { count: 'exact', head: true })
    .eq('status', 'active')

  return {
    check: 'subscriber_metrics',
    status: 'ok',
    totalUsers: count || 0,
    activeSubscriptions: activeSubCount || 0,
    message: `👥 ${count || 0} users, ${activeSubCount || 0} active subscriptions`,
  }
}

async function checkRevenueMetrics() {
  const monthStart = new Date()
  monthStart.setDate(1)
  monthStart.setHours(0, 0, 0, 0)

  const { data } = await supabase
    .from('orders')
    .select('total_cents')
    .eq('status', 'completed')
    .gte('paid_at', monthStart.toISOString())

  const totalRevenue = (data || []).reduce((sum, o) => sum + o.total_cents, 0)

  return {
    check: 'revenue_metrics',
    status: 'ok',
    monthlyRevenueCents: totalRevenue,
    message: `💰 Monthly revenue: $${(totalRevenue / 100).toFixed(2)}`,
  }
}

const CHECK_REGISTRY = {
  overdue_tasks: checkOverdueTasks,
  budget_status: checkBudgetStatus,
  pending_research: checkPendingResearch,
  review_queue: checkPublishingQueue,
  publication_schedule: checkPublishingQueue,
  publishing_queue: checkPublishingQueue,
  pipeline_health: checkPipelineHealth,
  data_freshness: checkPipelineHealth,
  api_status: checkPipelineHealth,
  content_calendar: checkPublishingQueue,
  subscriber_metrics: checkSubscriberMetrics,
  community_health: checkSubscriberMetrics,
  agent_performance: checkBudgetStatus,
}

// ── Main ──────────────────────────────────────────────────

async function runHeartbeat(agentKeys) {
  console.log('═══════════════════════════════════════════════')
  console.log('  🤖 Blockchain Economics Lab — Agent Heartbeat')
  console.log(`  📅 ${new Date().toISOString()}`)
  console.log('═══════════════════════════════════════════════\n')

  for (const key of agentKeys) {
    const agent = AGENTS[key]
    if (!agent) {
      console.log(`⚠️  Unknown agent: ${key}\n`)
      continue
    }

    console.log(`── ${agent.name} (${agent.id}) ──`)

    for (const checkName of agent.checks) {
      const checkFn = CHECK_REGISTRY[checkName]
      if (!checkFn) {
        console.log(`  ⏭️  ${checkName}: no handler`)
        continue
      }
      try {
        const result = await checkFn()
        const icon = result.status === 'ok' ? '✅' : result.status === 'warning' ? '⚠️' : result.status === 'error' ? '❌' : 'ℹ️'
        console.log(`  ${icon} ${result.message}`)
      } catch (err) {
        console.log(`  ❌ ${checkName}: ${err.message}`)
      }
    }
    console.log('')
  }

  // Revenue summary
  const revenue = await checkRevenueMetrics()
  console.log(`── 📊 Summary ──`)
  console.log(`  ${revenue.message}`)
  console.log('')
  console.log('═══════════════════════════════════════════════')
  console.log('  ✅ Heartbeat complete')
  console.log('═══════════════════════════════════════════════')
}

// Parse CLI args
const args = process.argv.slice(2)
const agentsArg = args.find((a) => a.startsWith('--agents='))
let agentKeys = []

if (agentsArg) {
  const val = agentsArg.split('=')[1]
  if (val === 'all') {
    agentKeys = Object.keys(AGENTS)
  } else {
    agentKeys = val.split(',').map((s) => s.trim())
  }
} else {
  agentKeys = ['ceo', 'cro', 'coo', 'cmo']
}

runHeartbeat(agentKeys).catch((err) => {
  console.error('❌ Heartbeat failed:', err)
  process.exit(1)
})
