from dataclasses import dataclass
import json,re
READ_EFFECTS={'RAG_READ','CURRENTNESS_READ','REPOSITORY_READ','PUBLIC_WEB_READ','DETERMINISTIC_COMPUTE'}
@dataclass(frozen=True)
class ToolCall:
    request_id:str;tool_name:str;arguments:dict;task_class:str;effect_class:str;currentness_requirements:tuple=()
    def validate(self):
        if not isinstance(self.request_id,str) or not self.request_id:raise ValueError('request_id')
        if not re.fullmatch(r'lion\.[a-z0-9_.-]+',self.tool_name):raise ValueError('tool')
        if self.effect_class not in READ_EFFECTS or type(self.arguments) is not dict:raise ValueError('effect/args')
        json.dumps(self.arguments);return self
def parse_tool_call(raw):
    v=json.loads(raw)
    if type(v) is not dict or set(v)!={'tool_call'}:raise ValueError('envelope')
    x=v['tool_call'];req={'request_id','tool_name','arguments','task_class','effect_class','currentness_requirements'}
    if type(x) is not dict or set(x)!=req or type(x['currentness_requirements']) is not list:raise ValueError('fields')
    return ToolCall(x['request_id'],x['tool_name'],x['arguments'],x['task_class'],x['effect_class'],tuple(x['currentness_requirements'])).validate()
