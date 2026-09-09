#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, socket, sys
SOCKET='/run/lion-runner-exec.sock'; HEX40=re.compile(r'^[0-9a-f]{40}$'); HEX64=re.compile(r'^[0-9a-f]{64}$'); MAX=10*1024*1024

def rid(): return hashlib.sha256(os.urandom(32)).hexdigest()
def call(req):
    if os.geteuid()!=0: raise SystemExit('runner-exec client requires root caller')
    s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.connect(SOCKET); s.sendall(json.dumps(req,sort_keys=True,separators=(',',':')).encode()+b'\n'); s.shutdown(socket.SHUT_WR)
    data=bytearray()
    while True:
        p=s.recv(65536)
        if not p: break
        data.extend(p)
        if len(data)>MAX: raise SystemExit('runner-exec response too large')
    s.close(); v=json.loads(bytes(data).decode()); print(json.dumps(v,sort_keys=True,separators=(',',':'))); return 0 if v.get('ok') is True else 2
p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True); sub.add_parser('identity')
for n in ('static-unittest','static-pycompile'):
    q=sub.add_parser(n); q.add_argument('--repo-path',required=True); q.add_argument('--source-head',required=True); q.add_argument('--source-tree',required=True)
q=sub.add_parser('provider-call'); q.add_argument('--provider-operation',choices=['PING','LIST_FLEET_RESOURCES'],required=True); q.add_argument('--source-head',required=True); q.add_argument('--source-tree',required=True)
q=sub.add_parser('pod-provider-call'); q.add_argument('--provider-operation',choices=['PRECHECK_POD_RUNTIMIË	Ô‘TT‘WÓĞĞSÒÎÉË	ÓPUT’PSV‘WÕ’ÕÔÑÉË	Ô‘PQÔÑÑU’QSÑIË	ÔÕÔÕ’ÕÔÑÉ×K™\]Z\™YUYJNÈK˜YØ\™İ[Y[
	ËK\Ûİ\˜ÙKZXY	Ë™\]Z\™YUYJNÈK˜YØ\™İ[Y[
	ËK\Ûİ\˜ÙK]™YIË™\]Z\™YUYJNÈK˜YØ\™İ[Y[
	ËK\[‹ZY	Ë™\]Z\™YUYJBœO\İX‹˜YÜ\œÙ\Š	ÜØØ[M\[‰ÊNÈK˜YØ\™İ[Y[
	ËK\Ûİ\˜ÙKZXY	Ë™\]Z\™YUYJNÈK˜YØ\™İ[Y[
	ËK\Ûİ\˜ÙK]™YIË™\]Z\™YUYJNÈK˜YØ\™İ[Y[
	ËK\[‹\™\]Y\İZY	Ë™\]Z\™YUYJB˜O\œ\œÙWØ\™ÜÊ
NÈ™\O^ÉÜØÚ[XWİ™\œÚ[Û‰Î‰ÌKŒŒ	Ë	Ü™\]Y\İÚY	ÎœšY

_BšYˆK˜ÛYOIÚY[]IÎˆ™\VÉÛÜ\˜][Û‰×OIÒQS•UIÂ™[YˆK˜ÛY[ˆ
	Üİ]XË][š]\İ	Ë	Üİ]XË\XÛÛ\[IÊN‚ˆYˆ›İV™[X]Ú
KœÛİ\˜ÙWÚXY
HÜˆ›İV™[X]Ú
KœÛİ\˜ÙWİ™YJNˆ˜Z\ÙHŞ\İ[Q^]
	Ú[˜[YÛİ\˜ÙHY[]IÊBˆ™\K\]JÜ\˜][ÛIÔÕUP×ÕS’UTÕ	ÈYˆK˜ÛYOIÜİ]XË][š]\İ	È[ÙH	ÔÕUP×ÔPÓÓTSIË™\×Ü]XKœ™\×Ü]Ûİ\˜ÙWÚXYXKœÛİ\˜ÙWÚXYÛİ\˜ÙWİ™YOXKœÛİ\˜ÙWİ™YJB™[YˆK˜ÛYOIÜ›İšY\‹XØ[	Î‚ˆYˆ›İV™[X]Ú
KœÛİ\˜ÙWÚXY
HÜˆ›İV™[X]Ú
KœÛİ\˜ÙWİ™YJNˆ˜Z\ÙHŞ\İ[Q^]
	Ú[˜[YÛİ\˜ÙHY[]IÊBˆ™\K\]JÜ\˜][ÛIÔ“Õ’QT—ĞĞS	Ë›İšY\—ÛÜ\˜][ÛXKœ›İšY\—ÛÜ\˜][Û‹Ûİ\˜ÙWÚXYXKœÛİ\˜ÙWÚXYÛİ\˜ÙWİ™YOXKœÛİ\˜ÙWİ™YJB™[YˆK˜ÛYOIÜÙ\›İšY\‹XØ[	Î‚ˆYˆ›İV™[X]Ú
KœÛİ\˜ÙWÚXY
HÜˆ›İV™[X]Ú
KœÛİ\˜ÙWİ™YJNˆ˜Z\ÙHŞ\İ[Q^]
	Ú[˜[YÛİ\˜ÙHY[]IÊBˆYˆ›İ™K™[X]Ú
‰ÖĞKV˜K^ŒNWVĞKV˜K^ŒNK—Î‹W^ÌLßIËKœ[—ÚY
Nˆ˜Z\ÙHŞ\İ[Q^]
	Ú[˜[Y[ˆY	ÊBˆ™\K\]JÜ\˜][ÛIÔÑÔ“Õ’QT—ĞĞS	Ë›İšY\—ÛÜ\˜][ÛXKœ›İšY\—ÛÜ\˜][Û‹Ûİ\˜ÙWÚXYXKœÛİ\˜ÙWÚXYÛİ\˜ÙWİ™YOXKœÛİ\˜ÙWİ™YK[—ÚYXKœ[—ÚY
B™[ÙN‚ˆYˆ›İV™[X]Ú
KœÛİ\˜ÙWÚXY
HÜˆ›İV™[X]Ú
KœÛİ\˜ÙWİ™YJHÜˆ›İV™[X]Ú
Kœ[—Ü™\]Y\İÚY
Nˆ˜Z\ÙHŞ\İ[Q^]
	Ú[˜[YØØ[MY[]IÊBˆ™\K\]JÜ\˜][ÛIÔĞĞSMÔ•S‰ËÛİ\˜ÙWÚXYXKœÛİ\˜ÙWÚXYÛİ\˜ÙWİ™YOXKœÛİ\˜ÙWİ™YK[—Ü™\]Y\İÚYXKœ[—Ü™\]Y\İÚY
Bœ˜Z\ÙHŞ\İ[Q^]
Ø[
™\JJB