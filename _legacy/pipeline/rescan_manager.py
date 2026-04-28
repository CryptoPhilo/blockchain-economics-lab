"""
Re-scan Manager — 제외된 프로젝트 재스캔 관리
==============================================
UNRATABLE/SCAN_ONLY로 분류되어 분석 스케줄에서 제외된 프로젝트를
재요청 시 투명성 스캐닝부터 다시 진행하여 파이프라인에 넣는 메커니즘.

3가지 트리거:
1. 수동 재요청 (Claim Your Rating / 관리자 명령)
2. 시장 변동 (시가총액 급등, 거래소 신규 상장 등)
3. 주기적 재스캔 (30일마다 SCAN_ONLY 프로젝트 자동 재점검)

Usage:
    from rescan_manager import RescanManager
    manager = RescanManager()

    # 수동 재요청
    result = manager.request_rescan('some-token')

    # 자동 재스캔 (daily pipeline에서 호출)
    auto_results = manager.auto_rescan(excluded_projects, market_data)

    # 재스캔 큐 확인
    queue = manager.get_pending_rescans()
"""

import json
import os
import time
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collectors.collector_transparency import CollectorTransparency
from collectors.collector_transparency_enhanced import EnhancedTransparencyScanner
from triage import TriageEngine


# 재스캔 설정
RESCAN_COOLDOWN_DAYS = 7         # 같은 프로젝트 재스캔 최소 간격
AUTO_RESCAN_INTERVAL_DAYS = 30   # SCAN_ONLY 자동 재스캔 주기
MARKET_CAP_SURGE_THRESHOLD = 3.0 # 시가총액 3배 이상 증가 시 자동 트리거
MAX_DAILY_RESCANS = 20           # 일일 최대 재스캔 수

# 재스캔 큐 파일
RESCAN_QUEUE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'data', 'rescan_queue.json'
)
RESCAN_HISTORY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'data', 'rescan_history.json'
)


class RescanManager:
    """
    제외된 프로젝트의 재스캔 요청을 관리하고 실행한다.
    """

    def __init__(self):
        self.scanner = CollectorTransparency()
        self.enhanced_scanner = EnhancedTransparencyScanner()
        self.engine = TriageEngine()

        # Ensure data directory exists
        os.makedirs(os.path.dirname(RESCAN_QUEUE_PATH), exist_ok=True)

        # Load queue and history
        self.queue = self._load_json(RESCAN_QUEUE_PATH, [])
        self.history = self._load_json(RESCAN_HISTORY_PATH, {})

    # ═══════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════

    def request_rescan(
        self,
        slug: str,
        reason: str = 'manual_request',
        requester: str = 'admin',
        priority: int = 1,
    ) -> Dict[str, Any]:
        """
        프로젝트 재스캔 요청.

        Args:
            slug: CoinGecko project slug
            reason: 재스캔 사유 (manual_request, claim_your_rating, market_surge, etc.)
            requester: 요청자 (admin, project_team, auto)
            priority: 우선순위 (0 = 최우선, 1 = 일반, 2 = 낮음)

        Returns:
            요청 결과 (accepted, rejected + reason)
        """
        # 쿨다운 확인
        last_scan = self.history.get(slug, {}).get('last_rescanned')
        if last_scan:
            last_date = datetime.fromisoformat(last_scan).date()
            if (date.today() - last_date).days < RESCAN_COOLDOWN_DAYS:
                days_left = RESCAN_COOLDOWN_DAYS - (date.today() - last_date).days
                return {
                    'status': 'rejected',
                    'reason': f'Cooldown: {days_left} days remaining',
                    'slug': slug,
                    'last_rescanned': last_scan,
                }

        # 이미 큐에 있는지 확인
        if any(q['slug'] == slug for q in self.queue):
            return {
                'status': 'already_queued',
                'slug': slug,
            }

        # 큐에 추가
        request = {
            'slug': slug,
            'reason': reason,
            'requester': requester,
            'priority': priority,
            'requested_at': datetime.utcnow().isoformat() + 'Z',
            'status': 'pending',
        }
        self.queue.append(request)
        self.queue.sort(key=lambda q: q['priority'])
        self._save_json(RESCAN_QUEUE_PATH, self.queue)

        return {
            'status': 'accepted',
            'slug': slug,
            'position': next(i for i, q in enumerate(self.queue) if q['slug'] == slug) + 1,
            'total_in_queue': len(self.queue),
        }

    def execute_rescans(
        self,
        market_data: Optional[Dict[str, Dict]] = None,
        max_rescans: int = MAX_DAILY_RESCANS,
    ) -> List[Dict]:
        """
        큐에 있는 재스캔 요청 실행.
        Daily pipeline Phase C 이후에 호출.

        Returns:
            실행 결과 리스트
        """
        results = []
        executed = 0

        # 큐에서 pending 항목만
        pending = [q for q in self.queue if q['status'] == 'pending']

        for request in pending[:max_rescans]:
            slug = request['slug']
            print(f"  [Rescan] Scanning {slug} (reason: {request['reason']})...")

            try:
                # 시장 데이터 가져오기
                market_token = (market_data or {}).get(slug)

                # Enhanced scan 실행 (정밀)
                scan = self.enhanced_scanner.quick_scan(slug, market_token=market_token)

                # Triage 재실행
                triage = self.engine.evaluate(
                    market_token or {'id': slug, 'symbol': slug},
                    scan
                )

                result = {
                    'slug': slug,
                    'status': 'completed',
                    'reason': request['reason'],
                    'new_transparency_score': scan.get('transparency_score', 0),
                    'new_transparency_label': scan.get('transparency_label', 'OPAQUE'),
                    'new_bce_grade': triage.bce_grade,
                    'new_report_decision': triage.report_decision,
                    'new_total_score': triage.total_score,
                    'upgraded': triage.report_decision not in ('UNRATABLE', 'SCAN_ONLY'),
                    'scanned_at': datetime.utcnow().isoformat() + 'Z',
                }

                # 이력 업데이트
                self.history[slug] = {
                    'last_rescanned': datetime.utcnow().isoformat() + 'Z',
                    'rescan_count': self.history.get(slug, {}).get('rescan_count', 0) + 1,
                    'last_result': result,
                }

                # 큐에서 제거
                request['status'] = 'completed'

                results.append(result)
                executed += 1

                if result['upgraded']:
                    print(f"    → UPGRADED: {triage.bce_grade} / {triage.report_decision}")
                else:
                    print(f"    → Still excluded: {triage.bce_grade} / {triage.report_decision}")

                time.sleep(3)  # Rate limit

            except Exception as e:
                request['status'] = 'failed'
                results.append({
                    'slug': slug,
                    'status': 'failed',
                    'error': str(e),
                })
                print(f"    → FAILED: {e}")

        # 완료/실패한 항목 큐에서 제거
        self.queue = [q for q in self.queue if q['status'] == 'pending']
        self._save_json(RESCAN_QUEUE_PATH, self.queue)
        self._save_json(RESCAN_HISTORY_PATH, self.history)

        return results

    def auto_rescan(
        self,
        excluded_projects: List[Dict],
        market_data: Dict[str, Dict],
    ) -> List[str]:
        """
        자동 재스캔 트리거 검사.
        조건 만족 시 재스캔 큐에 자동 추가.

        트리거:
        1. SCAN_ONLY 프로젝트 중 30일 경과한 것
        2. 시가총액 급등 (이전 대비 3배 이상)
        3. 거래소 신규 상장

        Returns:
            자동 큐잉된 slug 목록
        """
        auto_queued = []

        for project in excluded_projects:
            slug = project['slug']
            decision = project.get('report_decision', '')

            # Trigger 1: SCAN_ONLY 30일 경과
            if decision == 'SCAN_ONLY':
                last_scan = self.history.get(slug, {}).get('last_rescanned')
                if not last_scan:
                    # 최초 스캔이 30일+ 전이면 재스캔
                    # (실제로는 scanned_at 확인 필요)
                    pass
                else:
                    last_date = datetime.fromisoformat(last_scan).date()
                    if (date.today() - last_date).days >= AUTO_RESCAN_INTERVAL_DAYS:
                        req = self.request_rescan(slug, reason='auto_periodic', requester='auto', priority=2)
                        if req['status'] == 'accepted':
                            auto_queued.append(slug)

            # Trigger 2: 시가총액 급등
            if slug in market_data:
                current_mcap = market_data[slug].get('market_cap', 0) or 0
                prev_mcap = project.get('market_cap', 0) or 0
                if prev_mcap > 0 and current_mcap / prev_mcap >= MARKET_CAP_SURGE_THRESHOLD:
                    req = self.request_rescan(slug, reason='market_cap_surge', requester='auto', priority=0)
                    if req['status'] == 'accepted':
                        auto_queued.append(slug)

        return auto_queued

    def get_pending_rescans(self) -> List[Dict]:
        """큐에 대기 중인 재스캔 요청 반환."""
        return [q for q in self.queue if q['status'] == 'pending']

    def get_rescan_history(self, slug: str = None) -> Dict:
        """재스캔 이력 조회."""
        if slug:
            return self.history.get(slug, {})
        return self.history

    def get_stats(self) -> Dict:
        """재스캔 통계."""
        total_rescanned = sum(1 for h in self.history.values() if h.get('rescan_count', 0) > 0)
        total_upgraded = sum(
            1 for h in self.history.values()
            if h.get('last_result', {}).get('upgraded', False)
        )
        return {
            'queue_size': len(self.get_pending_rescans()),
            'total_rescanned': total_rescanned,
            'total_upgraded': total_upgraded,
            'upgrade_rate': round(total_upgraded / max(total_rescanned, 1) * 100, 1),
        }

    # ═══════════════════════════════════════════════════════
    # INTERNAL
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def _load_json(path: str, default: Any) -> Any:
        """Load JSON file or return default."""
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return default

    @staticmethod
    def _save_json(path: str, data: Any):
        """Save data to JSON file."""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"  [Rescan] Failed to save {path}: {e}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='BCE Rescan Manager')
    parser.add_argument('action', choices=['request', 'execute', 'queue', 'stats'])
    parser.add_argument('--slug', help='Project slug for rescan request')
    parser.add_argument('--reason', default='manual_request', help='Rescan reason')
    parser.add_argument('--max', type=int, default=MAX_DAILY_RESCANS, help='Max rescans')
    args = parser.parse_args()

    manager = RescanManager()

    if args.action == 'request':
        if not args.slug:
            print("ERROR: --slug required for request")
            sys.exit(1)
        result = manager.request_rescan(args.slug, reason=args.reason)
        print(json.dumps(result, indent=2))

    elif args.action == 'execute':
        results = manager.execute_rescans(max_rescans=args.max)
        print(f"\nExecuted {len(results)} rescans")
        for r in results:
            status = '✓ UPGRADED' if r.get('upgraded') else '✗ Still excluded'
            print(f"  {r['slug']}: {status}")

    elif args.action == 'queue':
        queue = manager.get_pending_rescans()
        print(f"Pending rescans: {len(queue)}")
        for q in queue:
            print(f"  [{q['priority']}] {q['slug']} — {q['reason']} ({q['requested_at']})")

    elif args.action == 'stats':
        stats = manager.get_stats()
        print(json.dumps(stats, indent=2))
