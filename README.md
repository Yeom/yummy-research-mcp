# yummy-research-mcp

해외·국내 거시/시장 통계를 도구로 노출하는 **MCP server**. 첫 번째 데이터 셋은 시장 심리/밸류에이션 지표지만, 향후 KRX·DART·한국은행 ECOS·FRED 등을 같은 패턴으로 추가하도록 설계.

## 현재 도구

| name | 설명 |
| --- | --- |
| `get_cnn_fear_greed` | CNN Fear & Greed Index (US) — 현재값 + 일별 히스토리 |
| `get_kospi_fear_greed` | 인덱서고 코스피 공포탐욕지수 (idxDetail=24501, 일간) |
| `get_kospi_buffett` | 코스피 버핏지수 = 시가총액(20104,D) / 직전 4Q GDP 합(09140,Q) × 100 |
| `get_all_indices` | 위 셋을 한 번에 반환 |

각 도구는 `{ name, source, latest, series, ... }` 형태의 JSON을 반환.

## 개발 환경

`uv` 기반.

```bash
cd ~/workspace/yummy-research-mcp

uv sync                          # 의존성 설치 (.venv 자동 생성)
uv run yummy-research-mcp        # MCP stdio 서버 실행
uv run python -m yummy_research_mcp.sources.cnn        # 단독 페치 디버깅
uv run pytest                    # 라이브 엔드포인트 스모크 테스트
```

## Claude Code / Claude Desktop 등록

```json
{
  "mcpServers": {
    "yummy-research": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/yeom/workspace/yummy-research-mcp",
        "run",
        "yummy-research-mcp"
      ]
    }
  }
}
```

## 새 데이터 소스 추가

1. `src/yummy_research_mcp/sources/<source>.py`에 페처 작성 — 순수 함수, JSON-직렬화 가능한 dict 반환.
2. `src/yummy_research_mcp/server.py`의 `TOOLS` 레지스트리에 `Tool` + 콜러블 추가.
3. `tests/`에 라이브 스모크 테스트 추가.

## 디렉토리

```
src/yummy_research_mcp/
  __init__.py
  http.py                # 공통 urllib 래퍼 (browser-like UA / Accept-Language)
  server.py              # MCP stdio 서버 + 도구 레지스트리
  sources/
    cnn.py               # CNN Fear & Greed (production.dataviz.cnn.io)
    indexergo.py         # indexergo.com (인라인 ECharts JSON 파싱)
tests/
  test_fetchers.py
```

## 데이터 소스 메모

- **CNN F&G**: `production.dataviz.cnn.io/index/fearandgreed/graphdata` JSON API. 브라우저 UA + `Origin: edition.cnn.com` + `Referer` 필수 (없으면 418).
- **indexergo**: 페이지 인라인 ECharts `option` JSON에서 첫 `series.data`를 균형 괄호 스캔으로 추출. 사이트의 `/ajaxMakeChart` POST 엔드포인트보다 정적 HTML 파싱이 안정적이라 그쪽 채택.
