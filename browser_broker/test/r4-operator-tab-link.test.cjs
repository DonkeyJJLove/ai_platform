'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const src=fs.readFileSync(path.join(__dirname,'..','src','main.cjs'),'utf8');
const start=src.indexOf("     if(v===mission&&(u.protocol==='lion-left:'||u.protocol==='lion-right:'))");
const end=src.indexOf("     if(v===panel&&u.protocol==='lion-saas:')",start);
assert(start>0&&end>start,"Exact mission-local tab navigation source is required");
const branch=src.slice(start,end);
const mission={id:'canonical-mission-view'};
const fn=new Function('v','mission','selectLeftTab','selectRightTab','event','url','const u=new URL(url);'+branch);
function route(url,v=mission){
 const decisions=[];
 const event={prevented:false,preventDefault(){this.prevented=true}};
 fn(v,mission,name=>decisions.push(['left',name]),name=>decisions.push(['right',name]),event,url);
 return {prevented:event.prevented,decisions};
}
test('exact mission navigation changes only native peer tabs',()=>{
 assert.deepEqual(route('lion-left://cluster'),{prevented:true,decisions:[['left','cluster']]});
 assert.deepEqual(route('lion-left://system'),{prevented:true,decisions:[['left','system']]});
 assert.deepEqual(route('lion-right://panel'),{prevented:true,decisions:[['right','panel']]});
});
test('unknown tabs and URI escape patterns never open a native surface',()=>{
 for(const url of [
  'lion-left://mission','lion-left://unknown','lion-left://cluster/path',
  'lion-left://cluster?force=1','lion-left://cluster#fragment',
  'lion-right://saas','lion-right://local','lion-right://panel/path',
  'lion-left://user@cluster','lion-left://cluster:123'
 ]){
  const result=route(url);
  assert.equal(result.prevented,true,url);
  assert.deepEqual(result.decisions,[],url);
 }
});
test('other renderer cannot invoke the operator tab branch',()=>{
 const result=route('lion-left://cluster',{id:'remote-webcontents'});
 assert.equal(result.prevented,false);
 assert.deepEqual(result.decisions,[]);
});
