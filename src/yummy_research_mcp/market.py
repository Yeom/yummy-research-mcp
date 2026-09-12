"""Official daily observations, vintage-safe snapshots and deterministic calculations."""
from __future__ import annotations
from contextlib import contextmanager
import csv
import hashlib
import io
import json
import math
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from .http import http_get
from .settings import setting

METRICS = {
    'us3y': {'series':'DGS3','name':'미국채 3Y','unit':'percent'},
    'us10y': {'series':'DGS10','name':'미국채 10Y','unit':'percent'},
    'us30y': {'series':'DGS30','name':'미국채 30Y','unit':'percent'},
    'real10y': {'series':'DFII10','name':'미국 실질금리 10Y','unit':'percent'},
    'fed_lower': {'series':'DFEDTARL','name':'정책금리 하단','unit':'percent'},
    'fed_upper': {'series':'DFEDTARU','name':'정책금리 상단','unit':'percent'},
    'fed_effective': {'series':'DFF','name':'실효 연방기금금리','unit':'percent'},
    'wti': {'series':'DCOILWTICO','name':'WTI 현물','unit':'usd_barrel'},
    'brent': {'series':'DCOILBRENTEU','name':'Brent 현물','unit':'usd_barrel'},
    'dollar_broad': {'series':'DTWEXBGS','name':'광의 달러지수','unit':'index'},
}

def utc(value):
    d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if d.tzinfo is None: raise ValueError('Timezone required')
    return d.astimezone(timezone.utc)

def metric_ids(ids=None):
    ids=[k for k in METRICS if k not in ('brent','dollar_broad')] if ids is None else ids
    if not isinstance(ids,list) or not ids or len(ids)>20 or any(x not in METRICS for x in ids):raise ValueError('Invalid metric IDs')
    return list(dict.fromkeys(ids))

def default_db():
    return Path(setting('YUMMY_MARKET_DB') or str(Path(__file__).resolve().parents[2]/'state/market_data.db'))

def parse_csv(text, series):
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if not reader.fieldnames or series not in reader.fieldnames:raise ValueError('Unexpected CSV schema')
    date_key='observation_date' if 'observation_date' in reader.fieldnames else 'DATE'
    result={}
    for row in reader:
        if row.get(series) in ('','.',None):continue
        day=datetime.strptime(row[date_key],'%Y-%m-%d').date().isoformat()
        value=float(row[series])
        if not math.isfinite(value):raise ValueError('Non-finite observation')
        result[day]={'date':day,'value':value}
    if not result:raise ValueError('No observations')
    return [result[d] for d in sorted(result)]

def fetch_metric(metric):
    definition=METRICS[metric]
    start=(datetime.now(timezone.utc)-timedelta(days=550)).date().isoformat()
    key=setting('FRED_API_KEY')
    if key:
        query=urlencode({'series_id':definition['series'],'api_key':key,'file_type':'json','observation_start':start,'sort_order':'asc','limit':1000})
        data=json.loads(http_get('https://api.stlouisfed.org/fred/series/observations?'+query,timeout=20))
        if 'observations' not in data:raise ValueError('FRED response missing observations')
        content=io.StringIO();writer=csv.writer(content)
        writer.writerow(['observation_date',definition['series']])
        for row in data['observations']:writer.writerow([row['date'],row['value']])
        return parse_csv(content.getvalue(),definition['series'])
    query=urlencode({'id':definition['series'],'cosd':start})
    return parse_csv(http_get('https://fred.stlouisfed.org/graph/fredgraph.csv?'+query,timeout=20).decode(),definition['series'])

def changes(series,unit):
    if len(series)<2:return {'delta':None,'unit':None,'attention':'insufficient_history'}
    current,previous=series[-1],series[-2]
    a,b=previous['value'],current['value']
    if unit=='percent':delta=(b-a)*100; delta_unit='bp'
    elif a>0:delta=(b/a-1)*100;delta_unit='%'
    else:delta=b-a;delta_unit='USD' if unit=='usd_barrel' else 'points'
    distribution=[]
    for left,right in zip(series[:-2],series[1:-1]):
        if (datetime.fromisoformat(right['date'])-datetime.fromisoformat(left['date'])).days>4:continue
        if unit=='percent':value=(right['value']-left['value'])*100
        elif left['value']>0:value=(right['value']/left['value']-1)*100
        else:continue
        distribution.append(abs(value))
    distribution=distribution[-252:]
    percentile=None;attention='insufficient_history'
    gap=(datetime.fromisoformat(current['date'])-datetime.fromisoformat(previous['date'])).days
    if len(distribution)>=120 and gap<=4 and delta_unit in ('bp','%'):
        percentile=100*sum(x<=abs(delta) for x in distribution)/len(distribution)
        attention='normal' if delta==0 else 'exceptional' if percentile>=97.5 else 'elevated' if percentile>=90 else 'normal'
    return {'delta':round(delta,6),'unit':delta_unit,'from_date':previous['date'],'to_date':current['date'],
            'percentile':percentile,'sample_size':len(distribution),'attention':attention,'gap_days':gap}

class MarketStore:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS observations(metric TEXT,date TEXT,value REAL,seen TEXT,PRIMARY KEY(metric,date,seen));
            CREATE TABLE IF NOT EXISTS snapshots(id TEXT PRIMARY KEY,body TEXT);
            CREATE TABLE IF NOT EXISTS health(metric TEXT PRIMARY KEY,attempt TEXT,success TEXT,error TEXT);''')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=30)
        try:
            with db:yield db
        finally:db.close()
    def ingest(self,metric,series,seen):
        metric_ids([metric]);seen=utc(seen).isoformat()
        with self.connect() as db:
            for row in series:
                old=db.execute('SELECT value FROM observations WHERE metric=? AND date=? ORDER BY seen DESC LIMIT 1',(metric,row['date'])).fetchone()
                if old is None or old[0]!=row['value']:
                    db.execute('INSERT OR IGNORE INTO observations VALUES(?,?,?,?)',(metric,row['date'],row['value'],seen))
            db.execute('INSERT INTO health VALUES(?,?,?,NULL) ON CONFLICT(metric) DO UPDATE SET attempt=excluded.attempt,success=excluded.success,error=NULL',(metric,seen,seen))
    def failure(self,metric,seen,error):
        with self.connect() as db:
            db.execute('INSERT INTO health VALUES(?,?,NULL,?) ON CONFLICT(metric) DO UPDATE SET attempt=excluded.attempt,error=excluded.error',(metric,seen,error))
    def series(self,metric,as_of,limit=1000):
        metric_ids([metric]);as_of=utc(as_of).isoformat()
        if not isinstance(limit,int) or not 1<=limit<=1000:raise ValueError('limit 1..1000 required')
        with self.connect() as db:
            rows=db.execute('''SELECT a.date,a.value,a.seen FROM observations a WHERE a.metric=? AND a.seen<=? AND a.date<=? AND a.seen=(SELECT MAX(b.seen) FROM observations b WHERE b.metric=a.metric AND b.date=a.date AND b.seen<=?) ORDER BY a.date DESC LIMIT ?''',(metric,as_of,as_of[:10],as_of,limit)).fetchall()
        return [{'date':d,'value':v,'first_seen_at':t} for d,v,t in reversed(rows)]
    def health(self):
        with self.connect() as db:return [dict(zip(('metric_id','last_attempt','last_success','error'),r)) for r in db.execute('SELECT * FROM health')]
    def snapshot(self,as_of,ids=None,errors=None):
        at=utc(as_of);items=[];errors=list(errors or [])
        for metric in metric_ids(ids):
            series=self.series(metric,as_of)
            if not series:
                errors.append({'metric_id':metric,'code':'no_observations_asof'});continue
            age=(at.date()-datetime.fromisoformat(series[-1]['date']).date()).days
            # Daily statistics have publication lag; never call these real-time closes.
            quality='stale' if age>5 else 'latest_available'
            items.append({'metric_id':metric,**METRICS[metric], 'source_url':'https://fred.stlouisfed.org/series/'+METRICS[metric]['series'],
                'latest':series[-1], 'history':series[-60:], 'change':changes(series,METRICS[metric]['unit']),
                'quality':quality,'observation_age_days':age,'availability_basis':'first_seen','published_at':None})
        body={'schema_version':1,'as_of':at.isoformat(),'status':'partial' if items and errors else 'ok' if items else 'unavailable','items':items,'errors':errors}
        key=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()[:24];body['snapshot_id']=key
        with self.connect() as db:db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(key,json.dumps(body,ensure_ascii=False)))
        return body
    def get_snapshot(self,key):
        with self.connect() as db:row=db.execute('SELECT body FROM snapshots WHERE id=?',(key,)).fetchone()
        if row is None:raise ValueError('Unknown snapshot')
        return json.loads(row[0])

def collect(path,ids=None,fetcher=fetch_metric,now=None):
    store=MarketStore(path);errors=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending={pool.submit(fetcher,m):m for m in metric_ids(ids)}
        for future in as_completed(pending):
            m=pending[future];seen=now or datetime.now(timezone.utc).isoformat()
            try:store.ingest(m,future.result(),seen)
            except Exception as exc:
                code=type(exc).__name__;errors.append({'metric_id':m,'code':code});store.failure(m,seen,code)
    return store.snapshot(now or datetime.now(timezone.utc).isoformat(),ids,errors)
