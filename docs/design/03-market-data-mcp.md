# yummy-research-mcp 확장 설계

작성: 2026-09-11 · 상태: 검토용 설계, 구현·배포 전
대상: https://github.com/Yeom/yummy-research-mcp

## 1. 목표와 책임

오전 지표 브리프와 오후 관심기업 브리프가 재현 가능한 수치·출처·발표 시점에 근거하도록 한다. MCP는 데이터 조회 인터페이스다. 예약 실행 자체는 Yummy 런타임, 수집·정규화·스냅샷 저장은 MCP 패키지의 수집 모듈, 사건 기억·해석·발행은 Yummy가 담당한다.

MCP 호출 시마다 모든 데이터를 새로 긁는 방식 대신, 수집기가 미리 저장한 동일 snapshot을 보고서와 차트에 제공한다. MCP 도구는 읽기 전용이며, 갱신은 운영 수집 명령으로 실행한다. 도구가 모델의 지시로 보고서를 발행하거나 개인 대화 기억을 수정하지 않는다.

관련 문서(로컬 형제 저장소): [브리핑 설계](../../../yummy_research/docs/design/01-briefing-product.md), [기억 설계](../../../yummy_research/docs/design/02-memory-context.md). GitHub에서는 형제 저장소 경로가 열리지 않을 수 있다. 본 문서의 입출력 계약은 단독 구현에 필요한 내용을 포함한다.

## 2. 현재 코드 감사

기준: 로컬 src/yummy_research_mcp/server.py, http.py, sources/cnn.py, sources/indexergo.py, tests/test_fetchers.py 및 공개 GitHub README.

- Python >=3.10, mcp>=1.2.0, stdio 서버. sync fetcher를 asyncio.to_thread로 실행한다.
- get_cnn_fear_greed, get_kospi_fear_greed, get_kospi_buffett, get_all_indices 4개 도구만 존재한다.
- CNN JSON과 indexergo HTML 파싱에 의존한다. 장기 데이터 저장, 발표시점·수정치 이력, 고정 snapshot은 없다.
- get_all_indices는 소스별 순차 호출이며 한 소스 예외가 전체 결과를 실패시킬 수 있다.
- JSON Schema를 광고하지만 런타임 인수 검증은 도구별로 보강해야 한다. 무제한 history 응답은 문맥을 크게 차지할 수 있다.
- 예외 문자열을 모델에게 그대로 반환하는 경로가 있다. API 키 기반 소스를 추가하기 전에 URL·자격증명 마스킹이 필요하다.
- 기존 테스트는 라이브 엔드포인트 중심이다. 설명에는 offline skip이라고 적혀 있지만 명시적인 skip 처리가 없어 외부 장애와 코드 회귀를 구분하기 어렵다.
- 현재 로컬 README 변경과 .claude/settings.local.json 삭제는 앞선 전환 작업의 미커밋 변경이다. 새 설계가 이를 덮어쓰지 않는다. 공개 원격과 로컬 상태는 아직 같지 않다.

## 3. 데이터 도입 범위

### 1차: 오전 핵심 금리·원유

FRED를 첫 정규화 공급자로 사용한다. 실제 API 키와 응답을 확인한 뒤 활성화한다. 아래 ID는 도입 대상 registry이며 구현 시 metadata로 단위·주기·원출처를 다시 검증한다.

| 내부 metric_id | 공급 후보 / series_id | 단위·해석 |
|---|---|---|
| us.policy.lower / upper | FRED DFEDTARL / DFEDTARU | %, 정책 목표 범위 |
| us.fedfunds.effective | FRED DFF | %, 실효금리. 정책 목표 범위와 구분 |
| us.treasury.3y / 10y / 30y | FRED DGS3 / DGS10 / DGS30 | %, 고정만기 수익률. 채권가격이 아님 |
| us.treasury.real10y | FRED DFII10 | %, 물가연동 10년 실질 수익률 |
| us.curve.10y_minus_3y | 같은 관측일의 DGS10-DGS3 | bp, (10년%-3년%)*100 |
| oil.wti.spot / oil.brent.spot | FRED DCOILWTICO / DCOILBRENTEU | USD/배럴, 현물. 선물 최근월과 혼합 금지 |

FRED는 배포 창구이며 원생산기관을 source_origin에 별도로 둔다. 공식 일별 데이터는 미국 시장의 방금 끝난 종가보다 늦을 수 있다. 오전 07:50이라는 이유만으로 최신 관측을 '밤사이' 값으로 설명하지 않는다.

### 2차: 설명 보강과 관심기업

- 달러: FRED DTWEXBGS 광의 달러지수. ICE DXY와 다른 지표임을 이름에 명시한다.
- USD/KRW: ECOS 또는 검증된 환율 공급자. 매매기준율·현물 종가 등 기준을 먼저 고정한다.
- 미국/한국 주가지수·VIX·원유선물: 공식 또는 계약한 공급자의 종가/지연시세와 재배포 권한을 확인한 후 추가한다. 일간 FRED 통계를 실시간 시세 대체물로 쓰지 않는다.
- 에너지 재고·생산: EIA API v2. 일간 가격과 주간 재고를 같은 시간척도로 합치지 않는다. 1차 FRED 원유와 별도 metric으로 보관한다.
- 기업 공시: 한국 OpenDART, 미국 SEC EDGAR submissions와 companyfacts. 기업 식별자는 DART corp_code/SEC CIK와 거래소 ticker를 매핑한다.
- 기업 IR: 사용자 관심기업별 공식 뉴스룸·RSS의 허용된 엔드포인트를 registry에 등록한다.
- 일반 뉴스·테마: 기존 승인 Telegram 수집과 별도 뉴스 공급자 어댑터를 결합한다. DART/SEC는 일반 뉴스 전체를 제공하지 않는다. 뉴스 공급자는 검색 범위·사용료·저장/재배포 조건을 확인한 뒤 활성화하며 기본값은 disabled다.
- 일정: 공식 FOMC/BLS/BEA/EIA 등 발표 캘린더를 출처와 timezone 포함해 저장한다. 컨센서스는 실제 공급이 확보되기 전 제공하지 않는다. 실제값만으로 '예상 상회'를 만들지 않는다.

CNN/indexergo 도구는 보조 지표로 유지한다. HTML 변경·차단에 취약하므로 핵심 금리·원유 파이프라인을 이 소스에 의존시키지 않는다. 버핏지수는 GDP의 실제 공개 가능 시점을 반영하기 전 과거 시점 재현 도구로 사용하지 않는다.

## 4. 공통 응답 계약 v1

모든 신규 도구는 다음 정보를 제공한다. 기존 4개 응답은 호환성을 위해 유지하고 신규 계약으로 변환하는 adapter를 내부에서 사용한다.

```json
{
  "schema_version": "1",
  "snapshot_id": "example-only",
  "as_of": "2026-09-15T07:40:00+09:00",
  "status": "ok",
  "items": [{
    "metric_id": "us.treasury.10y",
    "name": "미국채 10년 고정만기 수익률",
    "unit": "percent",
    "frequency": "business_daily",
    "source_origin": "Federal Reserve H.15",
    "source_provider": "FRED",
    "source_url": "https://fred.stlouisfed.org/series/DGS10",
    "latest": {
      "observation_id": "example-observation",
      "observation_date": "2026-09-14",
      "value": 4.12,
      "published_at": null,
      "first_seen_at": "2026-09-15T07:32:00+09:00",
      "vintage_date": "2026-09-15",
      "availability_basis": "first_seen"
    },
    "change": {"value": -8.0, "unit": "bp", "from_date": "2026-09-11", "to_date": "2026-09-14"},
    "quality": {"state": "fresh", "warnings": []}
  }],
  "errors": [],
  "next_cursor": null
}
```

위 JSON의 숫자와 ID는 계약 설명용 가상값이며 운영 데이터로 저장·발행하지 않는다.

응답 상태는 ok/partial/unavailable. 품질은 fresh/not_due/stale/missing/revised/unsupported_asof 중 하나로 표기한다. not_due는 예정된 새 관측이 아직 없다는 뜻이지 값이 0 또는 시장 변화가 없다는 뜻이 아니다. old값을 제공할 때도 stale과 실제 날짜를 유지한다.

published_at을 모르면 null로 둔다. first_seen_at이 cutoff 이전이면 '우리 시스템이 당시에 알았던 값'으로 사용 가능하다. 날짜 단위 vintage만으로 당일 오전 공개 여부를 증명할 수 없다. 수집 개시 전 과거 재현에서 시각 근거가 없으면 unsupported_asof로 반환하거나 보수적으로 다음 날짜부터 사용하며 해당 정책을 메타데이터에 명시한다.

지표 관측일이 cutoff보다 이전이어도 공개/인지가 cutoff 이후면 당시 보고서에 넣지 않는다. 수정된 같은 날짜 값은 덮어쓰지 않고 새 observation version으로 저장한다. source별 실제 발표 예상 시각과 휴일 달력을 기준으로 freshness를 판정하며 일괄 '24시간 이내' 규칙을 쓰지 않는다.

## 5. 제안 MCP 도구

도구명과 인수는 신규 설계 계약이며 현재 존재하지 않는다. query limit은 최대 100, series limit은 최대 1,000점, 기본 60점으로 제한한다.

| 도구 | 인수 | 반환·용도 |
|---|---|---|
| list_metrics | category?, cursor?, limit=50 | 지원 지표·단위·주기·공급자·활성화 상태 |
| get_market_snapshot | as_of, metric_ids?, snapshot_id? | 지표 수준·변화·품질. snapshot_id를 주면 as_of 일치 검사 |
| get_metric_series | metric_id, start, end, as_of, limit=60, cursor? | 해당 시점에 알 수 있었던 관측 버전, 차트용 이력 |
| get_metric_context | metric_id, as_of, lookback=252 | 1/5/20 유효 관측 변화, 백분위·표본수·계산 방법 |
| get_company_filings | entity_id, published_after, as_of, forms?, limit=20, cursor? | 공시 ID·유형·공개시각·원문 URL·정정 연결 |
| search_company_news | entity_ids, query?, published_after, as_of, limit=20, cursor? | 뉴스 후보·출처·검색 커버리지. 공급 미설정이면 unavailable |
| get_release_calendar | start, end, as_of, countries? | 당시 알려진 예정 이벤트, 변경 이력. 미확보 컨센서스 null |
| get_source_health | source_ids? | 마지막 성공·최신 관측일·지연·오류. 키나 개인 정보 제외 |

공시 반환 예: filing_id, entity_id, document_type, published_at, first_seen_at, title, source_url, amendment_of, quality. 뉴스는 evidence_id와 original_source_url을 제공하며 관련 테마 여부의 최종 판단은 Yummy가 한다.

snapshot_id는 모델 입력·차트·발행 이력이 공유한다. get_metric_series도 동일 as_of에서 선택한 observation ID들을 반환하며, 차트 artifact metadata에 snapshot_id와 사용 observation ID를 기록한다. 보고서 생성 중 새 값이 들어와도 기존 snapshot은 바뀌지 않는다.

MCP 입력은 타입·날짜·ID allowlist·최대 범위를 실제 코드로 검사한다. 임의 URL 다운로드 도구는 만들지 않는다. 잘못된 인수는 invalid_argument, 키 미설정은 source_not_configured, 제한은 rate_limited, 변경된 응답 형식은 schema_changed로 정규화한다.

## 6. 저장소·계산·시각화

MCP 측 SQLite state/market_data.db를 사용한다. 테이블:
- metrics: ID, 출처, 주기, 단위, 달력, 발표 지연 정책, 사용 조건.
- observation_versions: metric_id, observation_date, value, unit, published_at, first_seen_at, vintage_date, superseded_at, source_payload_hash.
- snapshots / snapshot_items: 고정된 as_of와 선택된 observation ID.
- source_runs: 시작·완료·상태·커버리지·오류 코드.
- entities / filings / news_items / release_events: 공공 기업·공시·뉴스 메타데이터. 개인 관심 이유는 저장하지 않는다.

수집 원본은 허용되는 범위에서 내용 해시와 함께 보관하고 키 포함 요청 URL은 저장하지 않는다. 접근권한이 제한된 원문은 저장 범위를 공급 조건에 맞춘다.

계산은 모델 밖의 순수 함수로 한다. 금리 변동은 (현재%-이전%)*100 bp. 가격은 분모가 양수일 때만 (현재/이전-1)*100. 음수·0 가격은 절대 달러 변화로 대체하고 % 계산 불가를 명시한다. 스프레드는 같은 날짜 관측끼리만 계산한다. 서로 다른 주기를 무리하게 전일 변화로 변환하지 않는다.

이례성은 이전 252개 유효 변화량의 절댓값 경험적 백분위, 최소 120개 표본이다. 현재 변화를 비교 분포에서 제외한다. 90/97.5 경계는 초기 설정값이며 통계적 유의확률이나 매매 신호로 설명하지 않는다. 큰 관측 공백은 별도 품질 경고를 주고 일간 변화 분포와 비교하지 않는다.

차트 생성은 Yummy의 charts.py가 담당한다. MCP는 시계열과 메타데이터를 제공하며 이미지 생성 모델로 차트를 그리지 않는다. 본문과 같은 snapshot으로 matplotlib PNG를 만들고, Telegram sendPhoto는 Yummy publisher에 추가한다. 이미지 전송도 message_id·sent_at·불확실 상태를 별도 추적한다. 현재 publisher는 텍스트만 지원하므로 이 변경이 필요하다.

## 7. 수집 실행과 실패 처리

제안 명령: yummy-research-collect --profile morning --as-of ISO_TIME. morning/evening 프로필은 등록된 공급자와 지표를 선택하며 재실행은 멱등적이다. 스케줄은 Yummy가 하나로 관리하고 MCP 자체에 별도 중복 타이머를 두지 않는다.

HTTP는 기본 10초 timeout, 일시 장애에 최대 2회 재시도, Retry-After 존중, 공급자별 동시성 제한과 회로 차단을 적용한다. 보고서 마감 예산 안에서 종료하고 실패한 소스만 오류로 남긴다. 초기 SEC 요청 상한은 자체적으로 초당 2회로 보수적으로 설정하며 공식 접근 정책 변경을 확인한다. 전체 소스 실패 시 정상 snapshot을 가장하지 않는다.

조회는 저장된 snapshot을 읽는다. 자료가 아직 없으면 unavailable을 반환하고 모델에게 재수집을 계속 요청하지 않는다. 작업자는 별도 수집 실행과 get_source_health로 원인을 확인한다. 수집 실패와 자료 없음, 휴장, 미발표는 서로 다른 상태다.

## 8. 인증·배포

FRED/EIA/OpenDART는 각 API 키를 운영자 설정에서 읽는다. SEC는 API 키보다 식별 가능한 User-Agent 및 접근 정책 준수가 필요하다. 실제 키는 아직 이 설계에서 확인하거나 발급하지 않았다.

현재 Codex runner는 자식 환경변수를 allowlist로 제한한다. 키를 그 환경에 무차별 추가하지 않는다. 수집기만 별도 비밀 설정을 읽어 API를 호출하고, 모델이 호출하는 stdio MCP는 저장된 데이터를 읽도록 분리한다. 환경 구성 파일은 저장소에 커밋하지 않는다.

현재 mcp>=1.2.0의 넓은 범위는 구현 시 호환 버전과 lockfile을 검증한다. 기존 도구 이름·응답은 유지한다. 신규 도구는 v1 계약에 맞추고 이전 도구 제거는 별도 버전 변경으로 다룬다. 이번 설계는 GitHub push나 배포를 수행하지 않는다.

## 9. 파일별 구현 제안

| 경로 | 역할 |
|---|---|
| src/yummy_research_mcp/models.py | 공통 응답·관측·품질 모델과 스키마 검증 |
| src/yummy_research_mcp/registry.py | 지표 ID와 공급·단위·달력 메타데이터 |
| src/yummy_research_mcp/storage.py | SQLite 마이그레이션·버전·snapshot |
| src/yummy_research_mcp/collect.py | 운영용 수집 CLI, 프로필, 실패 격리 |
| src/yummy_research_mcp/analytics.py | bp/%/구간 변화·백분위 |
| src/yummy_research_mcp/sources/fred.py | FRED 관측·metadata·vintage 수집 |
| src/yummy_research_mcp/sources/eia.py | EIA v2 에너지 시계열 |
| src/yummy_research_mcp/sources/dart.py, sec.py | 기업 식별·공시·정정 |
| src/yummy_research_mcp/sources/news.py, calendar.py | 공급자별 뉴스와 공식 일정 어댑터 |
| src/yummy_research_mcp/http.py | 재시도·rate limit·키 마스킹·timeout |
| src/yummy_research_mcp/server.py | 신규 읽기 도구·인수 검증·bounded 응답 |
| tests/fixtures/ | 고정 응답·결측·정정·차단·형식 변경 자료 |
| tests/test_contracts.py, test_asof.py, test_analytics.py, test_collect.py | 오프라인 회귀 테스트 |
| tests/test_live_sources.py | 명시적 실행 옵션과 인증이 있을 때만 라이브 점검 |

Yummy 연동 파일: brief.py(회차 입력), runner.py(MCP 등록·출력 계약), charts.py(신규), telegram.py(이미지·문단 분할), store.py(회차·전송 시각). 기억 기능은 별도 연구 DB를 사용한다.

## 10. 단계별 납품과 검증

A. 공통 계약·버전 저장·FRED 금리/원유: offline fixture로 단위·결측·날짜·수정치 검증 후 실제 인증 조회. 키가 없으면 비활성 상태를 정직하게 반환.
B. snapshot·변동 계산·품질 판정: 주말·미국 휴장·DST·지연 발표·동일 날짜 수정치·0/음수 가격 테스트. 당시에 알 수 없는 관측이 포함되면 실패.
C. 오전 패키지와 차트: 단일 snapshot에서 숫자·차트 일치, 텍스트 성공/사진 실패 복구, 사진 불확실 응답 중복 방지 검증.
D. SEC/DART·관심기업: 동명이인, ticker 변경, 정정 공시, 페이지네이션, 뉴스 공급 미설정, 새 소식 없음과 실패 구분.
E. 뉴스·달러·지수·캘린더: 공급 계약과 공개 시점 품질 확보 후 활성화. 과거 컨센서스·실시간 시세는 별도 공급 없이는 범위 밖.

단계별로 README와 source registry를 갱신한다. CI의 기본 테스트는 네트워크 없이 결정적으로 통과해야 하며 라이브 검증은 별도다. 저장된 fixture 결과만으로 실제 API 정상 작동을 주장하지 않는다.

## 11. 구현 전 필요한 입력과 리스크

- 사용자 관심기업 목록과 관심 이유: 오후 모듈 대상 확정에 필요.
- FRED/EIA/OpenDART 인증 설정: 해당 공급자의 실제 조회 검증에 필요.
- 뉴스/시세 공급 범위·예산: 공시 외 전체 뉴스와 시장 종가 확보에 필요.
- 주말/장애 복구 시간 범위: 최근 24시간 승인에서 확장되는 수집 범위 확인 필요.

이 입력이 없어도 schema·SQLite·계산·fixture·FRED adapter 구현은 진행 가능하다. 확인되지 않은 공급을 실제 운영 데이터처럼 채우지 않는다.

## 12. 확인한 공식 자료

- [대상 저장소](https://github.com/Yeom/yummy-research-mcp): 기존 도구 범위와 구조 확인.
- [FRED observations API](https://fred.stlouisfed.org/docs/api/fred/series_observations.html): 관측 기간·realtime/vintage 파라미터·키 요구. 일중 공개 시각 보장으로 해석하지 않는다.
- [DGS3 정의](https://fred.stlouisfed.org/series/DGS3), [DGS10 정의](https://fred.stlouisfed.org/series/DGS10), [DFF 정의](https://fred.stlouisfed.org/series/DFF), [WTI 현물 정의](https://fred.stlouisfed.org/series/DCOILWTICO), [실질금리](https://fred.stlouisfed.org/series/DFII10), [광의 달러지수](https://fred.stlouisfed.org/series/DTWEXBGS): 지표 의미와 주기 확인.
- [EIA API v2](https://www.eia.gov/opendata/documentation.php): 에너지 시계열 adapter 설계 근거.
- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces): submissions/companyfacts 및 접근 방식.
- [OpenDART 개발가이드](https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS001): 한국 공시 API 범위.

문서 확인과 실제 인증 API 호출은 별도다. 이번 단계에서는 문서와 코드를 조사했으며 신규 공급자의 라이브 수집은 수행하지 않았다.
