// Standalone: node cyber_lion/tests/test_supervisor_panel.js
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ids=new Map();
class Node {
  constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.attributes={};this.writes=0;this._text='';}
  set id(value){this._id=value;ids.set(value,this);} get id(){return this._id;}
  set textContent(value){this._text=value;this.writes++;} get textContent(){return this._text;}
  setAttribute(name,value){this.attributes[name]=value;}
  append(...nodes){this.children.push(...nodes);}
  appendChild(node){this.children.push(node);return node;}
  insertAdjacentElement(position,node){assert.equal(position,'afterend');this.adjacent=node;}
  get lastElementChild(){return this.children.at(-1);}
}
const anchor=new Node('div');anchor.id='mcV3Cards';anchor.className='cards';
const control=new Node('button');control.id='existing-control';control.textContent='UNCHANGED';
const document={getElementById:id=>ids.get(id),createElement:tag=>new Node(tag)};
const script=fs.readFileSync(path.resolve(__dirname,'../../deploy/mission-control/v3/control-v3.js'),'utf8');
const context=vm.createContext({document});
vm.runInContext(script.replace(/mcRefresh\(\);setInterval\(mcRefresh,3000\);\s*$/,''),context);
const projection={channel:'READY_FOR_HANDOFF',session:'BOUND',model:'GPT-5.6 Sol',transport:'SESSION_MEDIATED',pending:null,pending_state:'NONE',last_receipt:null,last_receipt_state:'NONE',lease:{state:'ACTIVE',expires_at:'2026-09-14T13:00:00Z'},authority:'NONE',automatic_hop:false,freshness:{state:'FRESH',observed_at:'2026-09-14T12:00:00Z'},unknown_reasons:[]};
context.mcRenderSupervisor(projection);
const host=ids.get('mcSupervisorCards');
const cards=new Map(host.children.map(node=>[node.dataset.supervisorKey,node]));
assert.equal(cards.get('automatic_hop').lastElementChild.textContent,'false');
assert.equal(cards.get('session').lastElementChild.textContent,'BOUND');
assert.equal(cards.get('authority').lastElementChild.textContent,'NONE');
assert.equal(cards.get('model').lastElementChild.textContent,'GPT-5.6 Sol');
const writes=host.children.map(node=>node.lastElementChild.writes);
context.mcRenderSupervisor(projection);
assert.deepEqual(host.children.map(node=>node.lastElementChild.writes),writes);
context.mcRenderSupervisor({...projection,session:'EXPIRED',pending:{request_id:'request-1'},lease:{state:'EXPIRED',expires_at:projection.lease.expires_at}});
for(const node of host.children)assert.equal(node,cards.get(node.dataset.supervisorKey));
assert.equal(cards.get('session').lastElementChild.textContent,'EXPIRED');
assert.equal(cards.get('pending').lastElementChild.textContent,'request-1');
assert.equal(cards.get('automatic_hop').lastElementChild.textContent,'false');
context.mcRenderSupervisor(null);
assert.equal(cards.get('session').lastElementChild.textContent,'UNKNOWN');
assert.equal(cards.get('pending').lastElementChild.textContent,'UNKNOWN');
assert.equal(cards.get('automatic_hop').lastElementChild.textContent,'UNKNOWN');
assert.equal(cards.get('unknown_reasons').lastElementChild.textContent,'PROJECTION_UNAVAILABLE');
assert.equal(control.textContent,'UNCHANGED');
assert.equal(ids.get('mcV3Cards'),anchor);
console.log('PASS: canonical supervisor values, no BOUND inference, keyed identity, unchanged patch, unavailable snapshot, untouched controls');
