"""Operator helper. Credentials are read from environment, never CLI arguments."""
import argparse
from datetime import datetime
import json
import os
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

def main():
    parser=argparse.ArgumentParser(description='May Bloom membership service operations')
    parser.add_argument('action',choices=['summary','jobs','slot','close-slot'])
    parser.add_argument('--at',help='Timezone-aware ISO timestamp, e.g. YYYY-MM-DDTHH:MM:SS+08:00')
    parser.add_argument('--slot-id',help='Existing slot identifier to close before it is booked')
    args=parser.parse_args()
    origin=os.environ['MB_PUBLIC_URL'].rstrip('/')
    parsed=urlsplit(origin)
    if parsed.scheme!='https' or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        parser.error('MB_PUBLIC_URL must be an HTTPS origin.')
    body=None
    if args.action=='slot':
        at=datetime.fromisoformat(args.at or '')
        if at.tzinfo is None: parser.error('Use an explicit timezone; Malaysia is +08:00.')
        path='/admin/slots';body={'starts_at':int(at.timestamp())}
    elif args.action=='close-slot':
        if not args.slot_id: parser.error('--slot-id is required.')
        path='/admin/close-slot';body={'slot_id':args.slot_id}
    elif args.action=='jobs': path='/admin/run-jobs';body={}
    else: path='/admin/summary'
    request=Request(origin+path,data=None if body is None else json.dumps(body).encode(),
                    headers={'Authorization':'Bearer '+os.environ['MB_ADMIN_KEY'],'Content-Type':'application/json'})
    with urlopen(request,timeout=45) as response: print(json.dumps(json.load(response),ensure_ascii=False,indent=2))

if __name__=='__main__': main()
