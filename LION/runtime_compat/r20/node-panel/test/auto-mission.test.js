'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {MissionControlAdapter,parsePairs,inferFleetCardinality}=require('../src/mission-control');

test('AUTO compiles deterministic 76L32M Docker mission and mission-scoped SaaS advisory',async()=>{
 const a=new MissionControlAdapter({baseUrl:'http://127.0.0.1:1',repo:'.',gitExe:'git'});
 let source=null,saasArgs=null;
 a.validateLpcl=async(s)=>{source=s;const kv=parsePairs(s);return {lpcl_digest:'a'.repeat(64),spec:{mission_id:kv.MISSION_ID}}};
 a.registerLpcl=async()=>({idempotent:false,mission:{mission_id:'x'}});
 a.activateLpcl=async(mid,dg)=>({mission_id:mid,lpcl_digest:dg});
 a.saasRequest=async(args)=>{saasArgs=args;return {request_id:'saas-canary',request_code:'CANARY',transport:'CHATGPT_SENTINELX_MCP'}};
 const out=await a.autoMission({threadId:'thread-one',question:'Inspect current LION runtime'});
 const kv=parsePairs(source);
 assert.equal(out.route,'AUTO_MISSION');
 assert.equal(kv.MODE,'AUTONOMOUS_EXECUTE');
 assert.equal(kv.MATERIAL_RUNTIME,'DOCKER_LOCAL_MODEL');
 assert.equal(kv.LOGICAL_DRONE_COUNT,'76');
 assert.equal(kv.MATERIAL_DRONE_COUNT,'32');
 assert.equal(kv.PHASE_01_EFFECT_CEILING,'NONE');
 assert.equal(saasArgs.missionId,out.mission_id);
 assert.equal(saasArgs.threadId,'thread-one');
});


test('explicit N/M fleet cardinality overrides AUTO default deterministically',async()=>{
 assert.deepEqual(inferFleetCardinality('Stary powołamy małą flotę 16/8 i namalujemy obrazek'),{logical_count:16,material_target:8,source:'EXPLICIT_N_M'});
 const a=new MissionControlAdapter({baseUrl:'http://127.0.0.1:1',repo:'.',gitExe:'git'});
 let source=null;
 a.validateLpcl=async(s)=>{source=s;const kv=parsePairs(s);return {lpcl_digest:'b'.repeat(64),spec:{mission_id:kv.MISSION_ID}}};
 a.registerLpcl=async()=>({idempotent:true,mission:{mission_id:'x'}});
 a.activateLpcl=async(mid,dg)=>({mission_id:mid,lpcl_digest:dg});
 a.saasRequest=async()=>{throw new Error('idempotent mission must not enqueue SaaS')};
 const out=await a.autoMission({threadId:'thread-two',question:'Stary powołamy małą flotę 16/8 i namalujemy obrazek'});
 const kv=parsePairs(source);
 assert.equal(out.logical_count,16);
 assert.equal(out.material_target,8);
 assert.equal(kv.LOGICAL_DRONE_COUNT,'16');
 assert.equal(kv.MATERIAL_DRONE_COUNT,'8');
});

test('unmarked text keeps legacy 76/32 default',()=>{
 assert.deepEqual(inferFleetCardinality('Inspect current LION runtime'),{logical_count:76,material_target:32,source:'DEFAULT'});
});
