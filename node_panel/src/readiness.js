'use strict';
const {health}=require('./http-json');
class ReadinessProbe{
  constructor({missionControl,operatorControl,localModel,relay,mcpTransportBase='http://127.0.0.1:8792',panelRuntime='NODE_EXPRESS_R18',externalConsumerReady=()=>false}={}){this.mc=missionControl;this.operator=operatorControl;this.local=localModel;this.relay=relay;this.mcpBase=mcpTransportBase;this.panelRuntime=panelRuntime;this.externalConsumerReady=externalConsumerReady;this.last=null;}
  async probe(){
    const [control,operator,local,ingress,mcp]=await Promise.all([this.mc?.ready?.().catch(()=>false)??false,this.operator?.ready?.().catch(()=>false)??false,this.local?.ready?.().catch(()=>false)??false,this.relay?.ready?.().catch(()=>false)??false,health(this.mcpBase,'/health').catch(()=>false)]);
    this.last={control_plane_ready:Boolean(control),operator_control_ready:Boolean(operator),panel_runtime_ready:true,panel_runtime:this.panelRuntime,local_model_ready:Boolean(local),turn_ingress_ready:Boolean(ingress),mcp_transport_ready:Boolean(mcp),durable_turn_dispatch_ready:Boolean(ingress),chatgpt_external_completion_ready:Boolean(mcp&&this.externalConsumerReady()),chatgpt_autonomous_execution_ready:false,browser_automation:'DISABLED_BY_POLICY',authority_effect:'NONE',observed_at:new Date().toISOString()};
    return this.last;
  }
  snapshot(){return this.last||{control_plane_ready:false,operator_control_ready:false,panel_runtime_ready:true,panel_runtime:this.panelRuntime,local_model_ready:false,turn_ingress_ready:false,mcp_transport_ready:false,durable_turn_dispatch_ready:false,chatgpt_external_completion_ready:false,chatgpt_autonomous_execution_ready:false,browser_automation:'DISABLED_BY_POLICY',authority_effect:'NONE'};}
}
module.exports={ReadinessProbe};
