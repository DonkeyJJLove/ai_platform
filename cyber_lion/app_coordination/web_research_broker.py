from dataclasses import dataclass,asdict
from datetime import datetime,timezone
from hashlib import sha256
from html.parser import HTMLParser
import http.client,ipaddress,socket,ssl,urllib.parse

DENIED_HOST_SUFFIXES=('.localhost','.local')

def resolve_public_https_target(url,resolver=socket.getaddrinfo):
    if not isinstance(url,str) or not url or len(url)>4096:raise ValueError('url')
    u=urllib.parse.urlsplit(url)
    if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('HTTPS public URL required')
    host=u.hostname.rstrip('.').lower()
    if host=='localhost' or host.endswith(DENIED_HOST_SUFFIXES):raise ValueError('local target denied')
    port=u.port or 443
    try:infos=resolver(host,port,type=socket.SOCK_STREAM)
    except TypeError:infos=resolver(host,port)
    ips=[]
    for row in infos:
        raw=row[4][0].split('%')[0]
        ip=ipaddress.ip_address(raw)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise ValueError('private/link-local/reserved target denied')
        if raw not in ips:ips.append(raw)
    if not ips:raise ValueError('no resolved address')
    return u,tuple(ips)

def validate_public_https_url(url,resolver=socket.getaddrinfo):
    resolve_public_https_target(url,resolver);return url

class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self,host,pinned_ip,port=443,timeout=8):
        super().__init__(host,port,timeout=timeout,context=ssl.create_default_context())
        self._pinned_ip=pinned_ip
    def _create_connection(self,address,timeout=socket._GLOBAL_DEFAULT_TIMEOUT,source_address=None):
        # The TLS SNI/certificate hostname remains self.host, but TCP is pinned to
        # the already-validated public IP. A second DNS answer cannot redirect the
        # connection into loopback/RFC1918 after the policy check.
        return socket.create_connection((self._pinned_ip,self.port),timeout,source_address)

@dataclass(frozen=True)
class WebEvidence:
    url:str;final_url:str;status:int;content_type:str;sha256:str;fetched_at:str;text:str;trust_class:str='UNTRUSTED_EXTERNAL_EVIDENCE';authority_effect:str='NONE';pinned_ip:str=''
    def as_dict(self):return asdict(self)

class _Parser(HTMLParser):
    def __init__(self):super().__init__();self.rows=[];self.href=None;self.buf=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='a' and ('result__a' in a.get('class','') or a.get('data-testid')=='result-title-a' or '/l/?uddg=' in a.get('href','')):self.href=a.get('href');self.buf=[]
    def handle_data(self,d):
        if self.href:self.buf.append(d)
    def handle_endtag(self,tag):
        if tag=='a' and self.href:self.rows.append((' '.join(''.join(self.buf).split()),self.href));self.href=None

class _RSSParser(HTMLParser):
    """Bounded RSS item extractor without XML entity/DTD processing."""
    def __init__(self):
        super().__init__(convert_charrefs=True);self.in_item=False;self.current=None;self.buf=[];self.title='';self.link='';self.rows=[]
    def handle_starttag(self,tag,attrs):
        tag=tag.lower()
        if tag=='item':self.in_item=True;self.title='';self.link='';self.current=None;self.buf=[]
        elif self.in_item and tag in {'title','link'}:self.current=tag;self.buf=[]
    def handle_data(self,data):
        if self.in_item and self.current:self.buf.append(data)
    def handle_endtag(self,tag):
        tag=tag.lower()
        if self.in_item and self.current==tag and tag in {'title','link'}:
            value=' '.join(''.join(self.buf).split())
            if tag=='title':self.title=value
            else:self.link=value
            self.current=None;self.buf=[]
        if tag=='item' and self.in_item:
            if self.title and self.link:self.rows.append((self.title,self.link))
            self.in_item=False;self.current=None;self.buf=[]

class PublicWebReadBroker:
    def __init__(self,resolver=socket.getaddrinfo,max_redirects=3):
        self.resolver=resolver;self.max_redirects=max_redirects
    def _once(self,url):
        u,ips=resolve_public_https_target(url,self.resolver);ip=ips[0]
        path=urllib.parse.urlunsplit(('', '',u.path or '/',u.query,''))
        c=_PinnedHTTPSConnection(u.hostname,ip,u.port or 443,timeout=8)
        try:
            c.request('GET',path,headers={'Host':u.hostname,'User-Agent':'LION-R10-readonly/2','Accept':'text/html,text/plain,application/json,application/xml'})
            r=c.getresponse();status=int(r.status);loc=r.getheader('Location')
            ctype=(r.getheader('Content-Type') or 'application/octet-stream').split(';',1)[0].strip().lower()
            if 300<=status<400 and loc:
                r.read(8192);return ('REDIRECT',urllib.parse.urljoin(url,loc),ip)
            if not (ctype.startswith('text/') or ctype in {'application/json','application/xml','application/xhtml+xml'}):raise ValueError('content type denied')
            b=r.read(2097153)
            if len(b)>2097152:raise ValueError('response too large')
            charset='utf-8'
            rawct=r.getheader('Content-Type') or ''
            for part in rawct.split(';')[1:]:
                if 'charset=' in part.lower():charset=part.split('=',1)[1].strip(' \"\'') or 'utf-8'
            return WebEvidence(url,url,status,ctype,sha256(b).hexdigest(),datetime.now(timezone.utc).isoformat(),b.decode(charset,'replace')[:2097152],pinned_ip=ip)
        finally:c.close()
    def fetch(self,url):
        original=url;cur=url
        for _ in range(self.max_redirects+1):
            out=self._once(cur)
            if isinstance(out,WebEvidence):
                return WebEvidence(original,cur,out.status,out.content_type,out.sha256,out.fetched_at,out.text,pinned_ip=out.pinned_ip)
            _,cur,_=out
            validate_public_https_url(cur,self.resolver)
        raise ValueError('redirect limit')
    def search(self,query,limit=5):
        if not isinstance(query,str) or not query.strip() or type(limit) is not int or not 1<=limit<=10:raise ValueError('query')
        providers=(('bing-rss','https://www.bing.com/search?format=rss&q='+urllib.parse.quote_plus(query)),('duckduckgo-lite','https://lite.duckduckgo.com/lite/?q='+urllib.parse.quote_plus(query)),('duckduckgo','https://html.duckduckgo.com/html/?q='+urllib.parse.quote_plus(query)),('bing','https://www.bing.com/search?q='+urllib.parse.quote_plus(query)))
        for provider,url in providers:
            try:
                ev=self.fetch(url);out=[]
                if provider=='bing-rss':
                    p=_RSSParser();p.feed(ev.text);p.close();rows=p.rows
                else:
                    p=_Parser();p.feed(ev.text);rows=p.rows
                for title,href in rows:
                    if href.startswith('//'):href='https:'+href
                    u=urllib.parse.urlsplit(href)
                    if 'duckduckgo.com' in (u.hostname or ''):href=urllib.parse.unquote((urllib.parse.parse_qs(u.query).get('uddg') or [''])[0])
                    try:validate_public_https_url(href,self.resolver)
                    except ValueError:continue
                    out.append({'provider':provider,'query':query,'title':title,'url':href,'searched_at':ev.fetched_at,'trust_class':'UNTRUSTED_EXTERNAL_EVIDENCE','result_digest':sha256((title+'\0'+href).encode()).hexdigest()})
                    if len(out)>=limit:return tuple(out)
                if out:return tuple(out)
            except Exception:continue
        raise ValueError('no public search provider available')
