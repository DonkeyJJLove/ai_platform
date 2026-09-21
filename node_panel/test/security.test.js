'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const ROOT=path.resolve(__dirname,'../..');
function tree(dir){const out=[];for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory())out.push(...tree(p));else out.push(p);}return out;}
const src=()=>tree(path.join(ROOT,'node_panel','src')).map(p=>fs.readFileSync(p,'utf8')).join('\n');
test('T30 production Node runtime has no browser automation dependency',()=>{assert.doesNotMatch(src(),/background_driver|edge_session_worker|Playwright|playwright|msedge|mediator\.js/);});
test('T31 production Node runtime has no Codex runtime dependency',()=>{assert.doesNotMatch(src(),/codex\.exe|Codex App Server|CODEX_PROJECT_HARNESS|codex cli/i);});
test('T32 production Node runtime has no OpenAI model API-key dependency',()=>{assert.doesNotMatch(src(),/OPENAI_API_KEY|api\.openai\.com|sk-proj-/);});
test('T33 current 8780 supervisor owns Node server, not legacy Python panel',()=>{const s=fs.readFileSync(path.join(ROOT,'tools','lion_control_plane_supervisor_windows.ps1'),'utf8');assert.match(s,/node_panel\\src\\server\.js/);assert.doesNotMatch(s,/lion_local_intelligence_runtime\.py/);assert.match(s,/runtime=NODE_EXPRESS_R18/);});
test('T36 documentation names executable symbols and tests',()=>{for(const p of ['R18_NODE_EXPRESS_SAAS_FABRIC.md','R18_PROVIDER_CONTRACT.md','R18_RELEVANCE_ENGINE.md','R18_DURABLE_TURN_STATE_MACHINE.md','R18_CHATGPT_SAAS_CONSUMER_PROTOCOL.md']){const t=fs.readFileSync(path.join(ROOT,'LION','architecture',p),'utf8');assert.match(t,/SOURCE_REF:/);assert.match(t,/TEST_REF:/);}});
