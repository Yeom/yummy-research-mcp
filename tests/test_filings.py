from datetime import datetime, timezone

def test_sec_acceptance_time_not_filing_date_controls_cutoff():
    from yummy_research_mcp.filings import parse_sec
    data={'filings':{'recent':{'accessionNumber':['0000000001-26-000001'],'acceptanceDateTime':['2026-09-11T15:00:00Z'],'filingDate':['2026-09-11'],'form':['8-K'],'primaryDocument':['a.htm']}}}
    assert parse_sec(data,'1','2026-09-10T00:00:00Z','2026-09-11T14:00:00Z')==[]
    assert len(parse_sec(data,'1','2026-09-10T00:00:00Z','2026-09-11T16:00:00Z'))==1

def test_missing_key_is_unavailable_not_empty_news(monkeypatch):
    from yummy_research_mcp.filings import get_filings
    monkeypatch.setattr('yummy_research_mcp.filings.setting',lambda key:'')
    result=get_filings('KR','00123456','2026-09-10T00:00:00Z','2026-09-11T14:00:00Z')
    assert result['status']=='unavailable' and result['error']=='source_not_configured'

def test_news_filters_future_and_labels_discovery(monkeypatch):
    from yummy_research_mcp import filings
    xml=b'<rss><channel><item><title>past</title><link>https://example.com/a</link><pubDate>Thu, 10 Sep 2026 12:00:00 GMT</pubDate></item><item><title>future</title><pubDate>Fri, 11 Sep 2026 12:00:00 GMT</pubDate></item></channel></rss>'
    monkeypatch.setattr(filings,'http_get',lambda *a,**k:xml)
    result=filings.search_news('test','2026-09-10T00:00:00Z','2026-09-11T00:00:00Z')
    assert len(result['items'])==1
    assert result['items'][0]['verification']=='headline_only'
