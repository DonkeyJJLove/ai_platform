"""Deliver cognitive broker receipts to threads independently of any browser."""
from __future__ import annotations
import json
import logging

LOGGER=logging.getLogger(__name__)


def deliver_once(threads,control):
    delivered=[]
    for ref in threads('saas_delivery_candidates',{}):
        try:
            result=control('saas_request_status',{'request_id':ref['request_id']})
            if result.get('status')!='RESPONDED' or not result.get('receipt_digest'):continue
            if result.get('thread_id') not in (None,ref['thread_id']):raise ValueError('broker thread mismatch')
            meta=json.loads(result.get('response_meta_json') or '{}')
            text='**SaaS supervisor · '+meta.get('model_identity','UNKNOWN')+'**\n\n'+result['response_text']
            if ref.get('dual_request_id'):
                joined=control('dual_result',{'request_id':ref['dual_request_id']})
                if joined.get('state')!='JOINED':continue
                text=joined['answer']
            receipt={**meta,'receipt_digest':result['receipt_digest'],'saas_request_id':ref['request_id']}
            saved=threads('append_assistant_once',{'thread_id':ref['thread_id'],'assistant':text,'dedupe_key':'saas:'+ref['request_id'],'meta':receipt})
            delivered.append(saved)
        except KeyError:
            # A concurrently deleted conversation must never be recreated.
            continue
        except (ValueError, OSError) as error:
            # One missing or unavailable request must not starve other threads.
            LOGGER.warning('SaaS delivery deferred request=%s error_class=%s',ref['request_id'],type(error).__name__)
            continue
    return delivered


def delivery_loop(threads,control,stop):
    while not stop.is_set():
        try:deliver_once(threads,control)
        except Exception as error:
            # Durable requests remain discoverable; retry after backend recovery.
            LOGGER.warning('SaaS delivery scan deferred error_class=%s',type(error).__name__)
        stop.wait(2)
