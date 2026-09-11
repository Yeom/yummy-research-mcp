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
uv run pytest                    # 오프라인 단위 테스트
```

## Codex 등록

`yummy-agent/.codex/config.toml`에 프로젝트 설정이 있다. 자동 실행하는
`yummy_research/yummy_codex/runner.py`도 동일 서버를 명시적으로 등록한다.
기존 Claude 플러그인 manifest는 사용하지 않는다.

```toml
[mcp_servers.yummy-research]
command = "/Users/yeom/workspace/yummy-research-mcp/.venv/bin/python"
args = ["-m", "yummy_research_mcp.server"]
```

가상 환경이 없으면 먼저 이 프로젝트에서 `uv sync`로 설치한다.
서버 도구 목록에 나타나는 것과 외부 데이터 소스가 정상 응답하는 것은 별도로 검증한다.

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

## 확장 설계

[지표·공시·뉴스 MCP 확장 설계](docs/design/03-market-data-mcp.md)는 금리·미국채·원유, 시점별 관측 저장, 관심기업 공시, 데이터 품질과 신규 도구 계약을 정의한다. 전체 목표 설계이며 현재 구현 범위는 아래 구현 상태 문서와 구분한다.

## 오전·오후 브리핑용 데이터 (구현)

`cp .env.example .env` 후 키를 입력한다. `.env`는 Git에서 제외된다.
FRED 키가 있으면 공식 JSON API, 없으면 공개 CSV 경로를 사용한다.
키는 서비스 내부에서만 읽고 MCP 응답이나 차트에 포함하지 않는다.

```sh
uv sync
uv run python -m yummy_research_mcp.collect collect
uv run python -m yummy_research_mcp.collect snapshot --as-of 2026-09-11T11:00:00Z
uv run python -m yummy_research_mcp.collect chart --snapshot-id SNAPSHOT_ID --out state/chart.png
uv run pytest
# 기존 외부 사이트 접속 시험은 선택 실행
YUMMY_LIVE_TESTS=1 uv run pytest tests/test_fetchers.py
```

추가 도구: `list_metrics`, `get_market_snapshot`, `get_metric_series`,
`get_source_health`, `get_company_filings`, `search_company_news`.
기존 4개 도구도 유지한다. 지표 일괄 갱신·차트 파일 작성은 운영 CLI에서 수행한다.

- 미국채 3·10·30년, 실질 10년, 정책금리 상·하단/실효금리, WTI·Brent 현물, 광의 달러지수.
- 지표 SQLite: `state/market_data.db`. observations는 수정값을 수집 시각별 보관,
  snapshots는 보고서 사용 시점의 고정 결과, health는 수집 성공·실패 이력의 최신 상태.
- 과거 날짜 값을 오늘 처음 수집했다면 오늘부터 알려진 값으로 처리한다. 완전한 과거 시점 복원이나 ALFRED 전체 빈티지 구축은 아니다.
- 금리 변화는 bp, 양수 가격 변화는 %. 비교 날짜를 반환한다. 일간 변동의 과거 분포 최소 120개가 있어야 주의 수준을 산출하며, 예측·매매 신호가 아니다.
- 일별 값은 발표 지연이 있다. 관측일·최초 수집 시각을 구분하고 5일 초과 관측은 stale로 표시한다.
- DART는 키 필요, SEC는 연락처 포함 User-Agent 필요. DART의 날짜 단위 검색은 장중 정확한 시각 필터를 보장하지 않는다.
- 뉴스는 Google News RSS 제목 발견 기능. 기사 원문 검증·기업 식별·테마 인과 확인은 분석 단계에서 필요하며 전수 수집을 보장하지 않는다.

실제 Telegram 운영 프로그램은 인접한 `yummy_research/`에서 실행된다.
이 저장소는 데이터 MCP와 수집기만 버전 관리한다. 운영 연동과 남은 범위는
[구현 상태](docs/implementation/status.md)를 참고한다.
