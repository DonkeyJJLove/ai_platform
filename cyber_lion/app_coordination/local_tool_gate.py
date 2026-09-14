from dataclasses import dataclass
from .local_tool_protocol import ToolCall
SPECS={'lion.rag.search':('RAG_READ',{'query'},{'limit'}),'lion.currentness.read':('CURRENTNESS_READ',{'subject'},set()),'lion.repo.search':('REPOSITORY_READ',{'query'},{'limit'}),'lion.repo.read_file':('REPOSITORY_READ',{'path'},set()),'lion.repo.head_tree':('REPOSITORY_READ',set(),set()),'lion.repo.git_status':('REPOSITORY_READ',set(),set()),'lion.repo.federation_state':('CURRENTNESS_READ',set(),set()),'lion.web.search':('PUBLIC_WEB_READ',{'query'},{'limit'}),'lion.web.fetch':('PUBLIC_WEB_READ',{'url'},set()),'lion.hash.sha256':('DETERMINISTIC_COMPUTE',{'text'},set()),'lion.json.validate':('DETERMINISTIC_COMPUTE',{'text'},set()),'lion.source.state':('REPOSITORY_READ',set(),set()),'lion.source.search':('REPOSITORY_READ',{'query'},{'limit'}),'lion.source.read':('REPOSITORY_READ',{'path'},set()),'lion.source.local_clones':('REPOSITORY_READ',set(),set()),'lion.source.federation':('CURRENTNESS_READ',set(),set()),'lion.source.branch_state':('CURRENTNESS_READ',{'repository','branch'},set())}
@dataclass(frozen=True)
class ToolGateDecision:allowed:bool;reason:str;authority_effect:str='NONE'
def evaluate_tool_call(c:ToolCall):
    try:c.validate()
    except ValueError:return ToolGateDecision(False,'invalid call')
    s=SPECS.get(c.tool_name)
    if not s:return ToolGateDecision(False,'unknown tool denied')
    effect,req,opt=s;keys=set(c.arguments)
    if c.effect_class!=effect:return ToolGateDecision(False,'effect class substitution')
    if not req.issubset(keys) or not keys.issubset(req|opt):return ToolGateDecision(False,'argument schema')
    return ToolGateDecision(True,'declared read-only/deterministic capability')
