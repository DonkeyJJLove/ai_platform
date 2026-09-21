'use strict';
const express=require('express');
const {timingSafeEqual}=require('node:crypto');
function createHttp({store,token,status}){
 if(typeof token!=='string'||token.length<32)throw Error('CONTROL_TOKEN_REQUIRED');
 const app=express();app.disable('x-powered-by');
 app.use((req,res,next)=>{
  res.set('Cache-Control','no-store');
  if(req.headers.origin||!['127.0.0.1','localhost','[::1]'].includes((req.headers.host||'').replace(/:\d+$/,'')))return res.status(403).json({error:'ORIGIN_OR_HOST_REJECTED'});
  const given=Buffer.from(String(req.headers.authorization||'')),expected=Buffer.from('Bearer '+token);
  if(given.length!==expected.length||!timingSafeEqual(given,expected))return res.status(401).json({error:'CONTROL_AUTH_REQUIRED'});next();
 });
 app.use(express.json({limit:'16kb',strict:true}));
 app.get('/v1/status',(req,res)=>res.json({schema:'lion.browser-broker.status/v1',...status(),stopped:store.stopped(),wakes:store.rows().map(r=>({request_id:r.request_id,state:r.state,sends:r.sends,reason:r.reason})),model_identity:'UNKNOWN',live_e2e:'NOT_PROVEN'}));
 app.post('/v1/wakes',(req,res)=>{try{const r=store.enqueue(req.body);res.status(202).json({request_id:r.request_id,state:r.state,meaning:'LOCAL_QUEUE_ACCEPTANCE_ONLY'})}catch(e){res.status(409).json({error:/^[A-Z_]+$/.test(e.message)?e.message:'ENQUEUE_REJECTED'})}});
 app.post('/v1/stop',(req,res)=>{store.stop();res.json({stopped:true,external_cancellation:'NOT_GUARANTEED_READBACK_REQUIRED'})});
 app.use((error,req,res,next)=>res.status(400).json({error:'INVALID_BODY'}));
 return app;
}
module.exports={createHttp};
