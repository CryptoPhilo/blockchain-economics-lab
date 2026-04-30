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
const SCHEDULE_PIPELINE_NAME = 'slide-pipeline';
const SCHEDULE_INTERVAL_MIN = 5;
const SCHEDULE_INTERVAL_MAX = 1440;

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
    scheduleTitle: '슬라이드 파이프라인 작동 주기',
    configMissing: 'Supabase 공개 자격증명이 빌드 시점에 인라인되지 않아 컨트롤 패널을 사용할 수 없습니다. NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY 를 설정 후 다시 생성하세요.',
    authPrompt: '관리자 이메일로 매직 링크를 받아 로그인하세요. 로그인 후 작동 주기를 변경할 수 있습니다.',
    emailPlaceholder: '관리자 이메일',
    sendMagicLink: '매직 링크 받기',
    magicLinkSent: '매직 링크를 전송했습니다. 이메일을 확인하세요.',
    magicLinkError: '매직 링크 전송 실패',
    signOut: '로그아웃',
    loggedInAs: '로그인',
    roleAdmin: '관리자 — 작동 주기 변경 가능',
    roleViewer: '권한 없음 — 보기 전용 (관리자 이메일이 아닙니다)',
    pipelineName: '파이프라인',
    intervalMinutes: '실행 주기 (분)',
    intervalHint: `5–1440 분 사이`,
    enabled: '활성화',
    lastRunAt: '최근 실행',
    updatedAt: '마지막 변경',
    updatedBy: '변경자',
    save: '저장',
    saving: '저장 중...',
    saveSuccess: '저장 완료',
    saveError: '저장 실패',
    loadError: '작동 주기 조회 실패',
    never: '아직 없음',
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
    scheduleTitle: 'Slide pipeline schedule',
    configMissing: 'Supabase public credentials were not inlined at build time, so the control panel is disabled. Set NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY and regenerate.',
    authPrompt: 'Sign in with an admin email via magic link to change the schedule.',
    emailPlaceholder: 'admin email',
    sendMagicLink: 'Send magic link',
    magicLinkSent: 'Magic link sent — check your email.',
    magicLinkError: 'Failed to send magic link',
    signOut: 'Sign out',
    loggedInAs: 'Signed in as',
    roleAdmin: 'Admin — can update schedule',
    roleViewer: 'Read-only — not on admin allowlist',
    pipelineName: 'Pipeline',
    intervalMinutes: 'Interval (minutes)',
    intervalHint: 'Between 5 and 1440 minutes',
    enabled: 'Enabled',
    lastRunAt: 'Last run',
    updatedAt: 'Last updated',
    updatedBy: 'Updated by',
    save: 'Save',
    saving: 'Saving...',
    saveSuccess: 'Saved',
    saveError: 'Save failed',
    loadError: 'Failed to load schedule',
    never: 'never',
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

function renderSchedulePanel(locale, supabaseConfig) {
  const t = STRINGS[locale];
  if (!supabaseConfig.url || !supabaseConfig.anonKey) {
    return `
  <h2>${t.scheduleTitle}</h2>
  <section class="panel" data-schedule-panel>
    <div class="panel-banner err">${escapeHtml(t.configMissing)}</div>
  </section>`;
  }

  return `
  <h2>${t.scheduleTitle}</h2>
  <section class="panel" data-schedule-panel hidden>
    <div class="panel-banner err" data-panel-error hidden></div>
    <div data-panel-signed-out hidden>
      <p class="panel-prompt">${escapeHtml(t.authPrompt)}</p>
      <form class="panel-form" data-magic-link-form>
        <input type="email" required placeholder="${escapeHtml(t.emailPlaceholder)}" data-magic-link-email />
        <button type="submit" class="btn primary">${escapeHtml(t.sendMagicLink)}</button>
      </form>
      <div class="panel-toast" data-magic-link-toast hidden></div>
    </div>
    <div data-panel-signed-in hidden>
      <div class="panel-userline">
        <span class="muted">${escapeHtml(t.loggedInAs)}:</span>
        <strong data-user-email></strong>
        <button type="button" class="btn ghost" data-sign-out>${escapeHtml(t.signOut)}</button>
      </div>
      <div class="panel-rolebanner" data-role-banner></div>
      <table class="schedule-table">
        <tbody>
          <tr><th>${escapeHtml(t.pipelineName)}</th><td><code>${SCHEDULE_PIPELINE_NAME}</code></td></tr>
          <tr>
            <th>${escapeHtml(t.intervalMinutes)}</th>
            <td>
              <input type="number" min="${SCHEDULE_INTERVAL_MIN}" max="${SCHEDULE_INTERVAL_MAX}" step="1" data-field-interval disabled />
              <span class="muted hint">${escapeHtml(t.intervalHint)}</span>
            </td>
          </tr>
          <tr>
            <th>${escapeHtml(t.enabled)}</th>
            <td><label class="switch"><input type="checkbox" data-field-enabled disabled /><span></span></label></td>
          </tr>
          <tr><th>${escapeHtml(t.lastRunAt)}</th><td data-field-last-run class="mono"></td></tr>
          <tr><th>${escapeHtml(t.updatedAt)}</th><td data-field-updated-at class="mono"></td></tr>
          <tr><th>${escapeHtml(t.updatedBy)}</th><td data-field-updated-by class="mono"></td></tr>
        </tbody>
      </table>
      <div class="panel-actions">
        <button type="button" class="btn primary" data-save disabled>${escapeHtml(t.save)}</button>
        <span class="panel-toast inline" data-save-toast hidden></span>
      </div>
    </div>
  </section>`;
}

function renderScheduleScript(locale, supabaseConfig) {
  if (!supabaseConfig.url || !supabaseConfig.anonKey) return '';
  const t = STRINGS[locale];
  const payload = {
    locale,
    supabaseUrl: supabaseConfig.url,
    supabaseAnonKey: supabaseConfig.anonKey,
    pipelineName: SCHEDULE_PIPELINE_NAME,
    minInterval: SCHEDULE_INTERVAL_MIN,
    maxInterval: SCHEDULE_INTERVAL_MAX,
    strings: {
      magicLinkSent: t.magicLinkSent,
      magicLinkError: t.magicLinkError,
      roleAdmin: t.roleAdmin,
      roleViewer: t.roleViewer,
      saving: t.saving,
      saveSuccess: t.saveSuccess,
      saveError: t.saveError,
      loadError: t.loadError,
      never: t.never,
    },
  };
  // Encode safely for inclusion inside a <script> tag — escape </ to avoid breaking the tag.
  const json = JSON.stringify(payload).replace(/<\/(script)/gi, '<\\/$1');
  return `
<script type="module">
  import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';
  const CFG = ${json};
  const sb = createClient(CFG.supabaseUrl, CFG.supabaseAnonKey, {
    auth: { detectSessionInUrl: true, persistSession: true, autoRefreshToken: true },
  });

  const panel = document.querySelector('[data-schedule-panel]');
  const errEl = panel.querySelector('[data-panel-error]');
  const outBlock = panel.querySelector('[data-panel-signed-out]');
  const inBlock = panel.querySelector('[data-panel-signed-in]');
  const userEmailEl = panel.querySelector('[data-user-email]');
  const roleBanner = panel.querySelector('[data-role-banner]');
  const intervalEl = panel.querySelector('[data-field-interval]');
  const enabledEl = panel.querySelector('[data-field-enabled]');
  const lastRunEl = panel.querySelector('[data-field-last-run]');
  const updatedAtEl = panel.querySelector('[data-field-updated-at]');
  const updatedByEl = panel.querySelector('[data-field-updated-by]');
  const saveBtn = panel.querySelector('[data-save]');
  const saveToast = panel.querySelector('[data-save-toast]');
  const linkForm = panel.querySelector('[data-magic-link-form]');
  const linkEmail = panel.querySelector('[data-magic-link-email]');
  const linkToast = panel.querySelector('[data-magic-link-toast]');

  let isAdmin = false;
  let originalRow = null;

  panel.hidden = false;

  function fmtDate(value) {
    if (!value) return CFG.strings.never;
    try {
      return new Date(value).toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
    } catch (e) {
      return String(value);
    }
  }

  function showError(msg) {
    if (!msg) { errEl.hidden = true; errEl.textContent = ''; return; }
    errEl.textContent = msg;
    errEl.hidden = false;
  }

  function showToast(el, msg, kind) {
    if (!el) return;
    el.textContent = msg;
    el.className = 'panel-toast' + (el.classList.contains('inline') ? ' inline' : '') + ' ' + (kind || '');
    el.hidden = false;
    if (kind !== 'err') {
      setTimeout(() => { el.hidden = true; }, 4000);
    }
  }

  async function checkAdmin(email) {
    const { data, error } = await sb
      .from('admin_emails')
      .select('email')
      .ilike('email', email)
      .maybeSingle();
    if (error) return false;
    return Boolean(data);
  }

  async function loadSchedule() {
    const { data, error } = await sb
      .from('pipeline_schedules')
      .select('pipeline_name, interval_minutes, enabled, last_run_at, updated_at, updated_by')
      .eq('pipeline_name', CFG.pipelineName)
      .maybeSingle();
    if (error) {
      showError(CFG.strings.loadError + ': ' + error.message);
      return;
    }
    if (!data) {
      showError(CFG.strings.loadError + ' (no row for ' + CFG.pipelineName + ')');
      return;
    }
    originalRow = data;
    intervalEl.value = data.interval_minutes;
    enabledEl.checked = !!data.enabled;
    lastRunEl.textContent = fmtDate(data.last_run_at);
    updatedAtEl.textContent = fmtDate(data.updated_at);
    updatedByEl.textContent = data.updated_by || '';
  }

  function applyRole(adminFlag) {
    isAdmin = adminFlag;
    roleBanner.textContent = adminFlag ? CFG.strings.roleAdmin : CFG.strings.roleViewer;
    roleBanner.className = 'panel-rolebanner ' + (adminFlag ? 'ok' : 'warn');
    intervalEl.disabled = !adminFlag;
    enabledEl.disabled = !adminFlag;
    saveBtn.disabled = !adminFlag;
  }

  async function renderSession(session) {
    showError('');
    if (!session) {
      outBlock.hidden = false;
      inBlock.hidden = true;
      return;
    }
    outBlock.hidden = true;
    inBlock.hidden = false;
    userEmailEl.textContent = session.user?.email || '';
    applyRole(false);
    await loadSchedule();
    const adminFlag = await checkAdmin(session.user?.email || '');
    applyRole(adminFlag);
  }

  linkForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = (linkEmail.value || '').trim();
    if (!email) return;
    showToast(linkToast, '...', '');
    const { error } = await sb.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.href },
    });
    if (error) {
      showToast(linkToast, CFG.strings.magicLinkError + ': ' + error.message, 'err');
    } else {
      showToast(linkToast, CFG.strings.magicLinkSent, 'ok');
    }
  });

  panel.querySelector('[data-sign-out]').addEventListener('click', async () => {
    await sb.auth.signOut();
  });

  saveBtn.addEventListener('click', async () => {
    if (!isAdmin) return;
    const interval = Number(intervalEl.value);
    if (!Number.isInteger(interval) || interval < CFG.minInterval || interval > CFG.maxInterval) {
      showToast(saveToast, CFG.strings.saveError + ': interval ' + CFG.minInterval + '–' + CFG.maxInterval, 'err');
      return;
    }
    const enabled = !!enabledEl.checked;
    const session = (await sb.auth.getSession()).data.session;
    const updatedBy = session?.user?.email || 'unknown';
    saveBtn.disabled = true;
    showToast(saveToast, CFG.strings.saving, '');
    const { data, error } = await sb
      .from('pipeline_schedules')
      .update({ interval_minutes: interval, enabled, updated_by: updatedBy })
      .eq('pipeline_name', CFG.pipelineName)
      .select('pipeline_name, interval_minutes, enabled, last_run_at, updated_at, updated_by')
      .maybeSingle();
    saveBtn.disabled = false;
    if (error) {
      showToast(saveToast, CFG.strings.saveError + ': ' + error.message, 'err');
      return;
    }
    if (data) {
      originalRow = data;
      intervalEl.value = data.interval_minutes;
      enabledEl.checked = !!data.enabled;
      lastRunEl.textContent = fmtDate(data.last_run_at);
      updatedAtEl.textContent = fmtDate(data.updated_at);
      updatedByEl.textContent = data.updated_by || '';
    }
    showToast(saveToast, CFG.strings.saveSuccess, 'ok');
  });

  sb.auth.onAuthStateChange((_event, session) => { renderSession(session); });
  sb.auth.getSession().then(({ data }) => renderSession(data.session));
</script>`;
}

function renderHtml({ summary, runs, locale, source, generatedAt, days, supabaseConfig }) {
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
  .panel { background: #14171c; border: 1px solid #1f2937; border-radius: 8px; padding: 16px 20px; margin-bottom: 24px; font-size: 13px; }
  .panel-banner { padding: 10px 12px; border-radius: 6px; margin-bottom: 12px; font-size: 12px; }
  .panel-banner.err { background: #7f1d1d; color: #fecaca; }
  .panel-prompt { color: #d1d5db; font-size: 13px; margin: 0 0 10px; }
  .panel-form { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  .panel-form input[type=email] { flex: 1 1 240px; min-width: 200px; padding: 8px 10px; background: #0b0d10; color: inherit; border: 1px solid #374151; border-radius: 6px; font-size: 13px; }
  .panel-userline { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
  .panel-rolebanner { padding: 6px 10px; border-radius: 6px; margin-bottom: 12px; font-size: 12px; display: inline-block; }
  .panel-rolebanner.ok { background: #064e3b; color: #34d399; }
  .panel-rolebanner.warn { background: #78350f; color: #fbbf24; }
  .panel-actions { display: flex; gap: 12px; align-items: center; margin-top: 12px; }
  .schedule-table { width: auto; min-width: 320px; }
  .schedule-table th { width: 40%; text-transform: none; font-size: 13px; color: #9ca3af; font-weight: 500; }
  .schedule-table td { font-size: 13px; }
  .schedule-table input[type=number] { width: 100px; padding: 6px 8px; background: #0b0d10; color: inherit; border: 1px solid #374151; border-radius: 6px; font-size: 13px; }
  .schedule-table .hint { margin-left: 8px; font-size: 11px; }
  .switch input { accent-color: #34d399; transform: scale(1.2); }
  .btn { padding: 8px 14px; border-radius: 6px; border: 1px solid #374151; background: #1f2937; color: #e5e7eb; font-size: 13px; cursor: pointer; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn.primary { background: #2563eb; border-color: #2563eb; color: #fff; }
  .btn.primary:disabled { background: #1e3a8a; border-color: #1e3a8a; }
  .btn.ghost { background: transparent; }
  .panel-toast { display: block; margin-top: 8px; padding: 6px 10px; border-radius: 6px; font-size: 12px; background: #1f2937; }
  .panel-toast.inline { display: inline-block; margin: 0; }
  .panel-toast.ok { background: #064e3b; color: #34d399; }
  .panel-toast.err { background: #7f1d1d; color: #fca5a5; }
  @media (prefers-color-scheme: light) {
    body { background: #f9fafb; color: #111827; }
    .card, ul.kv li, .panel { background: #fff; border-color: #e5e7eb; }
    h2 { color: #6b7280; border-color: #e5e7eb; }
    th { color: #6b7280; }
    td.mono { color: #374151; }
    .panel-form input[type=email], .schedule-table input[type=number] { background: #fff; color: #111827; border-color: #d1d5db; }
    .btn { background: #f3f4f6; border-color: #d1d5db; color: #111827; }
    .panel-toast { background: #f3f4f6; color: #374151; }
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
${renderSchedulePanel(locale, supabaseConfig)}

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
${renderScheduleScript(locale, supabaseConfig)}
</body>
</html>`;
}

function loadSupabasePublicConfig() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';
  return { url, anonKey };
}

async function main() {
  loadDotEnv();
  const { days } = parseArgs();
  const supabaseConfig = loadSupabasePublicConfig();
  if (!supabaseConfig.url || !supabaseConfig.anonKey) {
    console.warn('[snapshot] NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY missing — schedule control panel will render in disabled state.');
  }
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
    renderHtml({ summary, runs, locale: 'ko', source, generatedAt, days, supabaseConfig }),
  );
  fs.writeFileSync(
    path.join(OUTPUT_DIR, 'pipeline-ops-dashboard.en.html'),
    renderHtml({ summary, runs, locale: 'en', source, generatedAt, days, supabaseConfig }),
  );

  console.log(`[snapshot] source=${source} runs=${runs.length} done=${summary.done} stale=${summary.stale}`);
  console.log(`[snapshot] wrote: ${path.relative(REPO_ROOT, OUTPUT_DIR)}/pipeline-ops-dashboard.{ko,en}.html`);
}

main().catch((err) => {
  console.error('[snapshot] fatal:', err);
  process.exit(1);
});
