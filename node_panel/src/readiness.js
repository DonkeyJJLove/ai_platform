'use strict';
class ReadinessProbe{
  constructor({missionControl,operatorControl,localModel,relay,panelRuntime='NODE_EXPRESS_R18',externalConsumerReady=()=>false}={}){this.mc=missionControl;this.operator=operatorControl;this.local=localModel;this.relay=relay;this.panelRuntime=panelRuntime;this.externalConsumerReady=externalConsumerReady;this.last=null;}
  async probe(){
    const [control,operator,local,transport]=await Promise.all([
      this.mc?.ready?.().catch(()=>false)??false,
      this.operator?.ready?.().catch(()=>false)??false,
      this.local?.ready?.().catch(()=>false)??false,
      this.relay?.readiness?.().catch(()=>({}))??{}
    ]);
    const ingress=transport?.turn_ingress_ready===true,mcp=transport?.mcp_transport_ready===true,durable=transport?.durable_turn_dispatch_ready===true;
    this.last={control_plane_ready:Boolean(control),operator_control_ready:Boolean(operator),panel_runtime_ready:true,panel_runtime:this.panelRuntime,local_model_ready:Boolean(local),turn_ingress_ready:ingress,mcp_transport_ready:mcp,durable_turn_dispatch_ready:durable,chatgpt_external_completion_ready:Boolean(mcp&&this.externalConsumerReady()),chatgpt_autonomous_execution_ready:false,browser_automation:'DISABLED_BY_POLICY',transport_evidence:{broker_ready:transport?.broker_ready===true,tunnel_instance:transport?.tunnel_instance||null},authority_effect:'NONE',observed_at:new Date().toISOString()};
    return this.last;
  }
  snapshot(){return this.last||{control_plane_ready:false,operator_control_ready:false,panel_runtime_ready:true,panel_runtime:this.panelRuntime,local_model_ready:false,turn_ingress_ready:false,mcp_transport_ready:false,durable_turn_dispatch_ready:false,chatgpt_external_completion_ready:false,chatgpt_autonomous_execution_ready:false,browser_automation:'DISABLED_BY_POLICY',authority_effect:'NONE'};}
}
module.exports={ReadinessProbe};
