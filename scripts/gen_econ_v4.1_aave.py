#!/usr/bin/env python3
"""
Generate ECON v4.1 report for Aave using Anthropic API
This script implements deep research methodology to produce a comprehensive
cryptoeconomic analysis following the v4.1 prompt template.
"""

import os
import sys
from datetime import datetime
from anthropic import Anthropic
from pathlib import Path

def load_env():
    """Load environment variables from .env.local"""
    env_path = Path(__file__).parent.parent / '.env.local'
    if not env_path.exists():
        return

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

def generate_aave_report():
    """Generate comprehensive Aave ECON report using v4.1 prompt."""

    # Load environment
    load_env()

    # Load API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in environment or .env.local")
        sys.exit(1)

    client = Anthropic(api_key=api_key)

    # Load v4.1 prompt template
    prompt_path = "/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab/econ_v4.1_generic_url_input_prompt.md"
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_template = f.read()

    # Prepare the research prompt with Aave context
    project_url = "https://aave.com"
    project_name = "Aave"
    current_date = datetime.now().strftime("%Y년 %m월 %d일")

    research_prompt = f"""당신은 블록체인 경제 시스템 전문 연구 분석가입니다.

다음 프롬프트 템플릿을 사용하여 Aave 프로젝트에 대한 심층 크립토이코노미 분석 보고서를 작성해주세요.

**입력 파라미터:**
- PROJECT_URL: {project_url}
- PROJECT_NAME: {project_name}
- REPORT_LANG: 한국어
- 정보 수집 일자: {current_date}

**중요 지시사항:**
1. 반드시 실제로 접근 가능한 URL만 인용하세요 (할루시네이션 금지)
2. Section 7 참고문헌에 최소 48개 URL 포함
3. 본문에 인라인 인용 [번호] 형식으로 80회 이상 사용
4. 모든 개념 정의에 온체인 state 매핑 포함
5. Aave는 DeFi 대출 프로토콜이므로, 토큰노믹스, 거버넌스, 담보/대출 메커니즘에 집중

---

{prompt_template}

---

위 프롬프트를 따라 Aave 프로젝트에 대한 완전한 ECON 보고서를 생성해주세요.
보고서는 반드시 7개 섹션을 모두 포함해야 하며, 6000단어 이상의 상세한 분석이어야 합니다.
"""

    print(f"Starting deep research for Aave ECON v4.1 report...")
    print(f"Project URL: {project_url}")
    print(f"Model: Claude Opus 4.7 with extended thinking")
    print(f"Estimated time: 3-5 minutes for API response")
    print()

    # Call Anthropic API with extended thinking
    try:
        message = client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=16000,  # Maximum output for comprehensive report
            thinking={
                "type": "enabled",
                "budget_tokens": 10000  # Extended thinking budget
            },
            messages=[
                {
                    "role": "user",
                    "content": research_prompt
                }
            ]
        )

        # Extract the report text
        report_text = ""
        for block in message.content:
            if block.type == "text":
                report_text += block.text

        if not report_text:
            print("Error: No text content generated")
            sys.exit(1)

        # Save the report
        output_path = "/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab/aave_v4.1.md"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)

        print(f"✅ Report generated successfully!")
        print(f"Output: {output_path}")
        print(f"Length: {len(report_text)} characters")
        print(f"Words: ~{len(report_text.split())} words")
        print()

        # Quick validation
        has_section_7 = "## 7. 참고문헌" in report_text or "##7. 참고문헌" in report_text
        url_count = report_text.count("https://") + report_text.count("http://")

        print("Quick Validation:")
        print(f"  - Section 7 exists: {'✅' if has_section_7 else '❌'}")
        print(f"  - URL count: {url_count} (target: 48+)")
        print()

        return output_path

    except Exception as e:
        print(f"Error during API call: {e}")
        sys.exit(1)

if __name__ == "__main__":
    output_path = generate_aave_report()
    print(f"Report saved to: {output_path}")
