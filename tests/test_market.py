import pytest
from datetime import datetime, timezone

def test_registry_and_csv_missing_values():
    from yummy_research_mcp.market import METRICS, parse_csv
    assert [METRICS[x]['series'] for x in ('us3y','us10y','us30y')]==['DGS3','DGS10','DGS30']
    assert parse_csv('observation_date,DGS3\n2026-09-01,4.1\n2026-09-02,.\n','DGS3')==[{'date':'2026-09-01','value':4.1}]

def test_changes_rates_negative_prices_and_short_history():
    from yummy_research_mcp.market import changes
    assert changes([{'date':'2026-09-01','value':4.2},{'date':'2026-09-02','value':4.1}], 'percent')['delta']==pytest.approx(-10)
    result=changes([{'date':'2026-09-01','value':0},{'date':'2026-09-02','value':-2}], 'usd_barrel')
    assert result['unit']=='USD' and result['delta']==-2
    assert result['attention']=='insufficient_history'

def test_vintages_never_rewrite_previous_snapshot(tmp_path):
    from yummy_research_mcp.market import MarketStore
    store=MarketStore(tmp_path/'market.db')
    store.ingest('us3y',[{'date':'2026-09-01','value':4}], '2026-09-02T00:00:00+00:00')
    old=store.snapshot('2026-09-02T01:00:00+00:00',['us3y'])
    store.ingest('us3y',[{'date':'2026-09-01','value':4.1}], '2026-09-03T00:00:00+00:00')
    assert store.snapshot('2026-09-02T01:00:00+00:00',['us3y'])['items'][0]['latest']['value']==4
    assert store.get_snapshot(old['snapshot_id'])==old
    assert store.snapshot('2026-09-01T00:00:00+00:00',['us3y'])['status']=='unavailable'

def test_collect_partial_failure_never_fabricates_zero(tmp_path):
    from yummy_research_mcp.market import collect
    def fetch(metric):
        if metric=='us3y':return [{'date':'2026-09-01','value':4.1}]
        raise ValueError('private credential')
    out=collect(tmp_path/'m.db',['us3y','wti'],fetcher=fetch,now='2026-09-02T00:00:00+00:00')
    assert out['status']=='partial'
    assert out['errors'][0]['code']=='ValueError'
    assert 'credential' not in str(out)

def test_fred_json_api_uses_key_and_skips_missing(monkeypatch):
    import json
    from yummy_research_mcp import market
    monkeypatch.setenv('FRED_API_KEY','test-key')
    captured=[]
    def fake(url,timeout):
        captured.append(url)
        return json.dumps({'observations':[{'date':'2026-09-09','value':'.'},{'date':'2026-09-10','value':'4.12'}]}).encode()
    monkeypatch.setattr(market,'http_get',fake)
    assert market.fetch_metric('us10y')==[{'date':'2026-09-10','value':4.12}]
    assert captured[0].startswith('https://api.stlouisfed.org/fred/series/observations?')
    assert 'api_key=test-key' in captured[0]

def test_flat_policy_rate_is_not_exceptional():
    from datetime import timedelta
    from yummy_research_mcp.market import changes
    start=datetime(2026,1,1)
    rows=[{'date':(start+timedelta(days=i)).date().isoformat(),'value':4} for i in range(150)]
    assert changes(rows,'percent')['attention']=='normal'
