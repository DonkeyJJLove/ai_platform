"""LION R10: native LOCAL cognitive receipt without a material MD lease.

One-shot, source- and generation-bound LOCAL model proposals for phase-zero
CROSS_MODEL_RECON. This is not a Docker executor, admission issuer, SaaS
provider, or a replacement scheduler. A model response is untrusted data.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
import sqlite3
from typing import Any, Callable, Mapping
import urllib.request
import urllib.parse

from cyber_lion.mission_control import global_scheduler as scheduler
from cyber_lion.mission_control import operator_control

SCHEMA = "lion.native-cognitive-trajectory/v1"
ROLE_SET = frozenset({
    "PRIMARY_RECONSTRUCTION",
    "ADVERSARIAL_FALSIFICATION",
    "ALTERNATIVE_EXPLANATION",
})
PROVIDER_ID = "MOON_NATIVE_LLAMA_CPP_8772"
FIXED_ENDPOINT = "http://172.25.128.1:8772"
_SHA64 = re.compile(r"^[a-f0-9]{64}$")
_SHA40 = re.compile(r"^[a-f0-9]{40}$")
MAX_PROMPT_BYTES = 16000
MAX_HTTP_BYTES = 1024 * 1024
MAX_RESPONSE_CHARS = 18000


class NativeCognitiveError(ValueError):
    pass


def canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",",":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return sha256(canon(value)).hexdigest()


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise NativeCognitiveError(message)


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS mission_native_cognitive_trajectories (
      call_id TEXT PRIMARY KEY,
      mission_id TEXT NOT NULL,
      phase_id TEXT NOT NULL,
      role TEXT NOT NULL,
      evidence_bundle_digest TEXT NOT NULL,
      source_head TEXT NOT NULL,
      source_tree TEXT NOT NULL,
      lpcl_digest TEXT NOT NULL,
      contract_digest TEXT NOT NULL,
      driver_generation INTEGER NOT NULL,
      context_revision INTEGER NOT NULL,
      prompt_digest TEXT NOT NULL,
      request_digest TEXT NOT NULL,
      http_request_sha256 TEXT NOT NULL,
      provider_id TEXT NOT NULL,
      state TEXT NOT NULL,
      response_digest TEXT,
      http_response_sha256 TEXT,
      receipt_digest TEXT,
      response_text TEXT,
      model_declared TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      UNIQUE (mission_id,phase_id,role,evidence_bundle_digest)
    );
    CREATE INDEX IF NOT EXISTS idx_native_cognitive_mission_state
      ON mission_native_cognitive_trajectories(mission_id,phase_id,state);
    """)


def _source_and_launch(
    conn: sqlite3.Connection,
    mission_id: str, phase_id: str,
    current_source: Mapping[str,str],
    contract_digest: str,
) -> dict[str,Any]:
    _require(type(mission_id) is str and 1 <= len(mission_id) <= 128,
             "MISSION_IDENTITY_INVALID")
    _require(phase_id=="CROSS_MODEL_RECON","PHASE_ZERO_ONLY")
    from cyber_lion.mission_control.application_factory_program import MISSION_ID
    _require(mission_id==MISSION_ID,"APP_FACTORY_MISSION_ID_REQUIRED")
    _require(isinstance(current_source,Mapping),"INDEPENDENT_SOURCE_REQUIRED")
    m=conn.execute("SELECT mission_id,state,source_head,source_tree,spec_digest,adapter,material_target,materialized,ready "
                   "FROM missions WHERE mission_id=?",(mission_id,)).fetchone()
    process=conn.execute("SELECT authority_state FROM mission_process_specs WHERE mission_id=?",(mission_id,)).fetchone()
    driver=conn.execute("SELECT state,generation,lease_owner FROM mission_execution_drivers WHERE mission_id=?",(mission_id,)).fetchone()
    control=operator_control.control_state(conn,mission_id)
    _require(bool(m and process and driver),"CANONICAL_ACTIVATED_MISSION_REQUIRED")
    _require(m["state"] in {"AUTHORIZED","WAITING","RUNNING"}
             and process["authority_state"]=="EXPLICIT_USER_ACTIVATION"
             and m["adapter"] in (None,"LPCL_MISSION")
             and int(m["material_target"])==32
             and int(m["materialized"])==0
             and int(m["ready"])==0,
             "SOURCE_BOUND_PREMATERIAL_MISSION_REQUIRED")
    _require(bool(_SHA40.fullmatch(str(m["source_head"] or "")))
             and bool(_SHA40.fullmatch(str(m["source_tree"] or "")))
             and current_source.get("head")==m["source_head"]
             and current_source.get("tree")==m["source_tree"],
             "INDEPENDENT_SOURCE_CURRENTNESS_REQUIRED")
    _require(bool(_SHA64.fullmatch(str(m["spec_digest"] or ""))),
             "LPCL_IDENTITY_INVALID")
    _require(driver["state"]=="WAITING" and driver["lease_owner"] is None
             and type(driver["generation"]) is int and driver["generation"]>=1,
             "DRIVER_WAIT_GENERATION_REQUIRED")
    _require(bool(control and type(control.get("context_revision")) is int
                  and control["context_revision"]>=0)
             and operator_control.autonomy_allowed(conn,mission_id),
             "OPERATOR_CONTROL_FENCE_DENIED")
    phase=conn.execute(
      "SELECT ordinal,status FROM mission_phases WHERE mission_id=? AND phase_id=?",
      (mission_id,phase_id),
    ).fetchone()
    _require(bool(phase and int(phase["ordinal"])==1
                  and phase["status"] in {"PENDING","RUNNING","WAITING"}),
             "PHASE_ZERO_NOT_CURRENT")
    contract=scheduler.phase_execution_contract(conn,mission_id,phase_id)
    _require(bool(contract and contract["contract_digest"]==contract_digest
                  and contract["phase_id"]==phase_id
                  and contract["ordinal"]==1
                  and contract["execution_class"]=="COGNITIVE"
                  and contract["effect_ceiling"]=="NONE"
                  and contract["capability_classes"]==["CONTROL_PLANE_RECONNAISSANCE"]),
             "EXACT_PHASE_ZERO_CONTRACT_REQUIRED")
    earlier=conn.execute("SELECT COUNT(*) FROM mission_phases WHERE mission_id=? AND ordinal<1 AND status NOT IN ('PASS','COMPLETE')",(mission_id,)).fetchone()[0]
    _require(earlier==0,"PRIOR_PHASE_NOT_RECONCILED")
    return {
        "source_head":m["source_head"],"source_tree":m["source_tree"],
        "lpcl_digest":m["spec_digest"],"driver_generation":int(driver["generation"]),
        "context_revision":int(control["context_revision"]),
    }


def _http_payload(messages: list[dict[str,str]]) -> bytes:
    return canon({"messages":messages,"temperature":0,
                  "max_tokens":640,"stream":False})


def _input(role: str, messages: list[dict[str,str]], evidence_digest: str) -> dict[str,Any]:
    _require(role in ROLE_SET,"UNREGISTERED_TRAJECTORY_ROLE")
    _require(type(messages) is list and 1<=len(messages)<=4
             and all(type(r) is dict and set(r)=={"role","content"}
                     and r["role"] in {"system","user"}
                     and type(r["content"]) is str and r["content"] for r in messages),
             "LOCAL_TRAJECTORY_MESSAGES_INVALID")
    _require(type(evidence_digest) is str and bool(_SHA64.fullmatch(evidence_digest)),
             "EVIDENCE_BUNDLE_DIGEST_INVALID")
    val={
       "schema":SCHEMA,"role":role,"messages":messages,
       "evidence_bundle_digest":evidence_digest,
       "max_tokens":640,"temperature":0,
       "provider":PROVIDER_ID,"authority_effect":"NONE"
    }
    _require(len(canon(val))<=MAX_PROMPT_BYTES,"COGNITIVE_REQUEST_TOO_LARGE")
    return val


def _row(conn:sqlite3.Connection,call_id:str) -> dict[str,Any]|None:
    r=conn.execute("SELECT * FROM mission_native_cognitive_trajectories WHERE call_id=?",(call_id,)).fetchone()
    return dict(r) if r else None


def prepare_intent(conn:sqlite3.Connection, *, mission_id:str, phase_id:str,
                   role:str, evidence_bundle_digest:str, messages:list[dict[str,str]],
                   contract_digest:str, current_source:Mapping[str,str], now_fn:Callable[[],str]) -> dict[str,Any]:
    """Durable, idempotent intent only. No network activity."""
    source=_source_and_launch(conn,mission_id,phase_id,current_source,contract_digest)
    _require(_SHA64.fullmatch(contract_digest) is not None,"CONTRACT_DIGEST_INVALID")
    blob=scheduler.artifact(conn,mission_id,"RECON_EVIDENCE_BUNDLE",phase_id=phase_id)
    _require(bool(blob and blob["content_digest"]==evidence_bundle_digest),
             "EVIDENCE_BUNDLE_NOT_PERSISTED")
    data=_input(role,messages,evidence_bundle_digest)
    call_id="native-recon-"+sha256(
        f"{mission_id}|{phase_id}|{role}|{evidence_bundle_digest}".encode("utf8")
    ).hexdigest()[:32]
    binding={
      **source,"contract_digest":contract_digest,"mission_id":mission_id,
      "phase_id":phase_id,"evidence_bundle_digest":evidence_bundle_digest,
      "role":role,"prompt_digest":digest(messages),
      "request_digest":digest(data),
      "http_request_sha256":sha256(_http_payload(messages)).hexdigest(),
      "provider_id":PROVIDER_ID
    }
    old=_row(conn,call_id)
    if old:
        _require(all(old.get(k)==v for k,v in binding.items()),
                 "NATIVE_COGNITIVE_INTENT_DRIFT")
        return old
    stamp=now_fn()
    conn.execute("""
      INSERT INTO mission_native_cognitive_trajectories (
       call_id,mission_id,phase_id,role,evidence_bundle_digest,
       source_head,source_tree,lpcl_digest,contract_digest,driver_generation,
       context_revision,prompt_digest,request_digest,http_request_sha256,provider_id,state,
       created_at,updated_at
      ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'INTENT_DURABLE',?,?)
    """,(call_id,mission_id,phase_id,role,evidence_bundle_digest,
          source["source_head"],source["source_tree"],source["lpcl_digest"],
          contract_digest,source["driver_generation"],source["context_revision"],
          binding["prompt_digest"],binding["request_digest"],
          binding["http_request_sha256"],PROVIDER_ID,stamp,stamp))
    conn.commit()
    return _row(conn,call_id)


def send_once(conn:sqlite3.Connection, *, intent:Mapping[str,Any],
              messages:list[dict[str,str]], evidence_bundle_digest:str,
              contract_digest:str, current_source:Mapping[str,str],
              transport:Callable[[list[dict[str,str]]],tuple[str,bytes,str|None,str]],
              now_fn:Callable[[],str]) -> dict[str,Any]:
    """Mark SEND_UNKNOWN before external call; never replay an uncertain send.

    The native transport returns actual response text and the exact raw
    HTTP response bytes. It must be a trusted, fixed-endpoint host provider.
    """
    _require(callable(transport),"TRUSTED_NATIVE_LOCAL_PROVIDER_REQUIRED")
    mission_id,phase_id=intent["mission_id"],intent["phase_id"]
    checked=_source_and_launch(conn,mission_id,phase_id,current_source,contract_digest)
    before=_row(conn,intent["call_id"])
    _require(bool(before),"INTENT_NOT_PERSISTED")
    _require(before["state"]=="INTENT_DURABLE","UNCERTAIN_OR_COMPLETE_SEND_REPLAY_DENIED")
    _require(before["evidence_bundle_digest"]==evidence_bundle_digest
             and before["contract_digest"]==contract_digest
             and before["prompt_digest"]==digest(messages)
             and before["request_digest"]==digest(_input(before["role"],messages,evidence_bundle_digest))
             and before["source_head"]==checked["source_head"]
             and before["source_tree"]==checked["source_tree"]
             and before["driver_generation"]==checked["driver_generation"]
             and before["context_revision"]==checked["context_revision"],
             "NATIVE_COGNITIVE_BINDING_DRIFT")
    stamp=now_fn()
    updated=conn.execute("""
      UPDATE mission_native_cognitive_trajectories
      SET state='SEND_UNKNOWN',updated_at=?
      WHERE call_id=? AND state='INTENT_DURABLE'
    """,(stamp,before["call_id"]))
    _require(updated.rowcount==1,"NATIVE_SEND_ALREADY_CONSUMED")
    conn.commit()   # durable before any outgoing byte: uncertain failure cannot retry
    try:
        response_text,raw_response,model_declared,sent_sha=transport(messages)
        _require(sent_sha==before["http_request_sha256"],
                 "NATIVE_HTTP_REQUEST_BYTES_DRIFT")
        _require(type(response_text) is str and 1<=len(response_text)<=MAX_RESPONSE_CHARS,
                 "NATIVE_MODEL_OUTPUT_INVALID")
        _require(type(raw_response) is bytes and 1<=len(raw_response)<=MAX_HTTP_BYTES,
                 "NATIVE_RESPONSE_BYTES_INVALID")
        _require(model_declared is None or (type(model_declared) is str and len(model_declared)<=256),
                 "NATIVE_MODEL_IDENTITY_INVALID")
        after=_source_and_launch(conn,mission_id,phase_id,current_source,contract_digest)
        _require(after==checked,"NATIVE_SOURCE_OR_GENERATION_CHANGED_POST_SEND")
    except Exception:
        # Deliberate SEND_UNKNOWN: no silent synthetic FAILED or retry.
        raise
    receipt={
      "schema":"lion.native-cognitive-response-receipt/v1",
      "call_id":before["call_id"],"mission_id":mission_id,"phase_id":phase_id,
      "role":before["role"],"evidence_bundle_digest":evidence_bundle_digest,
      "source_head":checked["source_head"],"source_tree":checked["source_tree"],
      "contract_digest":contract_digest,"driver_generation":checked["driver_generation"],
      "context_revision":checked["context_revision"],
      "request_digest":before["request_digest"],
      "http_request_sha256":before["http_request_sha256"],
      "response_digest":sha256(response_text.encode("utf8")).hexdigest(),
      "http_response_sha256":sha256(raw_response).hexdigest(),
      "model_declared":model_declared,
      "model_attested":None,
      "provider":PROVIDER_ID,"authority_effect":"NONE","effect_class":"COGNITIVE_PROPOSAL",
    }
    rdig=digest(receipt)
    s=now_fn()
    result=conn.execute("""
     UPDATE mission_native_cognitive_trajectories
     SET state='RESPONSE_RECONCILED',response_digest=?,http_response_sha256=?,
         receipt_digest=?,response_text=?,model_declared=?,updated_at=?
     WHERE call_id=? AND state='SEND_UNKNOWN'
    """,(receipt["response_digest"],receipt["http_response_sha256"],rdig,
         response_text,model_declared,s,before["call_id"]))
    _require(result.rowcount==1,"NATIVE_SEND_STATE_CHANGED")
    conn.commit()
    return {**receipt,"receipt_digest":rdig,"state":"RESPONSE_RECONCILED"}


def read_response(conn:sqlite3.Connection, *, call_id:str, mission_id:str,
                  phase_id:str, role:str, evidence_bundle_digest:str,
                  current_source:Mapping[str,str], contract_digest:str) -> dict[str,Any]|None:
    checked=_source_and_launch(conn,mission_id,phase_id,current_source,contract_digest)
    v=_row(conn,call_id)
    if not v or v["state"]!="RESPONSE_RECONCILED":return None
    _require(v["mission_id"]==mission_id and v["phase_id"]==phase_id
             and v["role"]==role and v["evidence_bundle_digest"]==evidence_bundle_digest
             and v["contract_digest"]==contract_digest
             and v["driver_generation"]==checked["driver_generation"]
             and v["context_revision"]==checked["context_revision"]
             and v["source_head"]==checked["source_head"]
             and v["source_tree"]==checked["source_tree"],
             "NATIVE_RECEIPT_BINDING_DRIFT")
    raw=v["response_text"]
    _require(type(raw) is str and sha256(raw.encode("utf8")).hexdigest()==v["response_digest"]
             and _SHA64.fullmatch(v["http_response_sha256"] or "") is not None,
             "NATIVE_RESPONSE_CONTENT_DRIFT")
    receipt={
      "schema":"lion.native-cognitive-response-receipt/v1",
      "call_id":call_id,"mission_id":mission_id,"phase_id":phase_id,
      "role":role,"evidence_bundle_digest":evidence_bundle_digest,
      "source_head":checked["source_head"],"source_tree":checked["source_tree"],
      "contract_digest":contract_digest,"driver_generation":checked["driver_generation"],
      "context_revision":checked["context_revision"],
      "request_digest":v["request_digest"],
      "http_request_sha256":v["http_request_sha256"],
      "response_digest":v["response_digest"],
      "http_response_sha256":v["http_response_sha256"],
      "model_declared":v["model_declared"],"model_attested":None,
      "provider":PROVIDER_ID,"authority_effect":"NONE","effect_class":"COGNITIVE_PROPOSAL"
    }
    _require(v["receipt_digest"]==digest(receipt),"NATIVE_RECEIPT_DIGEST_DRIFT")
    return {**receipt,"receipt_digest":v["receipt_digest"],
            "response_text":raw,"state":v["state"]}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise NativeCognitiveError("LOCAL_REDIRECT_DENIED")


def native_llamacpp_transport(messages:list[dict[str,str]]) -> tuple[str,bytes,str|None]:
    """Original native Windows-hosted llama.cpp on an immutable address only."""
    endpoint=FIXED_ENDPOINT
    uri=urllib.parse.urlparse(endpoint)
    _require(uri.scheme=="http" and uri.hostname=="172.25.128.1"
             and uri.port==8772 and not uri.username and not uri.password
             and uri.path in ("","/") and not uri.query and not uri.fragment,
             "NATIVE_ENDPOINT_SUBSTITUTION_DENIED")
    payload=_http_payload(messages)
    _require(len(payload)<=MAX_PROMPT_BYTES,"NATIVE_MODEL_REQUEST_SIZE_INVALID")
    request=urllib.request.Request(
      endpoint+"/v1/chat/completions",data=payload,method="POST",
      headers={"Content-Type":"application/json","Accept":"application/json",
               "User-Agent":"LION-R10-NATIVE-COGNITIVE/1"},
    )
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),_NoRedirect())
    with opener.open(request,timeout=30) as res:
        _require(res.status==200,"NATIVE_MODEL_HTTP_NOT_200")
        raw=res.read(MAX_HTTP_BYTES+1)
    _require(len(raw)<=MAX_HTTP_BYTES,"NATIVE_MODEL_RESPONSE_OVERSIZE")
    value=json.loads(raw.decode("utf8"))
    _require(type(value) is dict and type(value.get("choices")) is list
             and len(value["choices"])==1,"NATIVE_MODEL_RESPONSE_SCHEMA")
    choice=value["choices"][0]
    _require(type(choice) is dict and choice.get("finish_reason") in (None,"stop")
             and type(choice.get("message")) is dict
             and type(choice["message"].get("content")) is str,
             "NATIVE_MODEL_INCOMPLETE")
    text=choice["message"]["content"]
    model=value.get("model")
    return text,raw,model if type(model) is str and len(model)<=256 else None,sha256(payload).hexdigest()
