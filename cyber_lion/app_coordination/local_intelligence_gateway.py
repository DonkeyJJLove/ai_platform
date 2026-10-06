# R10 R2 unified local intelligence gateway. Pure orchestration only.
from __future__ import annotations
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from hashlib import sha256
import json,re,secrets,threading,time,uuid
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit,unquote,parse_qs
from .lion_context_provider import build_lion_context
from .rag_tool_adapter import RagIndex
from .repository_read_adapter import RepositoryReader
from .currentness_tool_adapter import read_currentness
from .web_research_broker import PublicWebReadBroker
from .local_tool_protocol import ToolCall,parse_tool_call
from .local_tool_gate import evaluate_tool_call
from .conversation_domain import ConversationDomainError, ConversationConflict, ConversationNotFound
from .conversation_chat import submit_chat
from .cognitive_continuity import (
    active_saas_bridge,
    build_mission_cognitive_continuity,
    build_synchronization_checkpoint,
    provider_requirements,
)
from cyber_lion.contracts.cognitive_continuity import (
    CognitiveContinuityContractError,
    validate_synchronization_checkpoint,
)
from cyber_lion.contracts.attachment_projection import ProviderCapabilitySnapshot
from .r24_model_chat_ui import R24_MODEL_CHAT_UI

SENSITIVE=("push","merge","delete branch","delete ref","remove branch","usuń gałą","usun galaz","usuń branch","usun branch","credential","trust anchor","authority decision","autoryzacj","deploy production","runtime authority","force push")
REPO_WORDS=('repo','repository','repozytor','branch','gałą','galaz','master','commit','tree',' head','git','federac','source','źródło lokalne','zrodlo lokalne','stan projektu')
FED_WORDS=('federac','10 repo','repozytori','stan repo')
WEB_WORDS=('najnowsz','aktualne','dzisiaj','today','latest','news','wiadomo','internet','sieć','siec',' web','strona','site','domain','domena','http','https','wyszukaj','znajdź','znajdz','sprawdź w sieci','sprawdz w sieci')
LOCAL_SOURCE_WORDS=('plik','file ','kod źródł','kod zrodl','local source','źródło lokalne','zrodlo lokalne')
CAPABILITY_WORDS=('hybryd','hybrid','saas','chatgpt','proxy','remote model','zdaln model','local model','lokaln model','modele remote','modele local','selfupgrade','self-upgrade','self upgrade','lpcl','lcpl','token','koszt','cena','pricing','pakiet','abonament','subscription','czy muszę używać api','czy musze uzywac api','api w tym interfejsie','masz dostęp','masz dostep','dostęp do github','dostep do github','co robi lion','czym jest lion','what can lion','what is lion','lion teraz','lion w tym momencie')


class _PageEvidenceParser(HTMLParser):
    def __init__(self,base_url,site_root):
        super().__init__();self.base_url=base_url;self.site_root=site_root;self.active=None;self.buf=[];self.rows=[];self.anchor_href=None;self.anchor_buf=[]
    def _add(self,kind,text,href=None):
        text=' '.join(''.join(text).split()) if isinstance(text,list) else ' '.join(str(text).split())
        if not 18<=len(text)<=260:return
        url=None
        if href:
            try:
                url=urljoin(self.base_url,href);host=(urlsplit(url).hostname or '').lower()
                if host.startswith('www.'):host=host[4:]
                if host!=self.site_root and not host.endswith('.'+self.site_root):return
            except Exception:return
        key=(text.lower(),url or '')
        if key not in {(x['text'].lower(),x.get('url') or '') for x in self.rows}:self.rows.append({'kind':kind,'text':text,'url':url})
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.anchor_href=dict(attrs).get('href');self.anchor_buf=[]
        if tag in {'title','h1','h2','h3'}:self.active=tag;self.buf=[]
    def handle_data(self,data):
        if self.active:self.buf.append(data)
        elif self.anchor_href:self.anchor_buf.append(data)
    def handle_endtag(self,tag):
        if tag==self.active:
            self._add(tag,self.buf,self.anchor_href);self.active=None;self.buf=[]
        if tag=='a':
            if self.anchor_buf:self._add('a',self.anchor_buf,self.anchor_href)
            self.anchor_href=None;self.anchor_buf=[]

def _site_root(host):
    host=(host or '').lower().strip('.');return host[4:] if host.startswith('www.') else host

def _named_domain(message):
    m=re.search(r'\b((?:[a-z0-9-]+\.)+(?:pl|com|org|net|io|ai|dev))\b',message.lower());return m.group(1) if m else None

def _same_site(url,root):
    try:
        host=(urlsplit(url).hostname or '').lower().lstrip('www.');return host==root or host.endswith('.'+root)
    except Exception:return False

def _page_evidence(fetch_row,domain,limit=24):
    if not isinstance(fetch_row,dict) or fetch_row.get('content_type')!='text/html':return []
    base=fetch_row.get('final_url') or fetch_row.get('url') or ('https://'+domain);p=_PageEvidenceParser(base,_site_root(domain))
    try:p.feed(fetch_row.get('text',''))
    except Exception:return []
    # Prefer headings and substantive same-site anchors; preserve page order inside each tier.
    ranked=sorted(enumerate(p.rows),key=lambda z:(0 if z[1]['kind'] in {'h1','h2','h3'} else 1,z[0]))
    return [row for _,row in ranked[:limit]]

UI=r'''<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="frontend-revision" content="__FRONTEND_REVISION__"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LION CONTROL LPCL PANEL</title>
<style>
:root{color-scheme:dark;--bg:#091018;--panel:#0c1620;--panel2:#101c27;--line:#294052;--text:#e8f0f6;--muted:#8da6b8;--accent:#2d8693;--user:#173344;--assistant:#0d1923;--ok:#75d7a5;--warn:#e6c56a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 Inter,Segoe UI,system-ui,sans-serif}.app{max-width:1220px;margin:auto;padding:24px}.top{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.top h1{margin:.1rem 0;font-size:26px}.subtitle{color:var(--muted);margin:0 0 14px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:14px 0}.card{border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:var(--panel)}.k{color:#80a9bd;font-size:10px;letter-spacing:.07em}.v{font-weight:650;font-size:13px;overflow-wrap:anywhere}.chat{border:1px solid var(--line);border-radius:14px;background:var(--panel);min-height:420px;display:flex;flex-direction:column;overflow:hidden}.messages{padding:18px;display:flex;flex-direction:column;gap:14px;min-height:320px}.msg{max-width:92%;border:1px solid var(--line);border-radius:12px;padding:12px 14px}.msg.user{align-self:flex-end;background:var(--user);max-width:80%}.msg.assistant{align-self:flex-start;background:var(--assistant);width:min(920px,95%)}.role{font-size:11px;color:var(--muted);margin-bottom:6px}.composer{border-top:1px solid var(--line);padding:12px;background:#0b151e;position:sticky;bottom:0}.composer textarea{width:100%;resize:vertical;min-height:74px;max-height:220px;background:#071019;color:var(--text);border:1px solid var(--line);border-radius:10px;padding:11px}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px}button,select,input{background:#15303d;color:var(--text);border:1px solid #35576a;border-radius:8px;padding:8px 12px}button.primary{background:var(--accent);border-color:var(--accent)}button:disabled{opacity:.5}.grow{flex:1}.status{color:var(--muted);font-size:12px}.evidence{margin-top:12px;border:1px solid var(--line);border-radius:12px;background:var(--panel);padding:12px}.evidence h3{margin:0 0 8px;font-size:14px}.chips{display:flex;gap:6px;flex-wrap:wrap}.chip{border:1px solid var(--line);border-radius:999px;padding:3px 8px;font-size:11px;color:#b9cfdb}.source{padding:7px 0;border-top:1px solid #1b2b37;font-size:12px}.source a{color:#7fc6e3}.hide{display:none}.md p{margin:.55em 0}.md h1,.md h2,.md h3{margin:.9em 0 .4em}.md h1{font-size:1.45em}.md h2{font-size:1.25em}.md h3{font-size:1.1em}.md code{background:#172633;padding:.1em .35em;border-radius:4px}.md pre{overflow:auto;background:#071019;border:1px solid #263d4d;padding:11px;border-radius:8px}.md pre code{background:transparent;padding:0}.md table{border-collapse:collapse;width:100%;margin:.8em 0;font-size:13px}.md th,.md td{border:1px solid #365063;padding:7px 8px;text-align:left;vertical-align:top}.md th{background:#132433}.md ul,.md ol{padding-left:1.4em}.md blockquote{border-left:3px solid #3e738a;padding-left:10px;color:#b7cad4}.toolbar{display:flex;gap:6px;margin-top:8px}.debug{white-space:pre-wrap;max-height:420px;overflow:auto;background:#050b10;border:1px solid var(--line);padding:10px;border-radius:8px;font:12px/1.45 Consolas,monospace}.ok{color:var(--ok)}.warn{color:var(--warn)}

.layout{display:grid;grid-template-columns:280px minmax(0,1fr);min-height:100vh}.sidebar{border-right:1px solid var(--line);background:#071018;padding:14px;position:sticky;top:0;height:100vh;overflow:auto}.sidebar h2{font-size:15px;margin:12px 0}.thread-new{width:100%;margin-bottom:12px}.thread-list{display:flex;flex-direction:column;gap:5px}.thread{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:4px;align-items:center;border:1px solid transparent;border-radius:8px;padding:4px}.thread.active{background:#102331;border-color:#2f5a70}.thread-open{background:none;border:0;color:var(--text);text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:7px;cursor:pointer}.thread-icon{background:none;border:0;color:#9db2bf;padding:4px 6px;cursor:pointer}.sidebar .meta{font-size:11px;color:var(--muted);border-top:1px solid var(--line);margin-top:16px;padding-top:12px}.saas-unavailable{color:var(--warn)}.app{max-width:none!important}.thread-title{font-size:12px;color:var(--muted)}@media(max-width:900px){.layout{grid-template-columns:1fr}.sidebar{position:relative;height:auto;border-right:0;border-bottom:1px solid var(--line);max-height:280px}}

.control-panel{border:1px solid var(--line);border-radius:12px;background:var(--panel);padding:14px;margin:12px 0}.control-panel h2{margin:0;font-size:18px}.mission-objective{font-size:15px;font-weight:650;margin:8px 0}.mission-progress-head{display:flex;justify-content:space-between;gap:10px;color:#b9cbd6}.mission-progress{height:9px;background:#21313c;border-radius:999px;overflow:hidden;margin:6px 0 10px}.mission-progress i{display:block;height:100%;background:linear-gradient(90deg,#62dca5,#68bfe9)}.phase-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:7px}.phase-card{border:1px solid #2d404c;border-radius:8px;padding:8px;background:#09141c}.phase-card>div:first-child{display:flex;justify-content:space-between;gap:7px}.phase-card small{display:block;color:var(--muted);margin-top:4px}.protocol-filters{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:7px}.proto-btn{background:#0d1a23;border:1px solid #344d5c;color:#bcd2dd;border-radius:999px;padding:4px 8px;font-size:10px;cursor:pointer}.proto-btn.active{border-color:#6bc7e9;background:#15364a}.protocol-feed{max-height:240px;overflow:auto;border:1px solid #273b48;border-radius:8px;padding:7px;background:#071018}.proto-msg{font:10px/1.45 Consolas,monospace;padding:6px 2px;border-bottom:1px solid #20303a}.proto-msg .muted{color:#819aa9}.lpcl-grid{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(280px,.55fr);gap:10px}.lpcl-box{width:100%;height:280px;resize:vertical;background:#061019;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:10px;font:11px/1.45 Consolas,monospace}.lpcl-preview{white-space:pre-wrap;overflow:auto;max-height:280px;background:#061019;border:1px solid #293f4d;border-radius:8px;padding:9px;font:10px/1.45 Consolas,monospace}.mission-list{display:flex;flex-direction:column;gap:5px}.mission-item{display:block;width:100%;background:#0b1822;border:1px solid #283f4e;color:var(--text);border-radius:8px;padding:8px;text-align:left;cursor:pointer}.mission-item.active{border-color:#65c6e8;background:#123041}.mission-item b,.mission-item span,.mission-item small{display:block;overflow:hidden;text-overflow:ellipsis}.mission-item span,.mission-item small{font-size:10px;color:var(--muted);margin-top:2px;white-space:normal}.control-grid{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(320px,.8fr);gap:10px}.control-health{color:#9dd5ea}.lpcl-state{font-size:11px;color:var(--muted)}@media(max-width:1000px){.lpcl-grid,.control-grid{grid-template-columns:1fr}}

/* Epoch3 stable viewport: document does not scroll; app/sidebar own scroll, composer stays visible. */
html,body{height:100%;overflow:hidden}.layout{height:100vh;min-height:0}.app{height:100vh;min-height:0;overflow:auto;padding-bottom:150px}.composer{position:fixed;left:280px;right:0;bottom:0;z-index:40;box-shadow:0 -12px 28px #0009}.messages{overflow:auto}.proto-labels{display:flex;gap:5px;flex-wrap:wrap;margin-top:3px}.proto-labels span{border:1px solid #365365;border-radius:999px;padding:2px 6px;color:#a9c9d8}.proto-raw summary{cursor:pointer;color:#75bddc}.proto-raw pre{max-height:260px;overflow:auto;white-space:pre-wrap}@media(max-width:900px){.composer{left:0}.app{padding-bottom:175px}}

.phase-card{min-width:0;max-width:100%;overflow-wrap:anywhere}.phase-card>div{min-width:0;flex-wrap:wrap}.phase-card b{display:block;min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:break-word}.phase-card span{flex-shrink:0}

/* Bounded semantic inspections and responsive phase labels. */
.semantic-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr));gap:12px}.semantic-card{min-width:0;border:1px solid #35505e;border-radius:9px;padding:12px;margin:8px 0;background:#101b24;overflow-wrap:anywhere}.semantic-card h3{margin:0 0 10px;font-size:14px;white-space:normal;overflow-wrap:anywhere;word-break:break-word}.semantic-card dl{display:grid;grid-template-columns:minmax(80px,1fr) minmax(0,2fr);gap:6px 10px;margin:0;font-size:12px}.semantic-card dt{color:#9ab2c3}.semantic-card dd{margin:0;min-width:0;overflow-wrap:anywhere}.semantic-raw{margin-top:10px}.semantic-raw summary{cursor:pointer;color:#85c9e6}.semantic-raw pre{max-height:300px;max-width:100%;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere}.semantic-events{max-height:500px;overflow:auto}.phase-grid,.control-grid,.mc-process-grid,.mc-phase,.phase-card{min-width:0}.phase-card>div:first-child,.mc-phase>div:first-child{flex-wrap:wrap;min-width:0}.phase-card b,.mc-phase b{min-width:0;white-space:normal;overflow-wrap:anywhere}.layout,.app,.sidebar,.control-panel,.mc-v3{min-width:0}#missionPhases,#mcPhases{min-width:0}#mcV3Workers td{white-space:normal}#adapters,#hosts{display:grid;gap:10px}.card{min-width:0}#mcSupervisorCards .v{font-size:14px}@media(max-width:650px){.semantic-card dl{grid-template-columns:minmax(0,1fr)}.semantic-card dd{margin-bottom:5px}.control-grid,.detail-grid{grid-template-columns:minmax(0,1fr)}.mc-picker{min-width:0;max-width:100%}.mc-picker label{min-width:0;max-width:100%}.mc-picker select{min-width:0;max-width:100%}}
/* Keep the grid item within its track and wrap long live identities. */
.app{width:100%;max-width:100%;overflow-wrap:anywhere}.top{flex-wrap:wrap}.top>*{min-width:0;max-width:100%}.app select{max-width:100%}.mission-progress-head{flex-wrap:wrap}
/* Compact summaries; full values stay available on hover, focus and RAW disclosure. */
.cards{display:flex!important;flex-wrap:wrap;gap:6px;margin:8px 0}.card{display:inline-flex;align-items:center;gap:6px;padding:4px 7px;border-radius:6px;max-width:100%}.card .k,.card .v{margin:0;line-height:1.3}.card .k{font-size:9px}.card .v{font-size:11px!important;max-width:30ch;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.semantic-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:6px}.semantic-card{position:relative;padding:7px 9px;margin:3px 0;border-radius:7px}.semantic-card h3{font-size:12px;margin:0 0 5px;line-height:1.35}.compact-facts{display:flex;gap:4px;flex-wrap:wrap}.compact-fact{font-size:10px;line-height:1.4;padding:2px 5px;border:1px solid #35505e;border-radius:12px;color:#abc2d0;cursor:help}.compact-fact:focus-visible{outline:2px solid #85c9e6}.compact-tooltip{display:none;position:absolute;left:0;right:0;top:100%;z-index:80;background:#071019;color:#e7f2fa;border:1px solid #55788d;padding:10px;border-radius:6px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:220px;overflow:auto;box-shadow:0 6px 18px #0009}.compact-fact:hover .compact-tooltip,.compact-fact:focus .compact-tooltip{display:block}.semantic-raw{margin-top:3px;font-size:10px}.phase-actions:empty{display:none}.phase-actions button{font-size:10px;padding:3px 7px}
.semantic-events,#recentEvents,#events,#phases{display:flex;flex-wrap:wrap;align-content:flex-start;gap:5px}.semantic-event{display:inline-flex;align-items:center;gap:6px;max-width:100%;padding:4px 8px}.semantic-event h3{font-size:10px;margin:0;cursor:help}.semantic-event .semantic-raw{margin:0}.semantic-event details[open]{width:100%}.semantic-event:has(details[open]){flex-wrap:wrap;width:100%}.tone-info{border-color:#356b91}.tone-good{border-color:#328563}.tone-warn{border-color:#998037}.tone-bad{border-color:#a34c62}
.mission-item{padding:5px 7px}.mission-item b{font-size:11px;white-space:nowrap;text-overflow:ellipsis;overflow:hidden}.mission-item small{display:none}.mission-item span{font-size:9px}.control-panel,.panel{padding:10px}.control-panel h2,.panel h2{font-size:16px}.mission-objective,.mc-objective .objective{font-size:12px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.mc-objective{padding:7px;margin:7px 0}.mc-driver-state{padding:6px}.mc-schema-notice{padding:6px;font-size:11px}.mc-picker{width:100%;min-width:0}.mc-picker label{flex:1;min-width:0;max-width:100%}.mc-picker select,select{min-width:0!important;max-width:100%;text-overflow:ellipsis}.mc-picker select{width:100%;box-sizing:border-box}.mc-reg{font-size:11px;padding:5px 7px}.mc-reg small{display:none}


.event-label{font:inherit;font-size:10px;padding:2px 5px;background:transparent;border:0;color:inherit;cursor:pointer}.tone-info .event-label{color:#8bcafa}.tone-good .event-label{color:#80ddb0}.tone-warn .event-label{color:#f0d376}.tone-bad .event-label{color:#f6a2b3}.mission-item{max-width:100%;overflow:hidden}.mission-item b,.mission-item span{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

.semantic-card h3{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.compact-fact{padding:1px 4px}.compact-fact>span[aria-hidden]{display:none}

/* R24 complementary composition: one LPCL shell, compact canonical chat module. */
.complementary-tabs{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}.complementary-tabs a{color:#bcd3df;text-decoration:none;border:1px solid var(--line);border-radius:8px;padding:5px 9px;background:#0b1822}
.cmc-toolbar{display:flex;gap:6px;flex-wrap:wrap;align-items:center}.cmc-toolbar select{min-width:min(100%,360px);flex:1}
.cmc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:6px;margin:8px 0}.cmc-card{border:1px solid var(--line);border-radius:8px;padding:6px 8px;background:#09141c;min-width:0}.cmc-card .k{font-size:9px}.cmc-card .v{font:11px/1.4 Consolas,monospace;overflow-wrap:anywhere}
.cmc-bridge{border:1px solid #68528c;border-radius:9px;padding:8px;background:#0c1420;margin:8px 0}.cmc-bridge input{min-width:min(100%,360px);flex:1}.cmc-bridge-state{font:11px/1.45 Consolas,monospace;color:#cdbceb;overflow-wrap:anywhere}
.cmc-messages{min-height:160px;max-height:360px;overflow:auto;border:1px solid var(--line);border-radius:9px;padding:10px;background:#071018;display:flex;flex-direction:column;gap:8px}.cmc-msg{border:1px solid var(--line);border-radius:9px;padding:8px 10px;max-width:92%;white-space:pre-wrap}.cmc-msg.USER{align-self:flex-end;background:#173344;max-width:82%}.cmc-msg.ASSISTANT{align-self:flex-start;background:#0d1923}.cmc-role{font-size:9px;color:var(--muted);margin-bottom:4px}.cmc-composer textarea{width:100%;min-height:76px;resize:vertical;background:#061019;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:9px}.cmc-pending{font:11px Consolas,monospace;color:var(--warn)}
.legacy-archive{font-size:11px;color:var(--muted)}.legacy-archive summary{cursor:pointer}.legacy-row{padding:5px 0;border-bottom:1px solid #1b2b37}
@media(max-width:900px){.cmc-toolbar>*{max-width:100%}.cmc-grid{grid-template-columns:1fr 1fr}}
@media(max-width:620px){.cmc-grid{grid-template-columns:1fr}}
</style></head><body><div class="layout"><aside class="sidebar"><h2>Misje <button id="missionHistoryToggle" type="button" onclick="toggleMissionView()">History / Legacy</button></h2><div id="missionList" class="mission-list"></div><details class="legacy-archive"><summary>Archiwum legacy · read-only</summary><div id="threadList" class="thread-list"></div></details><div class="meta"><b>Control plane</b><br>Mission Control: 8766<br>Operator Gateway: 8767<br>LPCL intake: ACTIVE<br>Canonical Model Chat: ACTIVE<br><span class="ok">LION BUS · SENTINELX CONTROL</span><br><small>Legacy thread history is archival/read-only. Canonical conversation identity is separate.</small></div></aside><div class="app">
<div class="top"><div><h1>LION CONTROL LPCL PANEL</h1><p class="subtitle">Mission Control · LPCL · Operator · Canonical Model Chat · Protocol · Model Calls</p><div class="complementary-tabs"><a href="#lpclText">LPCL</a><a href="#canonicalModelChatPanel">MODEL CHAT</a><a href="#lionBusPanel">PROTOCOL</a><a href="#operatorPanel">OPERATOR</a><a href="#modelCallPanel">MODEL CALLS</a></div></div><div><div id="controlHealth" class="control-health">MISSION CONTROL …</div><div class="thread-title">Model Chat: <b id="activeThreadTitle">—</b></div><div id="threadContextHeader" class="status">CANONICAL CONVERSATION · NONE</div></div></div>
<div id="cards" class="cards"></div>
<section class="control-panel"><div class="top"><div><div class="k">FOCUS MISSION</div><h2 id="missionTitle">—</h2><div id="missionMeta" class="status"></div></div><button onclick="refreshMissions()">Odśwież misje</button></div><div id="missionObjective" class="mission-objective">Cel misji niezaładowany.</div><div id="missionDescription" class="status"></div><div class="mission-progress-head"><b id="missionProgressLabel">Postęp 0%</b><span id="missionPhaseLabel">Brak aktywnej fazy</span></div><div class="mission-progress"><i id="missionProgressBar"></i></div><div id="missionActions" class="row"></div><div class="control-grid"><div><h3>Fazy procesu autonomicznego</h3><div id="missionPhases" class="phase-grid"></div><div id="phaseControlResult" role="status"></div></div><div><h3>Komunikacja dronów · protokoły</h3><div id="protoFilters" class="protocol-filters"></div><div id="protoFeed" class="protocol-feed"></div></div></div></section>
<section class="control-panel" id="operatorPanel"><div class="top"><div><div class="k">HUMAN OPERATOR CONTROL</div><h2>OPERATOR_PRIMARY</h2><p class="status">Kanał protokołów operator ↔ rój/drony/workery oraz nadrzędne sterowanie misją · niezależny od Model Chat</p></div><button type="button" onclick="refreshOperator()">Odśwież operatora</button></div><div class="row operator-session-row"><button id="operatorPairButton" type="button" class="primary" onclick="operatorPair()">Aktywuj sterowanie operatorem</button><button id="operatorUnpairButton" type="button" onclick="operatorUnpair()">Rozłącz operatora</button><span id="operatorPairState" class="status">UNPAIRED · lokalny handshake</span></div><div id="operatorCards" class="cards"></div><div class="row"><label>Tryb <select id="operatorMode" data-operator-control disabled><option value="MESSAGE">Protokół / rozmowa z rojem</option><option value="AMEND_CONTEXT">Korekta kontekstu</option><option value="AMEND_PLAN">Korekta planu</option></select></label><label>Adresat <select id="operatorTarget" data-operator-control disabled></select></label></div><textarea id="operatorText" data-operator-control disabled class="lpcl-box" style="min-height:90px" placeholder="Wiadomość protokołu do misji, roju, drona lub workera…"></textarea><div class="row"><button type="button" class="primary" data-operator-control disabled onclick="operatorSend()">Wyślij</button><button type="button" data-operator-control disabled onclick="operatorControl('PAUSE_SCOPE')">Wstrzymaj</button><button type="button" class="danger" data-operator-control disabled onclick="operatorControl('STOP_SCOPE')">Zatrzymaj</button><button type="button" data-operator-control disabled onclick="operatorControl('TAKE_CONTROL')">Przejmij sterowanie</button><button type="button" data-operator-control disabled onclick="operatorControl('RELEASE_CONTROL')">Oddaj sterowanie</button><button type="button" data-operator-control disabled onclick="operatorControl('RESUME_SCOPE',{latch:'ALL'})">Wznów</button></div><div id="operatorResult" class="status">Operator control: oczekiwanie na stan.</div><h3>Zdarzenia operatora</h3><div id="operatorFeed" class="protocol-feed"></div></section>
<section class="control-panel"><h2>Mission evidence</h2><div id="missionSchema" class="semantic-grid"></div><h3>Material workers</h3><div id="missionWorkers" class="semantic-grid"></div><h3>Environment / hosts</h3><div id="missionEnvironment" class="semantic-grid"></div><h3>Recent events</h3><div id="missionEvents" class="semantic-events"></div></section>
<section class="control-panel"><div class="top"><div><div class="k">LION CONTROL LANGUAGE</div><h2>LPCL mission intake</h2><p class="status">Wklejenie i walidacja nie wykonują efektów. Rejestracja używa wyłącznie zamrożonego, zwalidowanego źródła. Dopiero jawne Autoryzuj jest activation event dla dokładnego digestu.</p></div><div id="lpclStatus" class="pill">BRAK LPCL</div></div><div id="lpclDiagnostics" class="cards"></div><div class="lpcl-grid"><div><textarea id="lpclText" class="lpcl-box" placeholder="Wklej LPCL/1.2…"></textarea><div class="row"><button id="lpclValidateButton" onclick="validateLpcl()">Waliduj LPCL</button><button id="lpclRegisterButton" class="primary" onclick="registerLpcl()" disabled>Zarejestruj misję</button><button id="lpclPrepareCognitiveButton" onclick="prepareCognitiveContext()" disabled>Przygotuj / synchronizuj cognition</button><button id="lpclActivateButton" onclick="activateLpcl()" disabled>Autoryzuj dokładny LPCL</button></div><div id="lpclCognitiveDiagnostics" class="cards"></div></div><pre id="lpclPreview" class="lpcl-preview">Brak zwalidowanego LPCL.</pre></div></section>

<section class="control-panel" id="canonicalModelChatPanel" data-module="canonical-model-chat">
 <div class="top"><div><div class="k">CANONICAL CONVERSATION PLANE</div><h2>Model Chat</h2><p class="status">Conversation identity is independent from mission, provider session and Protocol. LOCAL / SAAS / DUAL use durable delivery events and cursor.</p></div><div id="cmcHealth" class="status">BOOT</div></div>
 <div class="cmc-toolbar">
  <button type="button" class="primary" id="cmcNew">+ UNBOUND</button>
  <button type="button" id="cmcNewMission">+ dla wybranej misji</button>
  <button type="button" id="cmcFilterMission">Pokaż rozmowy misji</button>
  <button type="button" id="cmcShowAll">Pokaż wszystkie</button>
  <select id="cmcConversationSelect"><option value="">— brak rozmowy —</option></select>
 </div>
 <div class="cmc-grid">
  <div class="cmc-card"><div class="k">STATE</div><div class="v" id="cmcState">—</div></div>
  <div class="cmc-card"><div class="k">BINDING EPOCH</div><div class="v" id="cmcEpoch">—</div></div>
  <div class="cmc-card"><div class="k">MISSION</div><div class="v" id="cmcMission">NULL</div></div>
  <div class="cmc-card"><div class="k">ROUTE</div><div class="v" id="cmcRouteCard">LOCAL</div></div>
  <div class="cmc-card"><div class="k">DELIVERY CURSOR</div><div class="v" id="cmcCursor">0</div></div>
 </div>
 <div class="row">
  <button type="button" id="cmcBind">Bind selected mission → successor</button>
  <button type="button" id="cmcDetach">Detach → successor UNBOUND</button>
  <button type="button" id="cmcLineage">Lineage</button>
 </div>
 <div class="cmc-bridge" data-bridge-mode="AUTO">
  <div class="k">CHATGPT SAAS EXTERNAL BRIDGE · AUTO-PROVISION</div>
  <div id="cmcBridgeState" class="cmc-bridge-state">NO BRIDGE · first SAAS/DUAL will auto-create a dedicated native thread in Phase 3 transport.</div>
  <div class="row"><input id="cmcExternalThreadRef" readonly placeholder="external_thread_ref · auto-filled"><button type="button" id="cmcOpenSaasThread" disabled>Otwórz dokładny wątek SaaS</button><button type="button" id="cmcRotateBridge" disabled>Rotate / Rebind</button></div>
 </div>
 <div id="cmcPending" class="cmc-pending"></div>
 <div id="cmcMessages" class="cmc-messages"></div>
 <div class="cmc-composer"><textarea id="cmcInput" placeholder="Wiadomość Model Chat · Ctrl+Enter = wyślij"></textarea><div class="row"><select id="cmcRoute"><option>LOCAL</option><option>SAAS</option><option>DUAL</option></select><button type="button" class="primary" id="cmcSend">Wyślij</button><span id="cmcSendState" class="status">READY</span></div></div>
</section>
<section class="control-panel" id="lionBusPanel" data-module="protocol-plane"><div class="top"><div><div class="k">PROTOCOL COMMUNICATION PLANE</div><h2>LION BUS · PROTOKÓŁ ROJU</h2><p class="status">Operator, drony logiczne i workery komunikują się przez <code>operator_messages</code>. Ten kanał nie jest Model Chat i nie wybiera providera modelu.</p></div><button type="button" onclick="refreshActiveBus(false)">Odśwież protokół</button></div><div id="busCards" class="cards"></div><div id="busStatus" class="status">Wybierz misję w Mission Control. Protocol nie używa conversation_id.</div><div id="busThreadFeed" class="protocol-feed"></div></section><section class="control-panel" id="modelCallPanel"><div class="top"><div><div class="k">MODEL PLANE DIAGNOSTICS</div><h2>Model Calls</h2><p class="status">Read-only provenance: który worker pyta który model, przez jaki transport i dlaczego. Model output nie jest authority.</p></div></div><div id="modelCallCards" class="cards"></div><div id="modelCallFeed" class="semantic-grid"></div></section><section class="control-panel"><div class="k">LOCAL COGNITIVE EXECUTOR</div><h2>LION Local Model</h2><p class="status">Proposal-only GPT‑OSS · live Mission Control/repo/web evidence through material drones · authority NONE</p></section>
<div hidden aria-hidden="true" id="legacyChatScaffold"><div id="messages"></div><textarea id="q"></textarea><button id="send"></button><select id="modelRoute"><option value="LOCAL">LOCAL</option></select><input id="dbg" type="checkbox"><span id="route"></span><span id="busy"></span><div id="evidence"></div><pre id="debug"></pre></div>
</div></div><script>
/* Reconcile observed markup in place. User-owned disclosure/input state is retained. */
const lionMarkupCache=new WeakMap();
function lionNodeKey(node){
  if(node.nodeType!==1)return null;
  for(const key of ['id','data-key','data-message-id','data-mid','data-run','data-pod','data-mc-action','data-low-action','data-proto','data-p','data-channel','data-open','data-start-component','data-restart'])if(node.hasAttribute(key))return node.tagName+':'+key+':'+node.getAttribute(key);
  return null;
}
function patchHtml(root,markup){
  if(!root)return;markup=String(markup??'');if(lionMarkupCache.get(root)===markup)return;
  const fragment=document.createElement('template');fragment.innerHTML=markup;
  function reconcile(parent,desired){
    const old=Array.from(parent.childNodes),keyed=new Map(old.map(n=>[lionNodeKey(n),n]).filter(([k])=>k));const used=new Set();
    for(let i=0;i<desired.length;i++){
      const next=desired[i],key=lionNodeKey(next);let node=key?keyed.get(key):old[i];
      if(node&&(used.has(node)||node.nodeType!==next.nodeType||node.nodeName!==next.nodeName||(!key&&lionNodeKey(node))))node=null;
      if(!node){node=next.cloneNode(true);parent.insertBefore(node,parent.childNodes[i]||null)}
      else{
        if(node!==parent.childNodes[i])parent.insertBefore(node,parent.childNodes[i]||null);
        if(node.nodeType===3){if(node.data!==next.data)node.data=next.data}
        else if(node.nodeType===1){
          for(const attr of Array.from(node.attributes))if(!(node.tagName==='DETAILS'&&attr.name==='open')&&!next.hasAttribute(attr.name))node.removeAttribute(attr.name);
          for(const attr of Array.from(next.attributes))if(!(node.tagName==='DETAILS'&&attr.name==='open')&&node.getAttribute(attr.name)!==attr.value)node.setAttribute(attr.name,attr.value);
          if(!['INPUT','TEXTAREA','SELECT'].includes(node.tagName)||document.activeElement!==node)reconcile(node,Array.from(next.childNodes));
        }
      }
      used.add(node);
    }
    for(const node of old)if(!used.has(node)&&node.parentNode===parent)node.remove();
  }
  const positions=[root,...root.querySelectorAll('*')].filter(n=>n.scrollTop||n.scrollLeft).map(n=>[n,n.scrollTop,n.scrollLeft]);
  reconcile(root,Array.from(fragment.content.childNodes));
  for(const [node,top,left] of positions)if(node.isConnected){node.scrollTop=top;node.scrollLeft=left}
  lionMarkupCache.set(root,markup);
}
function boundedRows(value){return Array.isArray(value)?value.slice(0,300):[]}
function missingRecord(raw){return String(raw?.normalized_runtime?.record_class||raw?.schema_context?.record_class||'').startsWith('HISTORICAL')?'HISTORICAL_NOT_RECORDED':'NOT_RECORDED'}
function viewValue(value,raw){return value===null||value===undefined||value===''?missingRecord(raw):typeof value==='object'?JSON.stringify(value):String(value)}
function semanticDetail(key,title,fields,raw,escape){
 const values=fields.map(([name,value])=>[name,viewValue(value,raw)]);
 const tip=values.map(([name,value])=>name+': '+value).join('\n');
 const state=String(raw?.status||raw?.state||raw?.event_type||raw?.protocol||title).toUpperCase();
 const tone=/FAIL|ERROR|REJECT|BLOCK/.test(state)?'bad':/PASS|COMPLETE|READY|SUCCESS/.test(state)?'good':/WAIT|PENDING|EXPIRED/.test(state)?'warn':'info';
 const event=values.some(([name])=>['Timestamp','Observed at'].includes(name));
 const badges=values.map(([name,value])=>{const inline=['State','Progress','Evidence count'].includes(name)?' '+value:'';return `<span class="compact-fact" tabindex="0" aria-label="${escape(name+': '+value)}" title="${escape(name+': '+value)}"><span aria-hidden="true">${value==='NOT_RECORDED'?'○':'●'}</span> ${inline?escape(name+inline):escape(({Handler:'⚙','Handler version':'v',Blocker:'!',Detail:'ⓘ',Control:'⌘'})[name]||'ⓘ')}<span class="compact-tooltip" role="tooltip">${escape(name+': '+value)}</span></span>`}).join('');
 const details=`<details class="semantic-raw" data-key="raw"><summary title="Pokaż pełny rekord">${event?'⋯':'RAW'}</summary><pre>${escape(JSON.stringify(raw??{},null,2).slice(0,40000))}</pre></details>`;
 return `<article class="semantic-card ${event?'semantic-event':''} tone-${tone}" data-key="${escape(key)}">${event?`<button type="button" class="event-label" title="${escape(title+'\n'+tip)}" onclick="const d=this.parentElement.querySelector('details');d.open=!d.open">${escape(title)}</button>`:`<h3 tabindex="0" title="${escape(title+'\n'+tip)}">${escape(title)}</h3>`}${event?'':`<div class="compact-facts">${badges}</div>`}${details}</article>`;
}

function phaseCard(phase,mission,escape){
  const fields=[['State',phase.status??phase.state],['Progress',phase.progress===null||phase.progress===undefined?null:phase.progress+'%'],['Handler',phase.handler_id],['Handler version',phase.handler_version],['Blocker',phase.blocker],['Evidence count',phase.evidence_count],['Detail',phase.detail],['Control',Object.entries(phase.capabilities||{}).filter(([a,c])=>['PAUSE','STOP'].includes(a)&&c.supported===true).map(([a])=>a).join(' / ')||phase.control_unavailable_reason||phase.capabilities?.PAUSE?.reason||'INSPECTION_ONLY · no phase mutation capability supplied']];
  const controls=['PAUSE','STOP'].filter(action=>phase.capabilities?.[action]?.supported===true&&typeof phase.capabilities[action].control_token==='string').map(action=>`<button type="button" data-key="${action}" data-phase-action="${action}" data-phase-id="${escape(phase.phase_id)}" data-control-token="${escape(phase.capabilities[action].control_token)}">${action} current phase driver</button>`).join('');
  return semanticDetail(phase.phase_id||phase.id,phase.title||phase.phase_id,fields,{...phase,schema_context:mission.schema_context},escape).replace('</article>',`<div class="phase-actions">${controls}</div></article>`);
}
function workerCards(mission,escape){
  const workers=boundedRows(mission.normalized_runtime?.fleet?.material_workers??mission.workers).map(worker=>{
    const match=row=>(worker.material_drone_id&&row.material_drone_id===worker.material_drone_id)||(worker.pod_uid&&row.pod_uid===worker.pod_uid);
    return {...worker,assignment_history:worker.assignment_history??(Array.isArray(mission.execution_assignments)?mission.execution_assignments.filter(match):null),receipt_history:worker.receipt_history??(Array.isArray(mission.execution_receipts)?mission.execution_receipts.filter(match):null)};
  });
  return workers.map((w,i)=>semanticDetail(w.pod_uid||w.uid||w.worker_id||w.pod_name||i,w.pod_name||w.name||w.worker_id||'Material worker',[
    ['Identity',w.pod_uid??w.uid??w.worker_id],['Logical assignment',w.logical_id??w.assignment],['Runtime',w.runtime??w.process_id??w.pid],['State',w.phase??w.state],['Ready',w.ready],['Restarts',w.restarts],['Host / node',w.node_name??w.node??w.host],['Image',w.image],['Assignment history',w.assignment_history],['Receipt history',w.receipt_history],['History window','Latest 100 mission assignments / receipts; exact material_drone_id or pod_uid match'],['Control',w.capabilities?.RESTART?.reason||'INSPECTION_ONLY · no worker restart capability supplied']
  ],{...w,schema_context:mission.schema_context},escape)).join('')||'<p class="status">No material worker records supplied.</p>';
}

let history=[];let lastQuestion='';let lastAnswer='';let lastPayload=null;let activeThreadId=null;let activeThreadContext=null;let busMessages=[];let busRenderKey='';let busRefreshInFlight=false;let threads=[];let missions=[];let selectedMissionId=null;let missionFocusId=null;let missionPinned=false;let missionView='operational';let missionData=null;let protoFilter='ALL';let lpclValidated=null;let lpclRegistered=null;let lpclCognitiveState=null;let lpclSourceState='EMPTY';let stateRefreshing=false;let missionsRefreshing=false;let missionsRefreshPending=false;let stateRenderKey=null;let missionRenderKey=null;let missionListRenderKey=null;let missionProcessGeneration=0;
const $=id=>document.getElementById(id);const cardsEl=$('cards'),messagesEl=$('messages'),qEl=$('q'),sendEl=$('send'),routeEl=$('route'),busyEl=$('busy'),evidenceEl=$('evidence'),debugEl=$('debug'),dbgEl=$('dbg'),threadListEl=$('threadList'),activeThreadTitleEl=$('activeThreadTitle'),missionListEl=$('missionList');function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}function captureViewport(){let app=document.querySelector('.app'),proto=$('protoFeed'),active=document.activeElement;return {app,appScroll:app?.scrollTop||0,proto,protoScroll:proto?.scrollTop||0,active,selection:(active&&typeof active.selectionStart==='number')?[active.selectionStart,active.selectionEnd]:null}}function restoreViewport(v){if(!v)return;let restore=()=>{if(v.app&&document.contains(v.app))v.app.scrollTop=v.appScroll;if(v.proto&&document.contains(v.proto))v.proto.scrollTop=v.protoScroll;if(v.active&&document.contains(v.active)&&document.activeElement!==v.active){try{v.active.focus({preventScroll:true});if(v.selection&&typeof v.active.setSelectionRange==='function')v.active.setSelectionRange(v.selection[0],v.selection[1])}catch(e){}}};restore();requestAnimationFrame(restore)}
function inlineMd(s){s=esc(s);s=s.replace(/`([^`]+)`/g,'<code>$1</code>');s=s.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');s=s.replace(/\*([^*]+)\*/g,'<em>$1</em>');s=s.replace(/\[([^\]]+)\]\((https:\/\/[^)\s]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');s=s.replace(/(^|\s)(https:\/\/[^\s<]+)/g,'$1<a href="$2" target="_blank" rel="noopener">$2</a>');return s}
function md(src){let lines=String(src||'').replace(/\r/g,'').split('\n'),out=[],i=0,inCode=false,code=[];while(i<lines.length){let l=lines[i];if(l.trim().startsWith('```')){if(!inCode){inCode=true;code=[]}else{out.push('<pre><code>'+esc(code.join('\n'))+'</code></pre>');inCode=false}i++;continue}if(inCode){code.push(l);i++;continue}if(l.includes('|')&&i+1<lines.length&&/^\s*\|?\s*:?-+/.test(lines[i+1])){let rows=[];rows.push(l);i+=2;while(i<lines.length&&lines[i].includes('|')&&lines[i].trim()){rows.push(lines[i++])}let cells=r=>r.replace(/^\s*\||\|\s*$/g,'').split('|').map(x=>x.trim());let head=cells(rows[0]);out.push('<table><thead><tr>'+head.map(x=>'<th>'+inlineMd(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.slice(1).map(r=>'<tr>'+cells(r).map(x=>'<td>'+inlineMd(x)+'</td>').join('')+'</tr>').join('')+'</tbody></table>');continue}if(/^###\s+/.test(l))out.push('<h3>'+inlineMd(l.replace(/^###\s+/,''))+'</h3>');else if(/^##\s+/.test(l))out.push('<h2>'+inlineMd(l.replace(/^##\s+/,''))+'</h2>');else if(/^#\s+/.test(l))out.push('<h1>'+inlineMd(l.replace(/^#\s+/,''))+'</h1>');else if(/^>\s?/.test(l))out.push('<blockquote>'+inlineMd(l.replace(/^>\s?/,''))+'</blockquote>');else if(/^[-*]\s+/.test(l)){let xs=[];while(i<lines.length&&/^[-*]\s+/.test(lines[i]))xs.push('<li>'+inlineMd(lines[i++].replace(/^[-*]\s+/,''))+'</li>');out.push('<ul>'+xs.join('')+'</ul>');continue}else if(/^\d+\.\s+/.test(l)){let xs=[];while(i<lines.length&&/^\d+\.\s+/.test(lines[i]))xs.push('<li>'+inlineMd(lines[i++].replace(/^\d+\.\s+/,''))+'</li>');out.push('<ol>'+xs.join('')+'</ol>');continue}else if(l.trim())out.push('<p>'+inlineMd(l)+'</p>');i++}if(inCode)out.push('<pre><code>'+esc(code.join('\n'))+'</code></pre>');return out.join('')}
function addMsg(role,text,label=null,follow=false){let d=document.createElement('div');d.className='msg '+role;patchHtml(d,'<div class="role">'+esc(label||(role==='user'?'OPERATOR':'LION'))+'</div><div class="md">'+md(text)+'</div>');messagesEl.appendChild(d);if(follow)d.scrollIntoView({behavior:'smooth',block:'start'})}
function boundedHistory(){return history.slice(-12).map(x=>({role:x.role,content:x.content.slice(0,3000)}))}

function patchCards(container,rows){
  if(!container)return;
  const retained=new Set();
  for(const [key,value] of rows){
    retained.add(key);let node=Array.from(container.children).find(n=>n.dataset.key===key);
    if(!node){node=document.createElement('div');node.className='card';node.dataset.key=key;const k=document.createElement('div'),v=document.createElement('div');k.className='k';k.textContent=key;v.className='v';node.append(k,v);container.append(node)}
    const v=node.querySelector('.v'),text=String(value??'NOT RECORDED');if(v.textContent!==text)v.textContent=text;
  }
  for(const node of Array.from(container.children))if(!retained.has(node.dataset.key))node.remove();
}
function renderModelCalls(value){
  const x=value||{},calls=boundedRows(x.calls||[]),cards=$('modelCallCards'),feed=$('modelCallFeed');
  patchCards(cards,[['STATE',x.status||'UNKNOWN'],['CALLS',calls.length],['ACTIVE',calls.filter(c=>!['RESPONSE_RECONCILED','FAILED','CANCELLED'].includes(c.state)).length],['AUTH','NONE']]);
  const html=calls.map((c,i)=>semanticDetail(c.model_call_id||i,c.model_call_id||'Model call',[
    ['State',c.state],['Mission',c.mission_id],['Phase',c.phase_id],['Task',c.task_id],['Assignment',c.assignment_id],['Logical drone',c.logical_drone_id],['Material worker',c.material_worker_id],['Requested capability',c.requested_capability],['Provider',c.provider],['Requested model',c.model_requested],['Declared model',c.model_declared],['Attested model',c.model_attested],['Transport',c.transport],['Selection reason',c.selection_reason],['Context revision',c.context_revision],['Result digest',c.result_digest],['Consumer',c.downstream_consumer],['Authority',c.authority_effect]
  ],c,esc)).join('');
  patchHtml(feed,html||'<p class="status">No model-call records for focused mission.</p>');
}
async function state(){
  if(stateRefreshing)return;stateRefreshing=true;
  try{
    const response=await fetch('/api/state',{cache:'no-store'});if(!response.ok)throw new Error('HTTP '+response.status);
    const x=await response.json(),m=x.material||{},mc=x.mission_control||{},modelCalls=x.model_calls||{status:'UNKNOWN',calls:[]};
    patchCards(cardsEl,[['MODEL',x.model],['GPU',x.gpu],['RAG',x.rag_status],['WEB',x.web_capability],['REPOS',x.repository_capability],['BUS','OPERATOR_MESSAGES@8767'],['MISSION',mc.focus?.state],['MATERIAL HEALTHY',m.healthy],['AUTH',x.authority_effect]]);
    renderModelCalls(modelCalls);
  }catch(e){let h=$('controlHealth');if(h)h.textContent='STATE DEGRADED · '+e.message;await reportUiRuntimeError(e,'state.refresh')}
  finally{stateRefreshing=false}
}

function evidenceHtml(payload){
  const x=payload&&typeof payload==='object'?payload:{};
  const rows=v=>Array.isArray(v)?v.slice(0,100):[];
  const section=(title,text)=>'<div class="source"><b>'+esc(title)+'</b> · '+esc(text)+'</div>';
  let parts=['<h3>Dowody i wykonanie</h3>',section('Route',x.route||'NOT RECORDED')];
  parts.push(section('Tools',rows(x.tool_calls).join(', ')||'NOT RECORDED'));
  let m=x.mission_control?.focus;
  if(m)parts.push(section('Mission Control',String(m.mission_id||'')+' · '+String(m.state||'NOT RECORDED')));
  for(const c of rows(x.currentness))if(c)parts.push(section('Currentness',String(c.subject||'')+' · '+String(c.status||'NOT RECORDED')));
  for(const w of [...rows(x.web_fetches),...rows(x.web_sources)]){
    if(!w)continue;const raw=w.final_url||w.url||'';let url=null;
    try{const parsed=new URL(raw);if(['http:','https:'].includes(parsed.protocol))url=parsed.href}catch(e){}
    parts.push('<div class="source">'+(url?'<a target="_blank" rel="noopener noreferrer" href="'+esc(url)+'">'+esc(w.title||url)+'</a>':esc(w.title||'Source URL unavailable'))+'</div>');
  }
  parts.push(section('Material receipts',rows(x.material_receipts).length));
  return parts.join('');
}
async function reportUiRuntimeError(error,operation){
  const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
  const hex=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join(''),eventId=hex.slice(0,8)+'-'+hex.slice(8,12)+'-'+hex.slice(12,16)+'-'+hex.slice(16,20)+'-'+hex.slice(20);
  let stackDigest='UNAVAILABLE';try{const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(String(error?.stack||error?.message||error)));stackDigest=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('')}catch{}
  const event={event_id:eventId,error_id:eventId,component:'LPCL_PANEL',error_class:String(error?.name||'Error').slice(0,80),stack_digest:stackDigest,timestamp:new Date().toISOString(),request_id:'',frontend_revision:document.querySelector('meta[name=frontend-revision]')?.content||'UNKNOWN',event_class:'UI_RUNTIME_ERROR',operation:String(operation).slice(0,80),error_name:String(error?.name||'Error').slice(0,80),message:String(error?.message||error).slice(0,500),thread_id:String(activeThreadId||'').slice(0,32)};
  window.dispatchEvent(new CustomEvent('UI_RUNTIME_ERROR',{detail:event}));
  routeEl.textContent='UI_RUNTIME_ERROR · '+event.event_id;
  try{const r=await fetch('/api/ui-runtime-events',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(event)});if(!r.ok)throw new Error('event persistence HTTP '+r.status)}
  catch(persistenceError){routeEl.textContent+=' · NOT PERSISTED';console.error('UI_RUNTIME_ERROR_NOT_PERSISTED',event.event_id)}
  return event;
}
window.addEventListener('error',e=>{void reportUiRuntimeError(e.error||new Error(e.message),'window.error')});
window.addEventListener('unhandledrejection',e=>{void reportUiRuntimeError(e.reason,'unhandledrejection')});

/* R24 complementary canonical Model Chat module. */
const CMC_CONSUMER_KEY='lion-r24-complementary-consumer';
const CMC_ACTIVE_KEY='lion-r24-active-conversation';
let cmcConsumerId=localStorage.getItem(CMC_CONSUMER_KEY);
if(!cmcConsumerId){cmcConsumerId='browser-'+crypto.randomUUID().replaceAll('-','');localStorage.setItem(CMC_CONSUMER_KEY,cmcConsumerId)}
let cmcConversations=[],cmcActiveId=null,cmcActive=null,cmcGeneration=0,cmcFilterMission=null,cmcPollBusy=false,cmcCursorBy={},cmcPendingBy={};
async function cmcApi(path,opts={}){const r=await fetch(path,{cache:'no-store',...opts});let x={};try{x=await r.json()}catch(_){ }if(!r.ok)throw new Error(x.error||('HTTP '+r.status));return x}
const cmcPost=(path,body)=>cmcApi(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const cmcOpId=p=>p+'-'+crypto.randomUUID().replaceAll('-','');
function cmcRenderList(){
 const sel=$('cmcConversationSelect');if(!sel)return;
 const current=cmcActiveId||sel.value;
 sel.innerHTML='<option value="">— wybierz rozmowę —</option>'+cmcConversations.map(c=>{const mid=c.current_binding?.mission_id||'UNBOUND';return '<option value="'+esc(c.conversation_id)+'">'+esc((c.title||'Rozmowa')+' · '+c.state+' · e'+(c.current_binding?.binding_epoch??'—')+' · '+mid)+'</option>'}).join('');
 if(current&&cmcConversations.some(c=>c.conversation_id===current))sel.value=current;
}
async function cmcRefreshList(){
 const qs=new URLSearchParams({limit:'500'});if(cmcFilterMission)qs.set('mission_id',cmcFilterMission);
 const x=await cmcApi('/api/conversations?'+qs.toString());cmcConversations=x.conversations||[];cmcRenderList();
 if(cmcActiveId){const c=cmcConversations.find(x=>x.conversation_id===cmcActiveId);if(c)cmcRenderConversation(c)}
 return cmcConversations;
}
function cmcRenderBridge(c){
 const rows=c.external_bridges||[],state=$('cmcBridgeState'),input=$('cmcExternalThreadRef');
 if(!state||!input)return;
 if(!rows.length){state.textContent='NO BRIDGE · AUTO-CREATE on first SAAS/DUAL · no active-tab inference';input.value='';return}
 const b=rows[rows.length-1];state.textContent='BOUND · '+b.external_system+' · bridge_id='+b.bridge_id+' · authority_effect='+b.authority_effect;input.value=b.external_thread_ref||'';
 $('cmcOpenSaasThread').disabled=!b.external_thread_ref;$('cmcRotateBridge').disabled=false;
}
function cmcRenderConversation(c){
 cmcActive=c;cmcActiveId=c.conversation_id;localStorage.setItem(CMC_ACTIVE_KEY,c.conversation_id);cmcRenderList();
 $('activeThreadTitle').textContent=c.title||'Rozmowa';
 $('threadContextHeader').textContent='CANONICAL · '+c.state+' · conversation_id='+c.conversation_id+' · epoch '+(c.current_binding?.binding_epoch??'—')+' · mission '+(c.current_binding?.mission_id??'NULL');
 $('cmcState').textContent=c.state;$('cmcEpoch').textContent=c.current_binding?.binding_epoch??'—';$('cmcMission').textContent=c.current_binding?.mission_id??'NULL';$('cmcCursor').textContent=String(cmcCursorBy[c.conversation_id]??0);
 $('cmcBind').disabled=c.state==='FROZEN';$('cmcDetach').disabled=c.state==='FROZEN'||!c.current_binding?.mission_id;$('cmcSend').disabled=c.state==='FROZEN';cmcRenderBridge(c);
}
function cmcRenderMessages(rows){
 const box=$('cmcMessages');if(!box)return;
 patchHtml(box,(rows||[]).map(m=>'<div class="cmc-msg '+esc(m.role)+'" data-message-id="'+esc(m.message_id)+'"><div class="cmc-role">'+esc(m.role+' · '+m.lane_id+' · '+m.correlation_id)+'</div><div class="md">'+md(m.content||'')+'</div></div>').join('')||'<div class="status">Nowa canonical conversation. Wybierz LOCAL, SAAS albo DUAL.</div>');
 box.scrollTop=box.scrollHeight;
 const last=[...(rows||[])].reverse().find(m=>m.role==='ASSISTANT');if(last)lastAnswer=last.content||'';
}
async function cmcRefreshTranscript(id,generation){
 const x=await cmcApi('/api/conversations/'+encodeURIComponent(id)+'/messages');if(id!==cmcActiveId||generation!==cmcGeneration)return;cmcRenderMessages(x.messages||[]);
}
async function cmcOpen(id){
 if(!id)return;const generation=++cmcGeneration;cmcActiveId=id;const c=await cmcApi('/api/conversations/'+encodeURIComponent(id));if(id!==cmcActiveId||generation!==cmcGeneration)return;cmcRenderConversation(c);await cmcRefreshTranscript(id,generation);await cmcPoll(true);
}
async function cmcCreate(missionId=null){
 const body={title:missionId?'Mission · '+missionId:'Nowa rozmowa',idempotency_key:cmcOpId('complementary')};if(missionId)body.mission_id=missionId;
 const c=await cmcPost('/api/conversations',body);cmcFilterMission=null;await cmcRefreshList();await cmcOpen(c.conversation_id);
}
async function cmcBind(){
 if(!cmcActiveId)throw new Error('Wybierz rozmowę');const mid=selectedMissionId||missionFocusId;if(!mid)throw new Error('Wybierz misję');
 const next=await cmcPost('/api/conversations/'+encodeURIComponent(cmcActiveId)+'/bind',{mission_id:mid,operation_id:cmcOpId('bind')});cmcFilterMission=null;await cmcRefreshList();await cmcOpen(next.conversation_id);await refreshCognitiveReadiness();
}
async function cmcDetach(){
 if(!cmcActiveId)throw new Error('Wybierz rozmowę');const next=await cmcPost('/api/conversations/'+encodeURIComponent(cmcActiveId)+'/detach',{operation_id:cmcOpId('detach')});cmcFilterMission=null;await cmcRefreshList();await cmcOpen(next.conversation_id);
}
async function cmcShowLineage(){
 if(!cmcActiveId)return;const x=await cmcApi('/api/conversations/'+encodeURIComponent(cmcActiveId)+'/lineage');alert(JSON.stringify(x,null,2));
}
function cmcRenderPending(){
 const rows=cmcPendingBy[cmcActiveId]||[];$('cmcPending').textContent=rows.join(' · ');
}
async function cmcSend(){
 if(!cmcActiveId)return;const input=$('cmcInput'),text=input.value.trim();if(!text)return;const route=$('cmcRoute').value,id=cmcActiveId,generation=cmcGeneration;
 $('cmcSend').disabled=true;$('cmcSendState').textContent='SUBMITTING';$('cmcRouteCard').textContent=route;
 try{
   const x=await cmcPost('/api/conversations/'+encodeURIComponent(id)+'/chat',{message:text,route,client_request_id:cmcOpId('ui'),output_language:'auto'});
   if(id!==cmcActiveId||generation!==cmcGeneration)return;input.value='';$('cmcSendState').textContent=x.state||'ACCEPTED';
   if(x.state==='SAAS_QUEUED'||x.state==='DUAL_WAITING'){const rows=cmcPendingBy[id]||(cmcPendingBy[id]=[]);rows.push(route+' '+x.correlation_id+' waiting durable response');cmcRenderPending()}
   await cmcRefreshTranscript(id,generation);await cmcPoll(true);
 }catch(e){$('cmcSendState').textContent='ERROR · '+e.message}
 finally{if(id===cmcActiveId&&cmcActive?.state!=='FROZEN')$('cmcSend').disabled=false}
}
async function cmcPoll(force=false){
 if(!cmcActiveId||cmcPollBusy)return;cmcPollBusy=true;const id=cmcActiveId,generation=cmcGeneration;
 try{
   const known=cmcCursorBy[id],qs=new URLSearchParams({consumer_id:cmcConsumerId,limit:'100'});if(known!==undefined)qs.set('after',String(known));
   const x=await cmcApi('/api/conversations/'+encodeURIComponent(id)+'/events?'+qs.toString());if(id!==cmcActiveId||generation!==cmcGeneration)return;
   const events=x.events||[];if(events.length){await cmcRefreshTranscript(id,generation);const terminal=events.filter(e=>['DELIVERED','FAILED','DENIED','SUPERSEDED'].includes(e.state));if(terminal.length){const done=new Set(terminal.map(e=>e.correlation_id));cmcPendingBy[id]=(cmcPendingBy[id]||[]).filter(row=>![...done].some(corr=>row.includes(corr)));cmcRenderPending();$('cmcSendState').textContent=terminal[terminal.length-1].state}cmcCursorBy[id]=x.next_cursor;await cmcPost('/api/conversations/'+encodeURIComponent(id)+'/cursor',{consumer_id:cmcConsumerId,last_sequence:x.next_cursor});$('cmcCursor').textContent=String(x.next_cursor)}
   else if(known===undefined){cmcCursorBy[id]=x.next_cursor||0;$('cmcCursor').textContent=String(cmcCursorBy[id])}
   if(id===cmcActiveId&&((cmcPendingBy[id]||[]).length||!(cmcActive?.external_bridges||[]).length)){const refreshed=await cmcApi('/api/conversations/'+encodeURIComponent(id));if(id===cmcActiveId&&generation===cmcGeneration)cmcRenderConversation(refreshed)}
   $('cmcHealth').textContent='REACTIVE · '+new Date().toLocaleTimeString();
 }catch(e){if(force)$('cmcHealth').textContent='MODEL CHAT ERROR · '+e.message}
 finally{cmcPollBusy=false}
}
function cmcWire(){
 $('cmcNew').onclick=()=>cmcCreate(null).catch(e=>$('cmcHealth').textContent='CREATE ERROR · '+e.message);
 $('cmcNewMission').onclick=()=>{const m=selectedMissionId||missionFocusId;if(m)cmcCreate(m).catch(e=>$('cmcHealth').textContent='CREATE ERROR · '+e.message)};
 $('cmcFilterMission').onclick=async()=>{cmcFilterMission=selectedMissionId||missionFocusId||null;await cmcRefreshList()};
 $('cmcShowAll').onclick=async()=>{cmcFilterMission=null;await cmcRefreshList()};
 $('cmcConversationSelect').onchange=e=>cmcOpen(e.target.value).catch(err=>$('cmcHealth').textContent='OPEN ERROR · '+err.message);
 $('cmcBind').onclick=()=>cmcBind().catch(e=>$('cmcHealth').textContent='BIND ERROR · '+e.message);
 $('cmcDetach').onclick=()=>cmcDetach().catch(e=>$('cmcHealth').textContent='DETACH ERROR · '+e.message);
 $('cmcLineage').onclick=()=>cmcShowLineage().catch(e=>$('cmcHealth').textContent='LINEAGE ERROR · '+e.message);
 $('cmcOpenSaasThread').onclick=()=>{if(cmcActiveId)location.href='lion-saas://open/'+encodeURIComponent(cmcActiveId)};
 $('cmcRotateBridge').onclick=()=>{if(cmcActiveId)location.href='lion-saas://rotate/'+encodeURIComponent(cmcActiveId)};
 $('cmcSend').onclick=cmcSend;$('cmcRoute').onchange=()=>{$('cmcRouteCard').textContent=$('cmcRoute').value};
 $('cmcInput').addEventListener('keydown',e=>{if(e.key==='Enter'&&e.ctrlKey){e.preventDefault();cmcSend()}});
}

let activeChatController=null,chatGeneration=0,threadViewGeneration=0;
const deletedThreadIds=new Set();
async function bindActiveThread(){
 if(!activeThreadId)await createThread();const mid=selectedMissionId||missionFocusId;if(!mid)throw new Error('Wybierz misję');const target=($('busTarget')?.value||'').trim()||('mission:'+mid);
 const r=await fetch('/api/threads/'+encodeURIComponent(activeThreadId)+'/context',{method:'POST',headers:{'Content-Type':'application/json','X-LION-CSRF':OPERATOR_CSRF},body:JSON.stringify({action:'BIND',mission_id:mid,target})}),x=await r.json();if(!r.ok)throw new Error(x.error||('HTTP '+r.status));activeThreadContext=x;renderThreadContext();await refreshActiveBus(false);await refreshThreads();return x
}
async function unbindActiveThread(){if(!activeThreadId)return;const r=await fetch('/api/threads/'+encodeURIComponent(activeThreadId)+'/context',{method:'POST',headers:{'Content-Type':'application/json','X-LION-CSRF':OPERATOR_CSRF},body:JSON.stringify({action:'UNBIND'})}),x=await r.json();if(!r.ok)throw new Error(x.error||('HTTP '+r.status));activeThreadContext=x;busMessages=[];busRenderKey='';renderThreadContext();renderBusProjection({messages:[],message_deliveries:[],context:x},false);await refreshThreads()}
function renderThreadContext(){const c=activeThreadContext||{};const h=$('threadContextHeader');if(h)h.textContent='LION BUS · THREAD '+String(activeThreadId||'—').slice(0,12)+' · '+(c.binding_state||'MISSION_UNBOUND')+' · MISSION '+(c.mission_id||'—')+' · TARGET '+(c.target||'—')+' · REV '+(c.binding_revision??'—');if($('busTarget'))$('busTarget').value=c.target||''}
function renderModelThread(thread,follow=false){
 const rows=Array.isArray(thread?.messages)?thread.messages:[],nearBottom=messagesEl.scrollHeight-messagesEl.scrollTop-messagesEl.clientHeight<140,priorScroll=messagesEl.scrollTop;
 patchHtml(messagesEl,rows.length?rows.map(m=>'<div class="msg '+(m.role==='user'?'user':'assistant')+'"><div class="role">'+esc((m.role||'model').toUpperCase())+'</div><div class="md">'+md(m.content||'')+'</div></div>').join(''):'<div class="msg assistant"><div class="role">MODEL CHAT</div><div class="md"><p>Nowy wątek modelowy. Wybierz LOCAL, SAAS albo DUAL.</p></div></div>');
 const own=[...rows].reverse().find(m=>m.role==='user'),reply=[...rows].reverse().find(m=>m.role==='assistant');if(own)lastQuestion=own.content||'';if(reply)lastAnswer=reply.content||'';
 if(follow&&nearBottom)messagesEl.scrollTop=messagesEl.scrollHeight;else messagesEl.scrollTop=priorScroll;
}
function renderBusProjection(x,follow){
 const rows=Array.isArray(x?.messages)?x.messages:[],deliveries=Array.isArray(x?.message_deliveries)?x.message_deliveries:[];activeThreadContext=x?.context||activeThreadContext;renderThreadContext();const busFeed=$('busThreadFeed');if(!busFeed)return;
 const key=JSON.stringify(rows.map(m=>[m.message_id,m.state,m.applied_at,m.content_digest]));if(key===busRenderKey){renderBusStatus(x);return}const oldIds=new Set(busMessages.map(m=>m.message_id)),nearBottom=busFeed.scrollHeight-busFeed.scrollTop-busFeed.clientHeight<140,priorScroll=busFeed.scrollTop;busMessages=rows;busRenderKey=key;
 if(!rows.length){patchHtml(busFeed,'<div class="status">Brak wiadomości protokołu w tym wątku.</div>')}else{patchHtml(busFeed,rows.map(m=>{const mine=String(m.from_participant||'').startsWith('operator'),role=mine?'user':'assistant',ds=deliveries.filter(d=>d.message_id===m.message_id).map(d=>d.recipient+':'+d.delivery_state).join(' · '),label=[m.from_participant,m.kind,m.state,ds].filter(Boolean).join(' · ');return '<div class="msg '+role+'" data-message-id="'+esc(m.message_id)+'"><div class="role">'+esc(label)+'</div><div class="md">'+md(m.content)+'</div></div>'}).join(''))}
 if(follow&&nearBottom){const fresh=rows.find(m=>!oldIds.has(m.message_id));if(fresh){const node=busFeed.querySelector('[data-message-id="'+CSS.escape(fresh.message_id)+'"]');node?.scrollIntoView({behavior:'smooth',block:'start'})}}else busFeed.scrollTop=priorScroll;
 renderBusStatus(x)
}
function renderBusStatus(x){const c=x?.context||activeThreadContext||{},control=x?.control||{},deliveries=x?.message_deliveries||[],expected=deliveries.length,responded=deliveries.filter(d=>d.delivery_state==='APPLIED').length,cards=$('busCards');if(cards)patchCards(cards,[['MISSION',c.mission_id],['TARGET',c.target],['BINDING',c.binding_state],['REVISION',c.binding_revision],['OWNER',control.control_owner],['EPOCH',control.control_epoch],['RESPONSES',responded+'/'+expected],['AUTH','OPERATOR GRANT']]);const st=$('busStatus');if(st)st.textContent=c.mission_id?'PROTOCOL · '+c.mission_id+' · '+(c.target||'—')+' · responses '+responded+'/'+expected:'MISSION UNBOUND'}
async function refreshActiveBus(follow=false){if(busRefreshInFlight)return;busRefreshInFlight=true;try{const mid=selectedMissionId||missionFocusId;if(!mid){patchHtml($('busThreadFeed'),'<div class="status">Wybierz misję w Mission Control.</div>');return}const x=missionData?.mission_id===mid?missionData:await (await fetch('/api/missions/'+encodeURIComponent(mid)+'/process',{cache:'no-store'})).json();const rows=boundedRows(x.protocol_messages||x.normalized_runtime?.observability?.events);patchCards($('busCards'),[['MISSION',mid],['IDENTITY','PROTOCOL ≠ MODEL CHAT'],['MESSAGES',rows.length],['AUTH','OPERATOR GRANT']]);$('busStatus').textContent='PROTOCOL · '+mid+' · separate transcript semantics';patchHtml($('busThreadFeed'),rows.slice(-120).map((m,i)=>{const p=m.payload||{};return '<div class="proto-msg" data-key="'+esc(m.id||m.payload_digest||i)+'"><b>'+esc(m.protocol||m.kind||'PROTOCOL')+'</b> · '+esc(m.from_id||m.from_participant||'?')+' → '+esc(m.to_id||m.target||'?')+'<div class="muted">'+esc(m.observed_at||m.created_at||'')+'</div><details class="proto-raw"><summary>RAW</summary><pre>'+esc(JSON.stringify(p||m.content||{},null,2))+'</pre></details></div>'}).join('')||'<div class="status">Brak komunikatów protokołu.</div>')}catch(e){$('busStatus').textContent='PROTOCOL ERROR · '+e.message}finally{busRefreshInFlight=false}}
async function go(question){
 let text=(question??qEl.value).trim();if(!text||sendEl.disabled)return;const route=($('modelRoute')?.value||'LOCAL').toUpperCase();sendEl.disabled=true;busyEl.textContent='MODEL CHAT · '+route+' · RUN';
 try{
   if(!activeThreadId)await createThread();
   const r=await fetch('/api/threads/'+encodeURIComponent(activeThreadId)+'/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,route,output_language:'auto'})}),x=await r.json();
   if(!r.ok)throw new Error(x.error||('HTTP '+r.status));
   qEl.value='';routeEl.textContent='MODEL CHAT · '+route+' · '+(x.result?.route||'RECONCILED');
   const tr=await fetch('/api/threads/'+encodeURIComponent(activeThreadId),{cache:'no-store'}),thread=await tr.json();if(tr.ok)renderModelThread(thread,true);
   await refreshThreads();
 }catch(e){await reportUiRuntimeError(e,'model_chat.submit')}finally{sendEl.disabled=false;busyEl.textContent=''}
}
function copyLast(){if(lastAnswer)navigator.clipboard.writeText(lastAnswer)}function regenerate(){if(lastQuestion)go(lastQuestion)}function resetMessages(){lionMarkupCache.delete(messagesEl);messagesEl.replaceChildren();patchHtml(messagesEl,'<div class="msg assistant"><div class="role">MODEL CHAT</div><div class="md"><p>Wybierz wątek i model: LOCAL, SAAS albo DUAL.</p></div></div>');evidenceEl.replaceC