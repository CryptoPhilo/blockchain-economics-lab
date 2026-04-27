#!/usr/bin/env node
/**
 * BCE-882 — Static pipeline-ops dashboard snapshot generator.
 *
 * Produces self-contained HTML files under public/snapshots/ that can be
 * opened with file:// — no Next.js server, no API route, no login session.
 *
 * Data source priority:
 *   1. Supabase pipeline_runs (when SUPABASE_URL + SUPABASE_SERVICE_KEY set)
 *   2. Fallback fixture at src/lib/fixtures/pipeline-ops-dashboard-snapshot.json
 *
 * Usage:
 *   node scripts/generate-pipeline-ops-snapshot.mjs
 *   node scripts/generate-pipeline-ops-snapshot.mjs --days 14
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(REPO_ROOT, 'public', 'snapshots');
const FIXTURE_PATH = path.join(REPO_ROOT, 'src', 'lib', 'fixtures', 'pipeline-ops-dashboard-snapshot.json');
const ENV_PATH = path.join(REPO_ROOT, '.env.local');

const DAYS_DEFAULT = 7;
const STALE_MINUTES = 30;
const TERMINAL = new Set(['done', 'published', 'content_failed_terminal']);

function loadDotEnv() {
  if (!fs.existsSync(ENV_PATH)) return;
  for (const line of fs.readFileSync(ENV_PATH, 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue;
    const [k, ...rest] = trimmed.split('=');
    if (process.env[k.trim()] !== undefined) continue;
    let v = rest.join('=').trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
      v = v.slice(1, -1);
    }
    process.env[k.trim()] = v;
  }
}

function parseArgs() {
  const args = { days: DAYS_DEFAULT };
  const argv = process.argv.slice(2);
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--days') args.days = Number(argv[i + 1] || DAYS_DEFAULT);
  }
  return args;
}

async function fetchFromSupabase(days) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) {
    throw new Error('SUPABASE_URL/SUPABASE_SERVICE_KEY not set');
  }
  const { createClient } = await import('@supabase/supabase-js');
  const sb = createClient(url, key, { auth: { persistSession: false } });
  const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();
  const { data, error } = await sb
    .from('pipeline_runs')
    .select('id, report_type, project_slug, version, status, source_filename, retry_count, started_at, completed_at, languages_completed, error_detail')
    .gte('started_at', since)
    .order('started_at', { ascending: false })
    .limit(500);
  if (error) throw new Error(`Supabase query failed: ${error.message}`);
  return data || [];
}

function loadFixture() {
  if (!fs.existsSync(FIXTURE_PATH)) {
    throw new Error(`Fixture missing at ${FIXTURE_PATH}`);
  }
  const parsed = JSON.parse(fs.readFileSync(FIXTURE_PATH, 'utf8'));
  return Array.isArray(parsed) ? parsed : parsed.runs || [];
}

function isStale(run) {
  if (run.status !== 'processing') return false;
  if (!run.started_at) return true;
  const elapsed = (Date.now() - new Date(run.started_at).getTime()) / 60000;
  return elapsed > STALE_MINUTES;
}

function buildSummary(runs) {
  const total = runs.length;
  let done = 0;
  let processing = 0;
  let stale = 0;
  let failed = 0;
  const byStatus = {};
  const byType = { econ: 0, mat: 0, for: 0 };
  for (const r of runs) {
    byStatus[r.status] = (byStatus[r.status] || 0) + 1;
    if (byType[r.report_type] !== undefined) byType[r.report_type] += 1;
    if (r.status === 'done' || r.status === 'published') done += 1;
    else if (r.status === 'processing') {
      processing += 1;
      if (isStale(r)) stale += 1;
    } else if (!TERMINAL.has(r.status)) failed += 1;
  }
  const successRate = total === 0 ? 0 : Math.round((done / total) * 1000) / 10;
  return { total, done, processing, stale, failed, successRate, byStatus, byType };
}

const STRINGS = {
  ko: {
    title: '파이프라인 운영 스냅샷',
    subtitle: '서버 없이 file://에서 열 수 있는 정적 대시보드',
    generatedAt: '생성 시각',
    source: '데이터 출처',
    sourceSupabase: 'Supabase pipeline_runs',
    sourceFixture: 'Fixture (Supabase 자격증명 부재)',
    summaryTitle: '요약',
    total: '총 실행',
    done: '완료',
    processing: '처리 중',
    stale: 'Stale (30분 초과)',
    failed: '실패/재시도',
    successRate: '성공률',
    byTypeTitle: '유형별',
    byStatusTitle: '상태별',
    runsTitle: '최근 실행',
    cols: ['시작 시각', '유형', '프로젝트', '버전', '상태', '재시도', '진행 언어', '오류 요약'],
    none: '데이터 없음',
  },
  en: {
    title: 'Pipeline Operations Snapshot',
    subtitle: 'Static dashboard openable via file:// — no server required',
    generatedAt: 'Generated at',
    source: 'Data source',
    sourceSupabase: 'Supabase pipeline_runs',
    sourceFixture: 'Fixture (no Supabase credentials)',
    summaryTitle: 'Summary',
    total: 'Total runs',
    done: 'Done',
    processing: 'Processing',
    stale: 'Stale (>30m)',
    failed: 'Failed / retrying',
    successRate: 'Success rate',
    byTypeTitle: 'By type',
    byStatusTitle: 'By status',
    runsTitle: 'Recent runs',
    cols: ['Started', 'Type', 'Project', 'Version', 'Status', 'Retries', 'Languages', 'Error'],
    none: 'No data',
  },
};

function escapeHtml(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatLanguages(map) {
  if (!map || typeof map !== 'object') return '';
  return Object.entries(map)
    .map(([lang, status]) => `${lang}:${status}`)
    .join(', ');
}

function formatDate(value) {
  if (!value) return '';
  try {
    return new Date(value).toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  } catch {
    return String(value);
  }
}

function statusClass(status) {
  if (status === 'done' || status === 'published') return 'ok';
  if (status === 'processing') return 'warn';
  return 'err';
}

function renderHtml({ summary, runs, locale, source, generatedAt, days }) {
  const t = STRINGS[locale];
  const sourceLabel = source === 'supabase' ? t.sourceSupabase : t.sourceFixture;
  const rows = runs.length === 0
    ? `<tr><td colspan="8" class="muted">${t.none}</td></tr>`
    : runs.map((r) => `
      <tr>
        <td>${escapeHtml(formatDate(r.started_at))}</td>
        <td><span class="pill">${escapeHtml((r.report_type || '').toUpperCase())}</span></td>
        <td>${escapeHtml(r.project_slug)}</td>
        <td>${escapeHtml(r.version)}</td>
        <td><span class="status ${statusClass(r.status)}">${escapeHtml(r.status)}${isStale(r) ? ' (stale)' : ''}</span></td>
        <td>${escapeHtml(r.retry_count ?? 0)}</td>
        <td class="mono">${escapeHtml(formatLanguages(r.languages_completed))}</td>
        <td class="mono">${escapeHtml(r.error_detail || '')}</td>
      </tr>
    `).join('');

  const statusEntries = Object.entries(summary.byStatus || {}).sort((a, b) => b[1] - a[1]);
  const statusList = statusEntries.length === 0
    ? `<li class="muted">${t.none}</li>`
    : statusEntries.map(([s, c]) => `<li><code>${escapeHtml(s)}</code><span>${c}</span></li>`).join('');

  return `<!doctype html>
<html lang="${locale}">
<head>
<meta charset="utf-8">
<title>${t.title}</title>
<meta name="generator" content="BCE-882 generate-pipeline-ops-snapshot">
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; margin: 0; padding: 24px 32px; background: #0b0d10; color: #e5e7eb; }
  h1 { margin: 0 0 4px; font-size: 24px; }
  .subtitle { color: #9ca3af; margin-bottom: 24px; font-size: 13px; }
  .meta { display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; color: #9ca3af; margin-bottom: 24px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }
  .card { background: #14171c; border: 1px solid #1f2937; border-radius: 8px; padding: 16px; }
  .card .label { font-size: 11px; text-transform: uppercase; color: #9ca3af; letter-spacing: 0.04em; }
  .card .value { font-size: 28px; font-weight: 600; margin-top: 4px; }
  .card.warn .value { color: #fbbf24; }
  .card.err .value { color: #f87171; }
  .card.ok .value { color: #34d399; }
  h2 { font-size: 14px; text-transform: uppercase; color: #9ca3af; letter-spacing: 0.04em; border-bottom: 1px solid #1f2937; padding-bottom: 6px; margin: 32px 0 12px; }
  ul.kv { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; }
  ul.kv li { display: flex; justify-content: space-between; background: #14171c; border: 1px solid #1f2937; border-radius: 6px; padding: 8px 12px; font-size: 13px; }
  ul.kv code { color: #93c5fd; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #1f2937; vertical-align: top; }
  th { color: #9ca3af; text-transform: uppercase; font-size: 11px; letter-spacing: 0.04em; }
  td.mono { font-family: ui-monospace, "SF Mono", Menlo, monospace; color: #d1d5db; word-break: break-word; }
  .muted { color: #6b7280; }
  .pill { background: #1f2937; padding: 2px 8px; border-radius: 999px; font-size: 11px; }
  .status { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-family: ui-monospace, monospace; }
  .status.ok { background: #064e3b; color: #34d399; }
  .status.warn { background: #78350f; color: #fbbf24; }
  .status.err { background: #7f1d1d; color: #fca5a5; }
  @media (prefers-color-scheme: light) {
    body { background: #f9fafb; color: #111827; }
    .card, ul.kv li { background: #fff; border-color: #e5e7eb; }
    h2 { color: #6b7280; border-color: #e5e7eb; }
    th { color: #6b7280; }
    td.mono { color: #374151; }
  }
</style>
</head>
<body>
  <h1>${t.title}</h1>
  <div class="subtitle">${t.subtitle}</div>
  <div class="meta">
    <span><strong>${t.generatedAt}:</strong> ${escapeHtml(generatedAt)}</span>
    <span><strong>${t.source}:</strong> ${escapeHtml(sourceLabel)}</span>
    <span><strong>window:</strong> ${escapeHtml(days)}d</span>
  </div>

  <h2>${t.summaryTitle}</h2>
  <div class="grid">
    <div class="card"><div class="label">${t.total}</div><div class="value">${summary.total}</div></div>
    <div class="card ok"><div class="label">${t.done}</div><div class="value">${summary.done}</div></div>
    <div class="card warn"><div class="label">${t.processing}</div><div class="value">${summary.processing}</div></div>
    <div class="card err"><div class="label">${t.stale}</div><div class="value">${summary.stale}</div></div>
    <div class="card err"><div class="label">${t.failed}</div><div class="value">${summary.failed}</div></div>
    <div class="card"><div class="label">${t.successRate}</div><div class="value">${summary.successRate}%</div></div>
  </div>

  <h2>${t.byTypeTitle}</h2>
  <ul class="kv">
    <li><code>ECON</code><span>${summary.byType.econ || 0}</span></li>
    <li><code>MAT</code><span>${summary.byType.mat || 0}</span></li>
    <li><code>FOR</code><span>${summary.byType.for || 0}</span></li>
  </ul>

  <h2>${t.byStatusTitle}</h2>
  <ul class="kv">${statusList}</ul>

  <h2>${t.runsTitle}</h2>
  <table>
    <thead><tr>${t.cols.map((c) => `<th>${c}</th>`).join('')}</tr></thead>
    <tbody>${rows}</tbody>
  </table>
</body>
</html>`;
}

async function main() {
  loadDotEnv();
  const { days } = parseArgs();
  let runs;
  let source;
  try {
    runs = await fetchFromSupabase(days);
    source = 'supabase';
  } catch (err) {
    console.warn(`[snapshot] supabase unavailable, falling back to fixture: ${err.message}`);
    runs = loadFixture();
    source = 'fixture';
  }

  const summary = buildSummary(runs);
  const generatedAt = new Date().toISOString();

  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  fs.writeFileSync(
    path.join(OUTPUT_DIR, 'pipeline-ops-dashboard.snapshot.json'),
    JSON.stringify({ generatedAt, source, days, summary, runs }, null, 2),
  );
  fs.writeFileSync(
    path.join(OUTPUT_DIR, 'pipeline-ops-dashboard.ko.html'),
    renderHtml({ summary, runs, locale: 'ko', source, generatedAt, days }),
  );
  fs.writeFileSync(
    path.join(OUTPUT_DIR, 'pipeline-ops-dashboard.en.html'),
    renderHtml({ summary, runs, locale: 'en', source, generatedAt, days }),
  );

  console.log(`[snapshot] source=${source} runs=${runs.length} done=${summary.done} stale=${summary.stale}`);
  console.log(`[snapshot] wrote: ${path.relative(REPO_ROOT, OUTPUT_DIR)}/pipeline-ops-dashboard.{ko,en}.html`);
}

main().catch((err) => {
  console.error('[snapshot] fatal:', err);
  process.exit(1);
});
