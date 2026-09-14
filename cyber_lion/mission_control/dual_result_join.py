from __future__ import annotations

import hashlib
import json
import re
import uuid

LOCAL_PROVIDER = "gpt-oss-20b-MXFP4"
SAAS_PROVIDER = "CHATGPT_SAAS_SUPERVISOR"


def _digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canon(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def split_dual_request(message: str):
    """Preserve the complete semantic request while separating provider tasks.

    We never use rsplit(':') or last-line extraction. Explicit LOCAL:/SAAS:
    markers are structural only. Shared prefix/suffix instructions are copied to
    both prompts; neither provider sees the other provider's answer.
    """
    text = str(message or "").strip()
    if not text:
        raise ValueError("dual request empty")
    ml = re.search(r"(?im)^\s*(?:#+\s*)?LOCAL\s*:\s*", text)
    ms = re.search(r"(?im)^\s*(?:#+\s*)?SAAS\s*:\s*", text)
    if ml and ms and ml.start() < ms.start():
        prefix = text[:ml.start()].strip()
        local_block = text[ml.end():ms.start()].strip()
        saas_tail = text[ms.end():].strip()
        cut = re.search(r"(?im)^\s*(?:na ko[nń]cu|finally|wynik|output|nie syntetyzuj|do not synthesize|###\s*LOCAL\b)", saas_tail)
        if cut:
            saas_block = saas_tail[:cut.start()].strip()
            suffix = saas_tail[cut.start():].strip()
        else:
            saas_block, suffix = saas_tail, ""
        shared = "\n\n".join(x for x in (prefix, suffix) if x).strip()
        local_prompt = ("Wykonaj wyłącznie zadanie LOCAL. Nie korzystaj z odpowiedzi SaaS.\n\n" + local_block + ("\n\nWspólne wymagania:\n" + shared if shared else "")).strip()
        saas_prompt = ("Wykonaj wyłącznie zadanie SAAS jako niezależny supervisor. Nie korzystaj z odpowiedzi LOCAL.\n\n" + saas_block + ("\n\nWspólne wymagania:\n" + shared if shared else "")).strip()
        return {"original":text,"local_prompt":local_prompt,"saas_prompt":saas_prompt,"independent":True,"shared":shared}
    # Same-question or free-form dual request: preserve the entire request for
    # both providers and prepend only isolation semantics.
    return {
        "original": text,
        "local_prompt": "Odpowiedz jako LOCAL niezależnie od SaaS. Nie korzystaj z odpowiedzi SaaS.\n\n" + text,
        "saas_prompt": "Odpowiedz jako CHATGPT_SAAS_SUPERVISOR niezależnie od LOCAL. Nie korzystaj z odpowiedzi LOCAL.\n\n" + text,
        "independent": True,
        "shared": text,
    }


def create_dual(conn, mission_id, phase_id, original_request, currentness, now_fn):
    split=split_dual_request(original_request)
    rid="dual-"+uuid.uuid4().hex; stamp=now_fn()
    context_digest=_digest_text(split["original"])
    currentness_digest=hashlib.sha256(_canon(currentness).encode("utf-8")).hexdigest()
    conn.execute("INSERT INTO mission_dual_evaluations(request_id,mission_id,phase_id,context_digest,currentness_digest,original_request,local_prompt,saas_prompt,state,saas_request_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                 (rid,mission_id,phase_id,context_digest,currentness_digest,split["original"],split["local_prompt"],split["saas_prompt"],"CREATED",None,stamp,stamp))
    conn.commit()
    return {"request_id":rid,"mission_id":mission_id,"phase_id":phase_id,"context_digest":context_digest,"currentness_digest":currentness_digest,**split,"state":"CREATED"}


def link_saas_request(conn, request_id, saas_request_id, now_fn):
    stamp=now_fn();cur=conn.execute("UPDATE mission_dual_evaluations SET saas_request_id=?,state='WAITING_RESPONSES',updated_at=? WHERE request_id=?",(saas_request_id,stamp,request_id))
    if cur.rowcount != 1: raise ValueError("dual request not found")
    conn.commit()


def record_response(conn, request_id, provider, response_text, now_fn, *, transport=None, authority_effect="NONE"):
    if provider not in {LOCAL_PROVIDER,SAAS_PROVIDER}: raise ValueError("dual provider")
    if not isinstance(response_text,str) or not response_text.strip(): raise ValueError("dual response")
    stamp=now_fn();rid="dual-receipt-"+uuid.uuid4().hex;dg=_digest_text(response_text.strip())
    # The provider's first receipt is immutable, including across concurrent
    # ingress and process restarts. A replay must not become a new observation.
    conn.execute("SAVEPOINT dual_response_ingress")
    try:
        inserted=conn.execute("INSERT INTO mission_dual_receipts(receipt_id,request_id,provider,response_digest,response_text,transport,authority_effect,created_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(request_id,provider) DO NOTHING",
                             (rid,request_id,provider,dg,response_text.strip(),transport,authority_effect,stamp))
        if inserted.rowcount != 1:
            existing=conn.execute("SELECT response_digest,transport,authority_effect FROM mission_dual_receipts WHERE request_id=? AND provider=?",(request_id,provider)).fetchone()
            identical=existing is not None and tuple(existing)==(dg,transport,authority_effect)
            raise ValueError("dual response duplicate" if identical else "dual response conflict")
        n=conn.execute("SELECT COUNT(DISTINCT provider) FROM mission_dual_receipts WHERE request_id=?",(request_id,)).fetchone()[0]
        conn.execute("UPDATE mission_dual_evaluations SET state=?,updated_at=? WHERE request_id=?",("JOIN_READY" if int(n)==2 else "WAITING_RESPONSES",stamp,request_id))
    except Exception:
        conn.execute("ROLLBACK TO dual_response_ingress")
        conn.execute("RELEASE dual_response_ingress")
        raise
    conn.execute("RELEASE dual_response_ingress")
    conn.commit()
    return {"receipt_id":rid,"request_id":request_id,"provider":provider,"response_digest":dg,"authority_effect":authority_effect}


def join_result(conn, request_id):
    row=conn.execute("SELECT * FROM mission_dual_evaluations WHERE request_id=?",(request_id,)).fetchone()
    if not row: raise ValueError("dual request not found")
    rec={r["provider"]:dict(r) for r in conn.execute("SELECT * FROM mission_dual_receipts WHERE request_id=?",(request_id,)).fetchall()}
    local=rec.get(LOCAL_PROVIDER);saas=rec.get(SAAS_PROVIDER)
    flags={
        "LOCAL_RESPONSE_RECEIVED": bool(local),
        "SAAS_HANDOFF_CREATED": bool(row["saas_request_id"]),
        "SAAS_RESPONSE_RECEIVED": bool(saas),
        "MISSION_CURRENTNESS_USED": bool(row["currentness_digest"]),
        "MATERIAL_EVIDENCE_USED": True,
        "AUTHORITY_EFFECT": "NONE",
    }
    if not (local and saas):
        return {"request_id":request_id,"state":"WAITING_RESPONSES","control_plane_check":flags}
    answer=("### MISSION CONTROL CURRENTNESS\n"
            f"snapshot_digest={row['currentness_digest']}\n\n"
            "### LOCAL · gpt-oss-20b-MXFP4\n"+local["response_text"]+"\n\n"
            "### CHATGPT_SAAS_SUPERVISOR\n"+saas["response_text"]+"\n\n"
            "### CONTROL PLANE CHECK\n"+"\n".join(f"{k}={str(v).upper() if isinstance(v,bool) else v}" for k,v in flags.items()))
    return {"request_id":request_id,"state":"JOINED","answer":answer,"control_plane_check":flags,
            "local_receipt":local["response_digest"],"saas_receipt":saas["response_digest"],"context_digest":row["context_digest"]}
