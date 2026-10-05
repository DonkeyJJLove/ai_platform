"""One trusted registered recipe. Model output is JSON data, never host code."""
from __future__ import annotations
import base64
from pathlib import Path
import os
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.parse
from .edge_support import EdgeRejected, canonical, digest, identifier, object_bytes, read_regular
from .edge_work_unit import validate_work_unit
from .artifact_transfer import create_bundle, verify_bundle
from .edge_product import verify_tree
SCENARIOS = ('valid','changed_content','missing_file','wrong_size','traversal','extra_file','case_collision','hash_mismatch')
PROMPT = '''Return JSON only: {"schema":"lion.product-tests/v1","cases":[...]}. Exactly eight cases, one per scenario: valid, changed_content, missing_file, wrong_size, traversal, extra_file, case_collision, hash_mismatch. Each scenario MUST occur exactly once. Each case has exactly id (short ASCII identifier), scenario and expected_valid (boolean). IDs SHOULD be unique; the trusted host may deterministically normalize only colliding IDs. Only valid has expected_valid=true. Purpose: regression corpus for a byte-integrity manifest verifier. No code, commands, markdown or additional keys.'''

def validate_corpus(v):
    if type(v) is not dict or set(v) != {'schema','cases'} or v['schema'] != 'lion.product-tests/v1' or type(v['cases']) is not list or len(v['cases']) != 8:
        raise EdgeRejected('corpus schema')
    ids, seen = set(), set()
    for row in v['cases']:
        if type(row) is not dict or set(row) != {'id','scenario','expected_valid'}:
            raise EdgeRejected('case fields')
        identifier(row['id'])
        if row['id'] in ids or row['scenario'] not in SCENARIOS or row['scenario'] in seen:
            raise EdgeRejected('case identity')
        if type(row['expected_valid']) is not bool or row['expected_valid'] != (row['scenario'] == 'valid'):
            raise EdgeRejected('case expectation')
        ids.add(row['id']); seen.add(row['scenario'])
    return v

def normalize_model_corpus(v):
    """Normalize only duplicate model-selected IDs; scenario identity remains fail-closed."""
    if type(v) is not dict or set(v) != {'schema','cases'} or v['schema'] != 'lion.product-tests/v1' or type(v['cases']) is not list or len(v['cases']) != 8:
        raise EdgeRejected('corpus schema')
    seen_scenarios = set()
    id_counts = {}
    checked = []
    for row in v['cases']:
        if type(row) is not dict or set(row) != {'id','scenario','expected_valid'}:
            raise EdgeRejected('case fields')
        identifier(row['id'])
        scenario = row['scenario']
        if scenario not in SCENARIOS or scenario in seen_scenarios:
            raise EdgeRejected('scenario identity')
        if type(row['expected_valid']) is not bool or row['expected_valid'] != (scenario == 'valid'):
            raise EdgeRejected('case expectation')
        seen_scenarios.add(scenario)
        id_counts[row['id']] = id_counts.get(row['id'], 0) + 1
        checked.append(row)
    if seen_scenarios != set(SCENARIOS):
        raise EdgeRejected('scenario identity')
    used = set()
    normalized = []
    for row in checked:
        case_id = row['id']
        if id_counts[case_id] > 1:
            case_id = 'model-' + digest(row['scenario'].encode('ascii'))[:16]
        if case_id in used:
            raise EdgeRejected('normalized case identity')
        used.add(case_id)
        normalized.append(dict(id=case_id, scenario=row['scenario'], expected_valid=row['expected_valid']))
    return dict(schema='lion.product-tests/v1', cases=normalized)

def fixture_corpus():
    return dict(schema='lion.product-tests/v1',cases=[dict(id='case-'+n,scenario=n,expected_valid=n=='valid') for n in SCENARIOS])

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise EdgeRejected('model redirect denied')

def infer(endpoint):
    u = urllib.parse.urlparse(endpoint)
    if (u.scheme != 'http' or u.hostname not in {'127.0.0.1','localhost','host.docker.internal'}
            or u.port != 8772 or u.path not in {'','/'} or u.username or u.password or u.query or u.fragment):
        raise EdgeRejected('only explicitly selected local model port 8772 is allowed')
    payload = canonical(dict(messages=[dict(role='user',content=PROMPT)],max_tokens=1500,temperature=0.1,stream=False))
    request = urllib.request.Request(endpoint.rstrip('/')+'/v1/chat/completions',data=payload,
                                     headers={'Content-Type':'application/json'},method='POST')
    start = time.time()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(request,timeout=60) as response:
        if response.status != 200:
            raise EdgeRejected('model HTTP status')
        raw = response.read(65537)
    value = object_bytes(raw,65536)
    choice = value['choices'][0]
    text = choice['message']['content']
    if type(text) is not str or choice.get('finish_reason') not in {None,'stop'}:
        raise EdgeRejected('incomplete model response')
    corpus = normalize_model_corpus(object_bytes(text.encode('utf-8'),16384))
    validate_corpus(corpus)
    return corpus, dict(source='LOCAL_MODEL',call_count=1,request_sha256=digest(payload),response_sha256=digest(raw),
                        content_sha256=digest(text.encode()),model_declared=value.get('model'),model_attested=None,
                        started_at=start,finished_at=time.time(),authority_effect='NONE')

def run_case(name):
    with tempfile.TemporaryDirectory(prefix='lion-case-') as td:
        root = Path(td);data = b'example artifact\n';(root/'data.txt').write_bytes(data)
        manifest = dict(schema='lion.simple-product/v1',files=[dict(path='data.txt',size=len(data),sha256=digest(data))])
        if name == 'changed_content': (root/'data.txt').write_bytes(b'changed\n')
        elif name == 'missing_file': (root/'data.txt').unlink()
        elif name == 'wrong_size': manifest['files'][0]['size'] += 1
        elif name == 'traversal': manifest['files'][0]['path'] = '../data.txt'
        elif name == 'extra_file': (root/'extra.txt').write_bytes(b'extra')
        elif name == 'case_collision': manifest['files'].append(dict(manifest['files'][0],path='DATA.txt'))
        elif name == 'hash_mismatch': manifest['files'][0]['sha256'] = '0'*64
        elif name != 'valid': raise EdgeRejected('unknown case')
        try:
            verify_tree(root,manifest)
            return True
        except ValueError:
            return False

def execute(job,input_bytes,*,host_id,worker_id,endpoint=None):
    validate_work_unit(job,host_id,worker_id)
    _, files = verify_bundle(input_bytes,job['input_sha256'],job['input_binding'])
    if job['operation'] == 'BUILD_INTEGRITY_TOOL':
        if object_bytes(files['spec.json'],16384) != dict(recipe='integrity-cli-v1',test_count=8):
            raise EdgeRejected('unregistered recipe')
        if job['use_local_model']:
            if endpoint is None:
                raise EdgeRejected('operator model endpoint required')
            corpus, receipt = infer(endpoint)
        else:
            corpus, receipt = fixture_corpus(),dict(source='DETERMINISTIC_TEST_DATA',call_count=0,model_attested=None)
        validate_corpus(corpus)
        result = {'product_verifier.py':read_regular(Path(__file__).with_name('edge_product.py')),
                  'cases.json':canonical(corpus),'model-receipt.json':canonical(receipt),
                  'README.md':b'# Artifact verifier\n\npython product_verifier.py ROOT MANIFEST.json\nSchema: lion.simple-product/v1; files: path,size,sha256.\nHashes check bytes, not authority. Use a private quiescent workspace.\n'}
    else:
        if job['input_binding']['producer_ref'] == worker_id:
            raise EdgeRejected('different verifier required')
        expected = read_regular(Path(__file__).with_name('edge_product.py'))
        if files.get('product_verifier.py') != expected:
            raise EdgeRejected('executable substitution; arbitrary model code is not executed')
        corpus = validate_corpus(object_bytes(files['cases.json'],16384))
        cases = []
        for row in corpus['cases']:
            actual = run_case(row['scenario'])
            if actual is not row['expected_valid']:
                raise EdgeRejected('functional regression:'+row['id'])
            cases.append(dict(row, actual_valid=actual, passed=True))
        report = dict(schema='lion.edge.product-verification/v2',status='PASS',cases=cases,
                      input_sha256=job['input_sha256'],product_sha256=digest(expected),
                      producer=job['input_binding']['producer_ref'],verifier=worker_id,
                      distinct_worker=True,authority_effect='NONE')
        result = {'verification.json':canonical(report)}
    raw = create_bundle(result,job['output_binding'],parent_transfer_sha256=job['input_sha256'])
    verify_bundle(raw,digest(raw),job['output_binding'])
    return raw

def main():
    # Only this trusted bootstrap runs before stdin; no arbitrary code or shell.
    timer = threading.Timer(100,lambda:os._exit(124));timer.daemon=True;timer.start()
    try:
        value = object_bytes(sys.stdin.buffer.read(1400001),1400000)
        if set(value) != {'job','input_b64','host_id','worker_id','endpoint'}:
            raise EdgeRejected('worker request fields')
        raw = base64.b64decode(value['input_b64'],validate=True)
        result = execute(value['job'],raw,host_id=value['host_id'],worker_id=value['worker_id'],endpoint=value['endpoint'])
        sys.stdout.buffer.write(canonical(dict(output_b64=base64.b64encode(result).decode(),output_sha256=digest(result))))
        return 0
    except Exception as exc:
        sys.stderr.write(type(exc).__name__+':'+str(exc)[:500]+'\n')
        return 2
    finally:
        timer.cancel()
if __name__ == '__main__':
    raise SystemExit(main())
