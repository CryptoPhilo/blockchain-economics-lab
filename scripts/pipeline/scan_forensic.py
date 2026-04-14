"""
FOR (Forensic) Report Scanner — OPS-007

매 6시간마다 실행. CoinMarketCap에서 전체 시장 대비 변동폭이 10% 이상인 종목을 감지하고:
1. forensic_triggers 테이블에 기록
2. project_reports에 'coming_soon' 상태로 등록
3. philoskor@gmail.com에 이메일 발송

Usage:
    python scan_forensic.py                   # 실행
    python scan_forensic.py --dry-run         # 이메일/DB 없이 테스트
    python scan_forensic.py --top 200         # 상위 200개만 스캔
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests as http_requests

# ── Pipeline imports ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    FORENSIC_TRIGGERS, MARKET_BENCHMARK,
    CMC_API_KEY, CMC_RATE_LIMIT_SLEEP,
)

# ── Load .env.local ──
_env = Path(__file__).resolve().parent.parent.parent / '.env.local'
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# Re-read after env load
if not CMC_API_KEY:
    CMC_API_KEY = os.environ.get('CMC_API_KEY', '')

RELATIVE_DEVIATION_THRESHOLD = FORENSIC_TRIGGERS.get('relative_deviation_24h_pct', 10.0)
NOTIFY_EMAIL = 'philoskor@gmail.com'


# ═══════════════════════════════════════════
# CoinMarketCap API
# ═══════════════════════════════════════════

def _cmc_headers():
    return {'X-CMC_PRO_API_KEY': CMC_API_KEY, 'Accept': 'application/json'}


def fetch_cmc_listings(limit: int = 500) -> list[dict]:
    """Fetch top coins from CoinMarketCap /v1/cryptocurrency/listings/latest."""
    if not CMC_API_KEY:
        print("[ERROR] CMC_API_KEY not set. Cannot scan.")
        return []
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    params = {
        'start': 1, 'limit': limit, 'convert': 'USD',
        'sort': 'market_cap', 'sort_dir': 'desc',
    }
    try:
        r = http_requests.get(url, headers=_cmc_headers(), params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get('data', [])
    except Exception as e:
        print(f"[ERROR] CMC API call failed: {e}")
        return []


def fetch_global_metrics() -> dict:
    """Fetch global market metrics for market average calculation."""
    url = 'https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest'
    try:
        r = http_requests.get(url, headers=_cmc_headers(), timeout=30)
        r.raise_for_status()
        data = r.json().get('data', {})
        quote = data.get('quote', {}).get('USD', {})
        return {
            'total_market_cap': quote.get('total_market_cap'),
            'total_market_cap_change_24h': quote.get('total_market_cap_last_updated'),
            # BTC dominance를 활용한 시장 평균 추정
            'btc_dominance': data.get('btc_dominance'),
            'eth_dominance': data.get('eth_dominance'),
        }
    except Exception as e:
        print(f"[WARN] Global metrics fetch failed: {e}")
        return {}


def compute_market_avg(listings: list[dict]) -> float:
    """
    시장 평균 24h 변동률 계산.
    상위 20개 코인의 시가총액 가중 평균을 사용.
    """
    top = sorted(listings, key=lambda x: x.get('quote', {}).get('USD', {}).get('market_cap', 0), reverse=True)[:20]
    total_mcap = 0
    weighted_change = 0
    for coin in top:
        q = coin.get('quote', {}).get('USD', {})
        mcap = q.get('market_cap', 0) or 0
        change = q.get('percent_change_24h', 0) or 0
        total_mcap += mcap
        weighted_change += mcap * change
    if total_mcap == 0:
        return 0.0
    return weighted_change / total_mcap


# ═══════════════════════════════════════════
# Anomaly Detection
# ═══════════════════════════════════════════

def detect_anomalies(listings: list[dict], market_avg: float, threshold: float = None) -> list[dict]:
    """
    시장 평균 대비 상대 변동률이 threshold 이상인 종목 감지.
    |token_change_24h - market_avg| >= threshold
    """
    if threshold is None:
        threshold = RELATIVE_DEVIATION_THRESHOLD

    triggered = []
    for coin in listings:
        q = coin.get('quote', {}).get('USD', {})
        change_24h = q.get('percent_change_24h')
        if change_24h is None:
            continue

        deviation = abs(change_24h - market_avg)
        if deviation >= threshold:
            triggered.append({
                'cmc_id': coin.get('id'),
                'name': coin.get('name'),
                'symbol': coin.get('symbol'),
                'slug': coin.get('slug'),
                'price_usd': q.get('price'),
                'price_change_24h': change_24h,
                'market_avg_change_24h': market_avg,
                'relative_deviation': round(deviation, 2),
                'volume_24h': q.get('volume_24h'),
                'market_cap': q.get('market_cap'),
                'cmc_rank': coin.get('cmc_rank'),
                'direction': 'up' if change_24h > market_avg else 'down',
            })

    # Sort by deviation (most anomalous first)
    triggered.sort(key=lambda x: x['relative_deviation'], reverse=True)
    return triggered


# ═══════════════════════════════════════════
# Supabase Registration
# ═══════════════════════════════════════════

def _get_supabase():
    url = os.environ.get('SUPABASE_URL') or os.environ.get('NEXT_PUBLIC_SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY')
    if not url or not key:
        return None
    from supabase import create_client
    return create_client(url, key)


def register_coming_soon(triggers: list[dict], dry_run: bool = False) -> list[dict]:
    """
    감지된 종목을 Supabase에 등록:
    1. forensic_triggers 테이블에 스캔 결과 기록
    2. project_reports에 'coming_soon' 상태로 등록
    """
    if dry_run:
        print(f"[DRY RUN] Would register {len(triggers)} triggers")
        return triggers

    sb = _get_supabase()
    if not sb:
        print("[WARN] Supabase not configured — skipping DB registration")
        return triggers

    scan_ts = datetime.now(timezone.utc).isoformat()
    registered = []

    for t in triggers:
        slug = t['slug']

        # Check if already has a coming_soon or active FOR report
        existing = sb.table('project_reports').select('id, status') \
            .eq('report_type', 'forensic') \
            .filter('status', 'in', '("coming_soon","assigned","in_progress","in_review")') \
            .execute()

        # Find matching slug entries
        slug_existing = [r for r in (existing.data or [])
                         if True]  # We need project_id match

        # Get or create tracked_project
        proj = sb.table('tracked_projects').select('id').eq('slug', slug).execute()
        if not proj.data:
            # Auto-register new project
            try:
                new_proj = sb.table('tracked_projects').insert({
                    'slug': slug,
                    'name': t['name'],
                    'symbol': t['symbol'],
                    'status': 'monitoring_only',
                    'cmc_id': t.get('cmc_id'),
                }).execute()
                project_id = new_proj.data[0]['id']
                print(f"  새 프로젝트 등록: {slug} ({t['symbol']})")
            except Exception as e:
                print(f"  프로젝트 등록 실패 {slug}: {e}")
                continue
        else:
            project_id = proj.data[0]['id']

        # Check for existing coming_soon FOR report for this project
        existing_for = sb.table('project_reports').select('id') \
            .eq('project_id', project_id) \
            .eq('report_type', 'forensic') \
            .eq('status', 'coming_soon') \
            .execute()

        if existing_for.data:
            print(f"  {slug}: already has coming_soon FOR report — skip")
            continue

        # 1. Insert forensic_trigger
        trigger_data = {
            'project_id': project_id,
            'slug': slug,
            'symbol': t['symbol'],
            'scan_timestamp': scan_ts,
            'price_usd': t['price_usd'],
            'price_change_24h': t['price_change_24h'],
            'market_avg_change_24h': t['market_avg_change_24h'],
            'relative_deviation': t['relative_deviation'],
            'volume_24h': t['volume_24h'],
            'market_cap': t['market_cap'],
            'triggered': True,
            'risk_level': 'high' if t['relative_deviation'] >= 20 else 'elevated',
            'trigger_reasons': json.dumps([
                f"relative_deviation_24h: {t['relative_deviation']}% "
                f"({'↑' if t['direction'] == 'up' else '↓'} vs market avg {t['market_avg_change_24h']:.1f}%)"
            ]),
            'status': 'detected',
        }
        try:
            ft_result = sb.table('forensic_triggers').insert(trigger_data).execute()
            trigger_id = ft_result.data[0]['id'] if ft_result.data else None
        except Exception as e:
            print(f"  forensic_trigger 등록 실패 {slug}: {e}")
            continue

        # 2. Insert project_reports with coming_soon
        direction_ko = '급등' if t['direction'] == 'up' else '급락'
        trigger_reason = (
            f"24h {direction_ko} {t['price_change_24h']:+.1f}% "
            f"(시장평균 {t['market_avg_change_24h']:+.1f}%, "
            f"초과변동 {t['relative_deviation']:.1f}%)"
        )
        report_data = {
            'project_id': project_id,
            'report_type': 'forensic',
            'version': 1,
            'status': 'coming_soon',
            'trigger_reason': trigger_reason,
            'trigger_data': json.dumps(t),
            'triggered_at': scan_ts,
        }
        try:
            rpt_result = sb.table('project_reports').insert(report_data).execute()
            report_id = rpt_result.data[0]['id'] if rpt_result.data else None

            # Link trigger to report
            if trigger_id and report_id:
                sb.table('forensic_triggers').update({
                    'report_id': report_id, 'status': 'notified'
                }).eq('id', trigger_id).execute()

            t['report_id'] = report_id
            registered.append(t)
            print(f"  ✓ {slug} ({t['symbol']}): coming_soon 등록 | "
                  f"{t['price_change_24h']:+.1f}% (시장 대비 {t['relative_deviation']:.1f}%)")
        except Exception as e:
            print(f"  project_reports 등록 실패 {slug}: {e}")

    return registered


# ═══════════════════════════════════════════
# Email Notification
# ═══════════════════════════════════════════

def send_forensic_alert_email(triggers: list[dict], market_avg: float,
                               scan_time: str, dry_run: bool = False) -> dict:
    """감지된 종목 목록을 이메일로 발송."""
    if not triggers:
        return {'success': True, 'skipped': 'no triggers'}

    # Build HTML table
    rows_html = ''
    for t in triggers[:30]:  # Max 30 entries
        direction = '🔴' if t['direction'] == 'down' else '🟢'
        rows_html += f"""<tr>
          <td style="padding:8px;border-bottom:1px solid #333;color:#e5e7eb;">{t['cmc_rank']}</td>
          <td style="padding:8px;border-bottom:1px solid #333;color:white;font-weight:bold;">{t['symbol']}</td>
          <td style="padding:8px;border-bottom:1px solid #333;color:#d1d5db;">{t['name']}</td>
          <td style="padding:8px;border-bottom:1px solid #333;color:#d1d5db;">${t['price_usd']:.4f}</td>
          <td style="padding:8px;border-bottom:1px solid #333;color:{'#ef4444' if t['direction']=='down' else '#22c55e'};font-weight:bold;">
            {direction} {t['price_change_24h']:+.1f}%</td>
          <td style="padding:8px;border-bottom:1px solid #333;color:#f59e0b;font-weight:bold;">{t['relative_deviation']:.1f}%</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0f;color:#e5e7eb;padding:40px 20px;">
<div style="max-width:700px;margin:0 auto;">
  <div style="text-align:center;margin-bottom:24px;">
    <div style="display:inline-block;width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,#dc2626,#f59e0b);text-align:center;line-height:48px;color:white;font-weight:bold;font-size:20px;">⚠</div>
    <h1 style="color:white;font-size:22px;margin:16px 0 4px;">Forensic Alert — 이상 변동 감지</h1>
    <p style="color:#9ca3af;font-size:13px;">
      {scan_time} | 시장 평균 24h: {market_avg:+.1f}% | 임계값: ±{RELATIVE_DEVIATION_THRESHOLD}%
    </p>
  </div>

  <div style="background:rgba(255,255,255,0.05);border:1px solid rgba(220,38,38,0.3);border-radius:16px;padding:24px;">
    <p style="color:#f59e0b;font-size:14px;margin:0 0 16px;">
      <strong>{len(triggers)}개 종목</strong>이 시장 평균 대비 {RELATIVE_DEVIATION_THRESHOLD}% 이상 이탈했습니다.
      Gemini GEM으로 FOR 보고서 초안을 작성해 GDrive drafts/FOR/ 폴더에 업로드해주세요.
    </p>
    <table style="width:100%;border-collapse:collapse;">
      <tr>
        <th style="text-align:left;padding:8px;color:#6b7280;font-size:11px;border-bottom:2px solid #333;">#</th>
        <th style="text-align:left;padding:8px;color:#6b7280;font-size:11px;border-bottom:2px solid #333;">Symbol</th>
        <th style="text-align:left;padding:8px;color:#6b7280;font-size:11px;border-bottom:2px solid #333;">Name</th>
        <th style="text-align:left;padding:8px;color:#6b7280;font-size:11px;border-bottom:2px solid #333;">Price</th>
        <th style="text-align:left;padding:8px;color:#6b7280;font-size:11px;border-bottom:2px solid #333;">24h</th>
        <th style="text-align:left;padding:8px;color:#6b7280;font-size:11px;border-bottom:2px solid #333;">초과변동</th>
      </tr>
      {rows_html}
    </table>
  </div>

  <div style="margin-top:24px;background:rgba(255,255,255,0.03);border-radius:12px;padding:20px;">
    <h3 style="color:#9ca3af;font-size:13px;margin:0 0 8px;">📋 다음 단계</h3>
    <ol style="color:#d1d5db;font-size:13px;line-height:1.8;padding-left:20px;margin:0;">
      <li>위 종목의 FOR 보고서 초안(.md)을 작성</li>
      <li>GDrive → BCE Lab Reports → drafts → FOR 폴더에 업로드</li>
      <li>파일명: <code style="background:#1a1a2e;padding:2px 6px;border-radius:4px;">[slug]_for_v1.md</code></li>
      <li>파이프라인이 자동 감지 → 번역 → PDF 생성 → 웹사이트 게시</li>
    </ol>
  </div>

  <div style="margin-top:32px;text-align:center;">
    <p style="color:#4b5563;font-size:11px;">&copy; 2026 Blockchain Economics Lab &middot; bcelab.xyz</p>
  </div>
</div>
</body></html>"""

    # Use the existing email sender
    email_script = Path(__file__).resolve().parent.parent.parent / '.claude' / 'skills' / 'resend-email' / 'scripts' / 'send_email.py'

    # Import send_email directly
    sys.path.insert(0, str(email_script.parent))
    try:
        from send_email import send_email
        return send_email(
            to=NOTIFY_EMAIL,
            subject=f"[BCE Lab] ⚠ Forensic Alert — {len(triggers)}개 종목 이상 변동 감지",
            body=html,
            content_type='html',
            tags=[
                {'name': 'type', 'value': 'forensic_alert'},
                {'name': 'count', 'value': str(len(triggers))},
            ],
            dry_run=dry_run,
        )
    except ImportError:
        # Fallback: direct Resend API call
        api_key = os.environ.get('RESEND_API_KEY')
        if not api_key or dry_run:
            print(f"[{'DRY RUN' if dry_run else 'WARN'}] Email not sent")
            return {'success': dry_run, 'skipped': True}
        r = http_requests.post('https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={
                'from': os.environ.get('EMAIL_FROM', 'BCE Lab <onboarding@resend.dev>'),
                'to': [NOTIFY_EMAIL],
                'subject': f"[BCE Lab] ⚠ Forensic Alert — {len(triggers)}개 종목 이상 변동 감지",
                'html': html,
            }, timeout=30)
        return {'success': r.status_code in (200, 201)}


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='FOR Report Scanner — 6h anomaly detection')
    parser.add_argument('--dry-run', action='store_true', help='No DB/email, just print')
    parser.add_argument('--top', type=int, default=500, help='Number of coins to scan (default 500)')
    parser.add_argument('--threshold', type=float, default=None, help='Override deviation threshold')
    parser.add_argument('--output', type=str, help='Save results JSON to path')
    args = parser.parse_args()

    threshold = args.threshold or RELATIVE_DEVIATION_THRESHOLD
    scan_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    print(f"\n{'='*60}")
    print(f"FOR Report Scanner — {scan_time}")
    print(f"Top {args.top} coins | Threshold: ±{threshold}% vs market avg")
    print(f"{'='*60}\n")

    # Step 1: Fetch market data
    print("[1/4] CoinMarketCap 데이터 수집...")
    listings = fetch_cmc_listings(limit=args.top)
    if not listings:
        print("  ✗ 데이터 수집 실패")
        return
    print(f"  ✓ {len(listings)}개 종목 수집 완료")
    time.sleep(CMC_RATE_LIMIT_SLEEP)

    # Step 2: Compute market average
    print("[2/4] 시장 평균 변동률 계산...")
    market_avg = compute_market_avg(listings)
    print(f"  ✓ 시장 평균 24h: {market_avg:+.2f}% (상위 20개 시총가중)")

    # Step 3: Detect anomalies
    print(f"[3/4] 이상 변동 감지 (임계값: ±{threshold}%)...")
    triggered = detect_anomalies(listings, market_avg, threshold)
    print(f"  ✓ {len(triggered)}개 종목 감지")

    if triggered:
        print(f"\n  {'Rank':<6} {'Symbol':<10} {'Name':<20} {'24h':>8} {'초과변동':>10}")
        print(f"  {'─'*58}")
        for t in triggered[:20]:
            print(f"  {t['cmc_rank']:<6} {t['symbol']:<10} {t['name'][:18]:<20} "
                  f"{t['price_change_24h']:>+7.1f}% {t['relative_deviation']:>9.1f}%")
        if len(triggered) > 20:
            print(f"  ... +{len(triggered)-20}개 더")

    # Step 4: Register & notify
    print(f"\n[4/4] Supabase 등록 + 이메일 발송...")
    registered = register_coming_soon(triggered, dry_run=args.dry_run)
    print(f"  ✓ {len(registered)}개 coming_soon 등록")

    if registered:
        email_result = send_forensic_alert_email(
            registered, market_avg, scan_time, dry_run=args.dry_run)
        print(f"  ✓ 이메일: {'발송 완료' if email_result.get('success') else '실패'}")

    # Save results
    summary = {
        'scan_time': scan_time,
        'market_avg_24h': round(market_avg, 2),
        'threshold': threshold,
        'total_scanned': len(listings),
        'triggered_count': len(triggered),
        'registered_count': len(registered),
        'triggers': triggered[:50],  # Cap at 50 for storage
    }

    output_path = args.output or f'/sessions/amazing-cool-davinci/scan_forensic_{datetime.now().strftime("%Y%m%d_%H%M")}.json'
    with open(output_path, 'w') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {output_path}")
    print(f"\nDONE: {len(triggered)} 감지 / {len(registered)} 등록")


if __name__ == '__main__':
    main()
