"""Integração do produto local: documentos, API, biblioteca e transporte MCP real."""
import asyncio
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.projects import ProjectStore
from app.retrieval.bm25 import rank
from app.runtime_tools import call_local_mcp, project_tools
from app.web import create_app
from app.web import build_clarification
from app.wiki import ProjectWiki


def test_bm25_accents_and_empty():
    assert rank('regressao', ['Regressão linear', 'flores'])[0][0] == 0
    assert rank('unknown', ['texto']) == []
    assert rank('', []) == []
    with pytest.raises(ValueError):
        rank('a', ['a'], limit=0)


def test_documents_are_isolated_and_deduplicated(tmp_path):
    store = ProjectStore(tmp_path)
    first = store.create('A', 'Regression?')['id']
    second = store.create('B', 'Other?')['id']
    document = store.add_document(first, '../notes.txt', b'Regression evidence')
    assert store.add_document(first, 'copy.txt', b'Regression evidence')['duplicate']
    assert len(store.documents(first)) == 1
    hit = store.search(first, 'regression')[0]
    assert hit['source'] == 'notes.txt'
    assert hit['citation'] == document['id'] + ':1'
    assert store.search(second, 'regression') == []
    with pytest.raises(FileNotFoundError):
        store.source(second, document['id'])
    with pytest.raises(ValueError):
        store.directory('../escape')


@pytest.mark.parametrize('name,content', [('a.exe', b'data'), ('a.txt', b''), ('a.json', b'{bad')])
def test_bad_documents(tmp_path, name, content):
    store = ProjectStore(tmp_path)
    identifier = store.create('A', 'Question')['id']
    with pytest.raises(ValueError):
        store.add_document(identifier, name, content)


def test_job_lock_and_recovery(tmp_path):
    store = ProjectStore(tmp_path)
    identifier = store.create('A', 'Question')['id']
    job = store.start_job(identifier, 'build')
    with pytest.raises(ValueError):
        store.start_job(identifier, 'chat')
    store.recover_jobs()
    assert store.job(job)['status'] == 'interrupted'
    assert store.start_job(identifier, 'chat') != job


def test_scientific_build_block_becomes_factory_clarification():
    assert build_clarification({
        'status': 'blocked',
        'errors': ['Falta esclarecer a pergunta: Which private dataset is available?'],
    }) == 'INPUT_REQUIRED: Which private dataset is available?'
    assert build_clarification({'status': 'blocked', 'errors': ['Budget exhausted']}) is None


def test_running_operation_conflict_explains_what_is_blocking_the_project(tmp_path):
    application = create_app(tmp_path)
    store = application.state.store
    project = store.create('Lock test', 'Research question')['id']
    with TestClient(application) as client:
        job = store.start_job(project, 'chat')
        store.update_job(job, 'running', progress='Waiting for the configured model')
        client.headers['x-factory-token'] = client.get('/api/session').json()['token']
        response = client.post(f'/api/projects/{project}/build', json={'mode': 'demo'})
    assert response.status_code == 409
    assert 'Factory chat is still running' in response.json()['detail']
    assert store.job(job)['progress'] == 'Waiting for the configured model'


def test_build_watchdog_releases_a_stalled_project(tmp_path, monkeypatch):
    import app.web as web

    class ImmediateTimer:
        daemon = False

        def __init__(self, _seconds, callback):
            self.callback = callback

        def start(self):
            self.callback()

        def cancel(self):
            pass

    monkeypatch.setattr(web.threading, 'Timer', ImmediateTimer)
    monkeypatch.setattr(web, 'run_build', lambda *args, **kwargs: {'status': 'passed'})
    application = web.create_app(tmp_path)
    store = application.state.store
    project = store.create('Watchdog', 'Research question')['id']

    with TestClient(application) as client:
        client.headers['x-factory-token'] = client.get('/api/session').json()['token']
        response = client.post(f'/api/projects/{project}/build', json={'mode': 'demo'})
        job = store.job(response.json()['job_id'])

    assert job['status'] == 'failed'
    assert 'unlocked' in job['error']
    assert store.start_job(project, 'chat')


def test_terminal_job_and_project_can_be_deleted_with_their_files(tmp_path):
    application = create_app(tmp_path)
    store = application.state.store
    project = store.create('Cleanup', 'Remove failed build artifacts')['id']
    job = store.start_job(project, 'build')
    workspace = store.directory(project) / 'builds' / 'agent' / 'build-id'
    telemetry = store.directory(project) / 'builds' / '.factory_runs' / 'build-id'
    workspace.mkdir(parents=True)
    telemetry.mkdir(parents=True)
    (workspace / 'agent.py').write_text('pass', encoding='utf-8')
    store.update_job(job, 'failed', result={
        'build_id': 'build-id', 'workspace': str(workspace),
        'telemetry_path': str(telemetry), 'status': 'failed',
    })
    ProjectWiki(store.directory(project)).add('Failed build', 'cleanup', kind='build', agent_id=job)

    with TestClient(application) as client:
        client.headers['x-factory-token'] = client.get('/api/session').json()['token']
        response = client.delete(f'/api/projects/{project}/jobs/{job}')
        assert response.status_code == 200
        assert not workspace.exists() and not telemetry.exists()
        assert store.jobs(project) == []
        assert ProjectWiki(store.directory(project)).entries() == []
        response = client.delete(f'/api/projects/{project}')
        assert response.status_code == 200
        assert client.get(f'/api/projects/{project}').status_code == 404
        assert not store.directory(project).exists()


def test_web_project_workflow(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.get('/').status_code == 200
        assert client.get('/api/health').json() == {
            'status': 'ok', 'service': 'research-agent-factory', 'version': '0.1.3',
        }
        session = client.get('/api/session').json()
        catalogue = {item['model']: item for item in session['models']}
        assert 'openrouter/free' not in catalogue
        assert catalogue['openai/gpt-6-luna']['tier'] == 'Fast'
        assert catalogue['openai/gpt-6-sol']['tier'] == 'Strong'
        assert 'apodex/apodex-1.1-mini:free' not in catalogue
        assert catalogue['openai/gpt-6.1-sol-pro']['tier'] == 'Maximum reasoning'
        assert len(catalogue) >= 9
        assert all(float(item['max_call_usd']) <= 1 for item in catalogue.values())
        assert client.post('/api/projects', json={}).status_code == 403
        client.headers['x-factory-token'] = session['token']
        assert client.post('/api/projects', json={}, headers={'origin': 'https://evil.example'}).status_code == 403
        same_origin = client.post('/api/projects', json={}, headers={'origin': 'http://testserver'})
        assert same_origin.status_code == 422
        result = client.post('/api/projects', json={'name': 'Test', 'question': 'Regression evidence?'})
        assert result.status_code == 201
        identifier = result.json()['id']
        base = '/api/projects/' + identifier
        free_model = client.post(base + '/chat', json={
            'query': 'Do not run', 'mode': 'live',
            'model_provider': 'openrouter', 'model': 'openrouter/free',
        })
        assert free_model.status_code == 400
        assert 'Apenas modelos pagos' in free_model.json()['detail']
        assert not [job for job in client.get(base).json()['jobs']
                    if job['status'] in {'queued', 'running'}]
        uploaded = client.post(base + '/documents', files={'file': ('notes.txt', b'Regression evidence supports comparisons')})
        assert uploaded.status_code == 200
        assert client.get(base + '/wiki').json()[0]['kind'] == 'source'
        hit = client.post(base + '/search', json={'query': 'regression'}).json()['hits'][0]
        assert hit['citation'].endswith(':1')
        assert client.get(base + '/documents/' + uploaded.json()['id']).content.startswith(b'Regression')
        job_id = client.post(base + '/chat', json={'query': 'regression'}).json()['job_id']
        job = client.get('/api/jobs/' + job_id).json()
        assert job['status'] == 'passed'
        assert hit['citation'] in job['result']['answer']
        assert client.put(base + '/skills', json=['nonexistent']).status_code == 400
        assert client.get(base).json()['chunk_count'] == 1
        assert len(client.get('/api/mcps').json()['local']) == 2


def test_html_harness_exposes_and_calls_the_live_python_factory(tmp_path, monkeypatch):
    import app.web as web

    captured = {}

    def fake_run_build(store, project_id, **options):
        captured.update(project_id=project_id, **options)
        return {"status": "passed", "build_id": "00000000-0000-0000-0000-000000000001",
                "workspace": "", "agent_name": "trace-agent", "errors": []}

    application = create_app(tmp_path)
    with TestClient(application) as client:
        manifest = client.get('/api/harness').json()
        assert manifest['status'] == 'connected'
        assert manifest['runtime_entrypoint'] == 'app.project_runtime.run_build'
        assert manifest['factory_entrypoint'].endswith('BuilderHarness.build_research')
        assert {stage['id'] for stage in manifest['stages']} >= {
            'skills', 'retrieval', 'research_protocol', 'capabilities', 'generation', 'gates', 'tests', 'telemetry',
        }

        session = client.get('/api/session').json()
        client.headers['x-factory-token'] = session['token']
        project = client.post('/api/projects', json={
            'name': 'Harness trace', 'question': 'How should the complete factory run?', 'domain': 'research',
        }).json()
        monkeypatch.setattr(web, 'get_settings', lambda: SimpleNamespace(
            model_provider='openrouter', openrouter_api_key='test-key', openai_api_key=None,
        ))
        monkeypatch.setattr(web, 'run_build', fake_run_build)
        response = client.post(f"/api/projects/{project['id']}/build", json={
            'mode': 'live', 'backend': 'configured', 'repairs': 2,
            'budget_usd': '0.75',
            'question': 'How does factory-stage validation affect research-agent reliability across builds?',
        })
        assert response.status_code == 200
        job = client.get('/api/jobs/' + response.json()['job_id']).json()

    assert job['status'] == 'passed'
    assert captured['project_id'] == project['id']
    assert captured['mode'] == 'live'
    assert captured['backend'] == 'configured'
    assert captured['repairs'] == 2
    assert captured['budget_usd'] == Decimal('0.75')
    assert captured['question'] == 'How does factory-stage validation affect research-agent reliability across builds?'


def test_skill_catalog_integrity():
    from app.registry.skills import SkillLibrary
    library = SkillLibrary()
    assert len(library.entries) >= 55
    for entry in library.entries:
        if entry['enabled']:
            assert library.read(entry['id'])


def test_skill_selection_routes_scientific_and_domain_methods():
    from app.registry.skills import SkillLibrary
    selected = SkillLibrary().select(
        'Compare neural network optimizers and post-training model compressibility',
        max_skills=5,
    )['selected']
    assert selected[:2] == ['dougtrajano-arxiv-search', 'zsun79-write-literature-review']
    assert 'foryourhealth111-pixel-evaluating-machine-learning-models' in selected
    assert 'sergebulaev-linkedin-skills' not in selected


def test_runtime_tools_respect_selected_subset():
    assert project_tools('.', 'unused', allowed_tools=[]) == []
    selected = project_tools('.', 'unused', allowed_tools=['factory-bm25/search'])
    assert [tool.name for tool in selected] == ['search_documents']
    with pytest.raises(ValueError):
        project_tools('.', 'unused', allowed_tools=['factory-web/web_search'])


def test_real_mcp_stdio_project_scope(tmp_path):
    store = ProjectStore(tmp_path)
    identifier = store.create('A', 'Regression?')['id']
    other = store.create('B', 'Other?')['id']
    store.add_document(identifier, 'source.txt', b'Regression evidence')
    result = asyncio.run(call_local_mcp('bm25', tmp_path, identifier, 'search', {'query': 'regression'}))
    assert 'Regression evidence' in str(result)
    other_result = asyncio.run(call_local_mcp('bm25', tmp_path, other, 'search', {'query': 'regression'}))
    assert 'Regression evidence' not in str(other_result)


def test_demo_build_end_to_end(tmp_path):
    from app.project_runtime import run_build
    store = ProjectStore(tmp_path)
    identifier = store.create('Demo', 'Compare regression methods')['id']
    result = run_build(store, identifier, mode='demo', question='Estimate a panel model and compare clustered errors')
    assert result['status'] == 'passed', result
    from pathlib import Path
    workspace = Path(result['workspace'])
    assert (workspace / 'evaluation_plan.json').is_file()
    protocol = json.loads((workspace / 'research_protocol.json').read_text(encoding='utf-8'))
    assert protocol['question']['question'] == 'Estimate a panel model and compare clustered errors'
    assert json.loads((workspace / 'runtime_config.json').read_text())['allowed_tools'] == []


def test_web_evaluation_archive(tmp_path):
    from app.project_runtime import run_build
    from app.planning.research_validation import protocol_digest
    from app.schemas.research import ResearchProtocol
    from pathlib import Path
    application = create_app(tmp_path)
    store = application.state.store
    identifier = store.create('Eval', 'Compare methods')['id']
    build = run_build(store, identifier)
    job = store.start_job(identifier, 'build')
    store.update_job(job, 'passed', result=build)
    protocol = ResearchProtocol.model_validate_json((Path(build['workspace']) / 'research_protocol.json').read_text(encoding='utf-8'))
    values = {'protocol_sha256': protocol_digest(protocol), 'origin': 'synthetic',
              'candidate_method': 'A', 'code_version': 'test', 'dataset_version': 'synthetic',
              'parameters_json': '{}', 'measurements': [
                  {'method': method, 'metric': 'error', 'seed': seed, 'value': value}
                  for method, value in [('A', .8), ('B', 1.)] for seed in protocol.seeds]}
    with TestClient(application) as client:
        client.headers['x-factory-token'] = client.get('/api/session').json()['token']
        url = f'/api/projects/{identifier}/evaluations'
        response = client.post(url + '?job_id=' + job, files={'file': ('measurements.json', json.dumps(values).encode())})
        assert response.status_code == 200, response.text
        assert len(client.get(url).json()) == 1
        values['parameters_json'] = '{"overflow":1e999}'
        response = client.post(url + '?job_id=' + job, files={'file': ('bad.json', json.dumps(values).encode())})
        assert response.status_code == 400


def test_public_search_and_host_restrictions():
    import httpx
    from app.research_web import read_public, search_papers
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
        'message': {'items': [{'title': ['A paper'], 'URL': 'https://doi.org/example', 'DOI': 'example'}]}}))
    assert search_papers('regression', transport=transport)[0]['title'] == 'A paper'
    for url in ['http://api.crossref.org', 'https://localhost/x', 'https://api.crossref.org@localhost', 'https://api.crossref.org:9000']:
        with pytest.raises(ValueError):
            read_public(url, transport=transport)


def test_arxiv_html_fallback_on_406():
    import httpx
    from app.research_web import search_papers
    html = '''<li class="arxiv-result"><p class="list-title"><a href="https://arxiv.org/abs/1234.5678">arXiv</a></p>
      <p class="title">A regression paper</p><p class="abstract">Abstract: Evidence</p>
      <p class="is-size-7">Submitted 2026</p></li>'''
    def response(request):
        return httpx.Response(406 if request.url.host == 'export.arxiv.org' else 200,
                              text='' if request.url.host == 'export.arxiv.org' else html)
    result = search_papers('regression', limit=1, provider='arxiv', transport=httpx.MockTransport(response))
    assert result[0]['title'] == 'A regression paper'
    assert result[0]['url'] == 'https://arxiv.org/abs/1234.5678'


def test_agent_dossier_budget_and_wiki(tmp_path):
    from app.project_runtime import run_build
    from app.wiki import ProjectWiki
    application=create_app(tmp_path)
    store=application.state.store
    project=store.create('Causal study', 'Compare models')['id']
    store.add_document(project,'evidence.txt',b'Compare models with regression evidence')
    ProjectWiki(store.directory(project)).add('Working hypothesis','Compare both methods under matched seeds')
    build=run_build(store,project,budget_usd='2.50')
    job=store.start_job(project,'build')
    store.update_job(job,'passed',result=build)
    with TestClient(application) as client:
        client.headers['x-factory-token']=client.get('/api/session').json()['token']
        dossier=client.get(f'/api/projects/{project}/agents/{job}').json()
        assert dossier['costs']['budget_usd']=='2.50'
        assert dossier['spec']['name']=='offline_demo'
        assert dossier['rag']['hits'][0]['source']=='evidence.txt'
        assert dossier['rag']['documents'][0]['name']=='evidence.txt'
        assert dossier['rag']['wiki_entries'][0]['title']=='Working hypothesis'
        assert any(file['path']=='agent.py' for file in dossier['code_files'])
        note=client.post(f'/api/projects/{project}/wiki',json={'title':'Next step','content':'Review dataset versions','agent_id':job})
        assert note.status_code==201
        assert len(client.get(f'/api/projects/{project}/wiki').json())==2
        zipped=client.get(f'/api/projects/{project}/wiki/export')
        assert zipped.status_code==200 and zipped.content[:2]==b'PK'
        assert client.post(f'/api/projects/{project}/build',json={'budget_usd':'101'}).status_code==422
