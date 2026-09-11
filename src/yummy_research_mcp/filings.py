"""Public filing/news discovery. Titles are leads, never verified article contents."""
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode, quote
from .http import http_get
from .settings import setting
from .market import utc

def parse_sec(data,cik,since,as_of):
    lower,upper=utc(since),utc(as_of);out=[]
    recent=data.get('filings',{}).get('recent',{})
    for i,accession in enumerate(recent.get('accessionNumber',[])):
        times=recent.get('acceptanceDateTime',[])
        if i>=len(times) or not times[i]:continue
        if not lower<utc(times[i])<=upper:continue
        doc=recent.get('primaryDocument',[])[i]
        out.append({'id':accession,'form':recent.get('form',[])[i],'published_at':times[i],
                    'url':f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-", "")}/{quote(doc)}'})
    return out

def get_filings(market,company_id,since,as_of):
    if market not in ('KR','US') or not re.fullmatch(r'\d{1,10}',company_id):raise ValueError('Invalid company identifier')
    if utc(since)>=utc(as_of) or (utc(as_of)-utc(since)).days>90:raise ValueError('Invalid filing window')
    try:
        if market=='US':
            agent=setting('SEC_USER_AGENT')
            if not agent:return {'status':'unavailable','items':[],'error':'source_not_configured'}
            data=json.loads(http_get(f'https://data.sec.gov/submissions/CIK{int(company_id):010d}.json',{'User-Agent':agent}))
            return {'status':'ok','items':parse_sec(data,company_id,since,as_of),'coverage':'recent_submissions'}
        key=setting('DART_API_KEY')
        if not key:return {'status':'unavailable','items':[],'error':'source_not_configured'}
        items=[]
        for page in range(1,11):
            query=urlencode({'crtfc_key':key,'corp_code':company_id.zfill(8),'bgn_de':utc(since).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Seoul')).strftime('%Y%m%d'),'end_de':utc(as_of).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Seoul')).strftime('%Y%m%d'),'page_count':100,'page_no':page})
            data=json.loads(http_get('https://opendart.fss.or.kr/api/list.json?'+query))
            if data.get('status')=='013':break
            if data.get('status')!='000':return {'status':'unavailable','items':[],'error':'provider_rejected'}
            for row in data.get('list',[]):
                items.append({'id':row['rcept_no'],'title':row['report_nm'],'published_date':row['rcept_dt'],
                    'published_at':None,'availability_basis':'date_only','url':'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+row['rcept_no']})
            if page>=int(data.get('total_page',1)):break
        return {'status':'partial' if int(data.get('total_page',0))>10 else 'ok','items':items,'coverage':'filing_dates_only_no_intraday_guarantee'}
    except Exception as exc:return {'status':'unavailable','items':[],'error':type(exc).__name__}

def search_news(query,since,as_of,limit=15):
    if not isinstance(query,str) or not 1<=len(query)<=150 or not isinstance(limit,int) or not 1<=limit<=30:raise ValueError('Invalid news query/limit')
    lower,upper=utc(since),utc(as_of)
    if lower>=upper:raise ValueError('Invalid time window')
    url='https://news.google.com/rss/search?'+urlencode({'q':query+' when:7d','hl':'ko','gl':'KR','ceid':'KR:ko'})
    try:
        root=ET.fromstring(http_get(url,timeout=12));items=[]
        for item in root.findall('./channel/item'):
            date=item.findtext('pubDate')
            if not date:continue
            when=parsedate_to_datetime(date).astimezone(timezone.utc)
            if not lower<when<=upper:continue
            items.append({'title':item.findtext('title'),'url':item.findtext('link'),'source':item.findtext('source'),
                          'published_at':when.isoformat(),'verification':'headline_only'})
        items.sort(key=lambda x:x['published_at'],reverse=True)
        return {'status':'ok','items':items[:limit],'truncated':len(items)>limit,'coverage':'Google News RSS discovery, not exhaustive'}
    except Exception as exc:return {'status':'unavailable','items':[],'error':type(exc).__name__}
