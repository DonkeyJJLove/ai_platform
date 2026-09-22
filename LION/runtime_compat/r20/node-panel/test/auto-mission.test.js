'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {MissionControlAdapter,parsePairs}=require('../src/mission-control');

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
