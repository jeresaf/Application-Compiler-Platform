"""Deterministic packaged 2026d transition projection, no OS/JVM authority.

CPython's pinned TZif reader supplies explicit transitions and POSIX footer rules.
The declared finite target horizon rejects dates outside packaged coverage.
"""
import argparse
from datetime import datetime,timezone
from importlib.resources import files
import hashlib
import json
from pathlib import Path
from zoneinfo import _zoneinfo
import tzdata

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'targets/spring-vue-postgres/templates/backend/src/main/resources/acp-tzdb-2026d.json'

def package():
    if tzdata.IANA_VERSION!='2026d':raise ValueError('PINNED_TZDB_VERSION')
    start=int(datetime(1900,1,1,tzinfo=timezone.utc).timestamp());end=int(datetime(2101,1,1,tzinfo=timezone.utc).timestamp());zones={}
    for name in ('Africa/Nairobi','America/New_York','Europe/Berlin'):
        resource=files('tzdata.zoneinfo').joinpath(*name.split('/'));raw=resource.read_bytes()
        with resource.open('rb') as f:zone=_zoneinfo.ZoneInfo.from_file(f,key=name)
        pairs=[(t,int(info.utcoff.total_seconds())) for t,info in zip(zone._trans_utc,zone._ttinfos) if start<t<end]
        after=zone._tz_after
        if hasattr(after,'transitions'):
            last=zone._trans_utc[-1]
            for year in range(max(1899,datetime.fromtimestamp(last,timezone.utc).year-1),2102):
                begin,finish=after.transitions(year)
                for t,offset in ((begin-int(after.std.utcoff.total_seconds()),int(after.dst.utcoff.total_seconds())),(finish-int(after.dst.utcoff.total_seconds()),int(after.std.utcoff.total_seconds()))):
                    if max(start,last)<t<end:pairs.append((t,offset))
        initial=int(datetime.fromtimestamp(start,timezone.utc).astimezone(zone).utcoffset().total_seconds());transitions=[[start,initial]]
        for t,offset in sorted(set(pairs)):
            if offset!=transitions[-1][1]:transitions.append([t,offset])
        zones[name]={'tzifSha256':hashlib.sha256(raw).hexdigest(),'transitions':transitions}
    return json.dumps({'version':'2026d','source':'https://www.iana.org/time-zones/releases/2026d','package':'tzdata/'+tzdata.__version__,'start':start,'end':end,'zones':zones},separators=(',',':'))+'\n'

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args();data=package()
    if args.check:
        if DEST.read_text()!=data:raise ValueError('PINNED_TZDB_ARTIFACT_MISMATCH')
    else:DEST.write_text(data)
    print('PINNED_TZDB_2026d = PASS; sha256:'+hashlib.sha256(data.encode()).hexdigest())
