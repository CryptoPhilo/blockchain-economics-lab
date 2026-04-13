"""
CRO Agent — Chief Research Officer automated pipeline improvement agent.

Lifecycle:
  1. DISCOVER  — Search web for new blockchain data APIs
  2. REGISTER  — Add candidates to source registry
  3. VALIDATE  — Run comprehensive quality tests
  4. INTEGRATE — Generate collector modules for validated sources
  5. REPORT    — Produce improvement summary for C-level review

Designed to run periodically via scheduled task.
"""
import os
import sys
import json
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Add pipeline root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cro.source_registry import SourceRegistry
from cro.discover import DataSourceDiscoverer, run_discovery
from cro.validate import DataSourceValidator, run_validation
from cro.integrate import PipelineIntegrator


class CROAgent:
    """
    Chief Research Officer Agent — continuously improves the data pipeline.
    """

    def __init__(self, mode: str = "full"):
        """
        Args:
            mode: 'full' (all phases), 'discover', 'validate', 'integrate', 'report'
        """
        self.mode = mode
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.results = {
            "run_id": self.run_id,
            "mode": mode,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "phases": {},
        }

    def run(self) -> Dict:
        """Execute the CRO agent pipeline."""
        print(f"\n{'═'*70}")
        print(f"  🏢 CRO Agent — Pipeline Improvement Run #{self.run_id}")
        print(f"  Mode: {self.mode}")
        print(f"{'═'*70}\n")

        if self.mode in ("full", "discover"):
            self._phase_discover()

        if self.mode in ("full", "validate"):
            self._phase_validate()

        if self.mode in ("full", "integrate"):
            self._phase_integrate()

        # Always produce a report
        self._phase_report()

        self.results["completed_at"] = datetime.now(timezone.utc).isoformat()
        return self.results

    # ══════════════════════════════════════════════════
    # PHASE 1: DISCOVER
    # ══════════════════════════════════════════════════

    def _phase_discover(self):
        """Search for new data sources and seed known candidates."""
        print(f"\n{'─'*50}")
        print(f"📡 Phase 1: DISCOVERY")
        print(f"{'─'*50}\n")

        phase_result = {"new_candidates": 0, "seeded": 0}

        # Step 1: Seed known candidates that aren't in the registry yet
        print("Seeding known candidate sources...")
        try:
            seeded = SourceRegistry.seed_known_candidates()
            phase_result["seeded"] = seeded
            print(f"  Seeded {seeded} known candidates\n")
        except Exception as e:
            print(f"  ⚠ Seed error: {e}\n")

        # Step 2: Web search for new sources (if web search available)
        print("Searching for new data sources...")
        try:
            discovery = run_discovery()
            total = discovery.get("total_discovered", 0)
            phase_result["web_search_found"] = total

            # Register discovered candidates
            registered = 0
            for category, candidates in discovery.get("candidates", {}).items():
                for candidate in candidates:
                    try:
                        SourceRegistry.register_source(candidate)
                        registered += 1
                        SourceRegistry.log_improvement(
                            action_type="source_discovered",
                            description=f"Discovered {candidate['source_name']} ({candidate['base_url']}) via web search",
                        )
                    except Exception:
                        pass  # Likely duplicate

            phase_result["new_candidates"] = registered
            print(f"  Registered {registered} new candidates from web search\n")
        except Exception as e:
            print(f"  ⚠ Discovery error: {e}\n")
            phase_result["web_search_error"] = str(e)

        self.results["phases"]["discover"] = phase_result

    # ══════════════════════════════════════════════════
    # PHASE 2: VALIDATE
    # ══════════════════════════════════════════════════

    def _phase_validate(self):
        """Run validation tests on candidate sources."""
        print(f"\n{'─'*50}")
        print(f"🧪 Phase 2: VALIDATION")
        print(f"{'─'*50}\n")

        phase_result = {"tested": 0, "validated": 0, "rejected": 0}

        try:
            summaries = run_validation()
            phase_result["tested"] = len(summaries)
            phase_result["validated"] = sum(1 for s in summaries if s.get("passed"))
            phase_result["rejected"] = sum(1 for s in summaries if not s.get("passed"))

            phase_result["details"] = [
                {
                    "source": s.get("source_name"),
                    "passed": s.get("passed"),
                    "scores": s.get("scores", {}),
                }
                for s in summaries
            ]
        except Exception as e:
            print(f"  ⚠ Validation error: {e}\n")
            phase_result["error"] = str(e)

        self.results["phases"]["validate"] = phase_result

    # ══════════════════════════════════════════════════
    # PHASE 3: INTEGRATE
    # ══════════════════════════════════════════════════

    def _phase_integrate(self):
        """Integrate validated sources into the pipeline."""
        print(f"\n{'─'*50}")
        print(f"🔗 Phase 3: INTEGRATION")
        print(f"{'─'*50}\n")

        phase_result = {"integrated": 0, "failed": 0}

        try:
            results = PipelineIntegrator.integrate_all_validated()
            phase_result["integrated"] = sum(1 for r in results if r.get("success"))
            phase_result["failed"] = sum(1 for r in results if not r.get("success"))

            phase_result["details"] = [
                {
                    "source": r.get("source_name"),
                    "success": r.get("success"),
                    "module": r.get("module_name"),
                    "reports": r.get("target_reports", []),
                }
                for r in results
            ]
        except Exception as e:
            print(f"  ⚠ Integration error: {e}\n")
            phase_result["error"] = str(e)

        self.results["phases"]["integrate"] = phase_result

    # ══════════════════════════════════════════════════
    # PHASE 4: REPORT
    # ══════════════════════════════════════════════════

    def _phase_report(self):
        """Generate CRO improvement summary."""
        print(f"\n{'─'*50}")
        print(f"📊 Phase 4: REPORT")
        print(f"{'─'*50}\n")

        # Get current state
        status = PipelineIntegrator.get_integration_status()

        report = {
            "registry_status": status,
            "recommendations": [],
        }

        # Generate recommendations
        missing = status.get("missing_categories", [])
        if missing:
            report["recommendations"].append({
                "priority": "HIGH",
                "action": f"Add data sources for missing categories: {', '.join(missing)}",
                "impact": "Improves report depth for underserved areas",
            })

        integrated = status.get("integrated_count", 0)
        if integrated < 8:
            report["recommendations"].append({
                "priority": "MEDIUM",
                "action": "Increase data source diversity (currently {}/target 8+)".format(integrated),
                "impact": "More data sources = more robust reports",
            })

        # Check for sources that need re-validation (older than 7 days)
        all_sources = SourceRegistry.get_all_sources(status="integrated")
        stale = [s for s in all_sources if not s.get("last_test_at")]
        if stale:
            report["recommendations"].append({
                "priority": "LOW",
                "action": f"Re-validate {len(stale)} integrated sources (no recent test)",
                "impact": "Ensures continued data quality",
            })

        self.results["phases"]["report"] = report

        # Print summary
        print(f"  Registry: {status.get('total_sources', 0)} total sources")
        print(f"  Status: {json.dumps(status.get('status_distribution', {}))}")
        print(f"  Integrated: {status.get('integrated_count', 0)}")
        print(f"  Categories: {', '.join(status.get('categories_covered', []))}")
        if missing:
            print(f"  ⚠ Missing: {', '.join(missing)}")
        print(f"\n  Recommendations: {len(report['recommendations'])}")
        for rec in report["recommendations"]:
            print(f"    [{rec['priority']}] {rec['action']}")

    # ══════════════════════════════════════════════════
    # SAVE RESULTS
    # ══════════════════════════════════════════════════

    def save_results(self, output_dir: str = None) -> str:
        """Save run results to JSON file."""
        if not output_dir:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))))),
                "scan_results"
            )
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"cro_run_{self.run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Results saved: {path}")
        return path


def main():
    parser = argparse.ArgumentParser(description="CRO Agent — Pipeline Improvement")
    parser.add_argument("--mode", choices=["full", "discover", "validate", "integrate", "report"],
                        default="full", help="Execution mode")
    parser.add_argument("--save", action="store_true", help="Save results to file")
    args = parser.parse_args()

    agent = CROAgent(mode=args.mode)
    results = agent.run()

    if args.save:
        agent.save_results()

    return results


if __name__ == "__main__":
    main()
