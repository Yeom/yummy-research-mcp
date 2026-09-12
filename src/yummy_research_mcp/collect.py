"""Operational CLI. MCP readers never initiate bulk market writes."""
import argparse
import json
from pathlib import Path
from .market import collect, default_db, MarketStore
from .filings import search_news, get_filings

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['collect','snapshot','chart','news','filings'])
    parser.add_argument('--db',default=str(default_db()))
    parser.add_argument('--as-of');parser.add_argument('--since');parser.add_argument('--query')
    parser.add_argument('--snapshot-id');parser.add_argument('--out');parser.add_argument('--market');parser.add_argument('--company-id')
    args=parser.parse_args()
    if args.action=='collect':result=collect(args.db)
    elif args.action=='snapshot':result=MarketStore(args.db).snapshot(args.as_of)
    elif args.action=='news':result=search_news(args.query,args.since,args.as_of)
    elif args.action=='filings':result=get_filings(args.market,args.company_id,args.since,args.as_of)
    else:
        from .charts import render
        snapshot=MarketStore(args.db).get_snapshot(args.snapshot_id)
        result=render(snapshot,Path(args.out))
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
