import { mountResearchScene, mountSetupScene } from '/static/scene.js';

const $ = selector => document.querySelector(selector);
const safe = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const state = {token:'',session:{},integrations:{providers:{},obsidian:{}},harness:{},projects:[],skills:[],project:null,view:'home',tab:'overview',agent:null};
const date = value => value ? new Date(value).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}) : '—';
const money = value => '$' + Number(value ?? 0).toFixed(2);
const statuses = {passed:'READY',failed:'FAILED',blocked:'BLOCKED',running:'RUNNING',queued:'QUEUED',interrupted:'INTERRUPTED'};

function modelKey(provider,model) { return `${provider || ''}|${model || ''}`; }

function modelByKey(key) {
  return (state.session.models || []).find(item=>modelKey(item.provider,item.model)===key);
}

function modelOptions(provider,model) {
  const available=(state.session.models || []).filter(item=>item.configured);
  const selected=modelKey(provider || state.session.provider,model || state.session.model);
  const effective=available.some(item=>modelKey(item.provider,item.model)===selected)?selected:modelKey(available[0]?.provider,available[0]?.model);
  return (state.session.models || []).map(item=>`<option value="${safe(modelKey(item.provider,item.model))}" ${modelKey(item.provider,item.model)===effective?'selected':''} ${item.configured?'':'disabled'}>${safe(item.label)} · ${safe(item.tier)}${item.configured?'':' · KEY'}</option>`).join('');
}

function modelControl(provider,model,label='AI MODEL') {
  return `<label class="model-control">${safe(label)}<select name="model_choice" required>${modelOptions(provider,model)}</select></label>`;
}

function selectedModelFields(data) {
  const choice=modelByKey(data.model_choice);
  delete data.model_choice;
  if(choice){data.model_provider=choice.provider;data.model=choice.model;}
  return data;
}

function responseDiagnostics(details) {
  const run=(details.response_runs || [])[0];
  if(!run)return `<div class="response-diagnostics legacy"><strong>Response diagnostics</strong><span>No diagnostic record exists yet. Send a new message to record model and context.</span></div>`;
  if(run.status!=='passed')return `<div class="response-diagnostics failed"><strong>Last response failed</strong><span>${safe(run.error || 'The provider returned no usable reply.')}</span></div>`;
  const result=run.result || {}, model=result.model || {}, context=result.context || {};
  const papers=(result.literature || []).map(paper=>`<li><a href="${safe(/^https:\/\//.test(paper.url||'')?paper.url:'#')}" ${/^https:\/\//.test(paper.url||'')?'target="_blank" rel="noopener noreferrer"':''}>${safe(paper.title)}</a><small>${safe(paper.citation)}</small></li>`).join('');
  return `<details class="response-diagnostics"><summary><strong>Last response diagnostics</strong><span>${safe(model.resolved || model.requested || 'model not reported')}</span></summary><div class="diagnostic-grid"><div><small>REQUESTED MODEL</small><b>${safe(model.requested || '—')}</b></div><div><small>RESOLVED MODEL</small><b>${safe(model.resolved || 'Provider did not report it')}</b></div><div><small>RESEARCH CONTRACTS</small><b>${context.research_question&&context.research_protocol?'Question + protocol supplied':'Incomplete'}</b></div><div><small>RESEARCH CONTEXT</small><b>${Number(context.source_passages||0)} local passages · ${Number(context.external_papers||0)} external papers</b></div><div><small>SKILLS APPLIED</small><b>${Number(context.effective_skills??context.skills??0)} methodological guides</b></div><div><small>TOOLS AVAILABLE</small><b>${(result.tools||details.chat_tools||[]).map(safe).join(' · ')||'—'}</b></div></div>${papers?`<div class="literature-results"><strong>Literature retrieved for this reply</strong><ul>${papers}</ul></div>`:''}<p>Reported cost: ${money(result.costs?.reported_cost_usd)}. Open Project details → Activity for the full audit record.</p></details>`;
}

function factoryResponseDiagnostics(project) {
  const run=(project.jobs || []).find(job=>job.kind==='chat'&&job.status==='passed'&&job.result?.mode==='live');
  if(!run)return '';
  const result=run.result || {}, model=result.model || {};
  return `<details class="response-diagnostics factory-diagnostics"><summary><strong>Latest factory reply</strong><span>${safe(model.resolved || model.requested || 'legacy response')}</span></summary><div class="diagnostic-grid"><div><small>REQUESTED MODEL</small><b>${safe(model.requested || 'Not recorded')}</b></div><div><small>RESOLVED MODEL</small><b>${safe(model.resolved || 'Provider did not report it')}</b></div><div><small>PROJECT EVIDENCE</small><b>${Number(result.context?.source_passages ?? result.sources?.length ?? 0)} passages supplied</b></div><div><small>REPORTED COST</small><b>${money(result.costs?.reported_cost_usd)}</b></div></div></details>`;
}

function harnessSummary() {
  const harness=state.harness || {}, stages=harness.stages || [];
  if(harness.status!=='connected')return '';
  return `<details class="python-harness-proof"><summary><span><i></i> FULL PYTHON FACTORY CONNECTED</span><b>${stages.length} VERIFIED STAGES</b></summary><div class="python-harness-body"><code>HTML → ${safe(harness.runtime_entrypoint)} → ${safe(harness.factory_entrypoint)}</code><ol>${stages.map(stage=>`<li><span>${safe(stage.id.replaceAll('_',' '))}</span>${safe(stage.label)}</li>`).join('')}</ol><p>${safe(harness.scope)}</p></div></details>`;
}

function toast(message) {
  const element = $('#toast');
  element.textContent = String(message);
  element.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => element.hidden = true, 6500);
}

function integrationMark(item) {
  return `<span class="connection-mark ${item?.configured||item?.connected?'online':''}"></span>`;
}

function renderSetup() {
  const providers=state.integrations.providers||{}, obsidian=state.integrations.obsidian||{};
  $('#setup-body').innerHTML=`<div class="setup-visual" id="setup-scene"><span>API ⇄ AGENT ⇄ MEMORY</span></div><div class="setup-grid">
    ${['openrouter','openai'].map(id=>{const item=providers[id]||{label:id.toUpperCase(),configured:false};return `<section class="setup-card"><div class="setup-card-head">${integrationMark(item)}<strong>${safe(item.label).toUpperCase()}</strong><span>${item.configured?'ON':'OFF'}</span></div><form class="provider-form" data-provider-form="${id}"><input type="password" name="api_key" required minlength="20" maxlength="500" autocomplete="new-password" placeholder="API_KEY"><button>${item.configured?'UPDATE':'CONNECT'}</button></form>${item.configured?`<button class="setup-remove" data-remove-provider="${id}">×</button>`:''}</section>`;}).join('')}
    <section class="setup-card obsidian-card"><div class="setup-card-head">${integrationMark(obsidian)}<strong>OBSIDIAN</strong><span>${obsidian.connected?'ON':'OFF'}</span></div><form id="obsidian-form"><input name="path" required maxlength="1000" value="${safe(obsidian.path||'')}" placeholder="C:/VAULT"><button>LINK</button></form>${obsidian.connected?'<button class="setup-remove" data-action="disconnect-obsidian">×</button>':''}</section>
  </div>`;
  requestAnimationFrame(()=>mountSetupScene($('#setup-scene')));
}

function openSetup() {
  renderSetup();
  const dialog=$('#setup-dialog');
  if(!dialog.open)dialog.showModal();
}

async function refreshConnections() {
  [state.session,state.integrations]=await Promise.all([api('/session'),api('/integrations')]);
  state.token=state.session.token;
}

async function api(path, options={}) {
  const headers = {'x-factory-token':state.token,...options.headers};
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch('/api' + path,{...options,headers});
  let data;
  try { data = await response.json(); }
  catch { throw new Error('The server returned an unexpected response.'); }
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === 'string' ? detail : 'Check the submitted values.');
  }
  return data;
}

function setView(view, subtitle) {
  state.view = view;
  if (['home','agents','library','mcps'].includes(view) && location.hash) {
    history.replaceState(null,'',location.pathname + location.search);
  }
  document.querySelectorAll('[data-view]').forEach(button => button.classList.toggle('active',button.dataset.view === view));
  $('#breadcrumb').innerHTML = `FACTORY <span>/</span> ${safe(subtitle || view.toUpperCase())}`;
  mountResearchScene(null);
}

function section(title, number, extra='') {
  return `<div class="section-heading"><div><div class="section-index">${safe(number)}</div><h2>${safe(title)}</h2></div>${extra}</div>`;
}

function empty(title, detail) {
  return `<div class="empty"><span>∅</span><h3>${safe(title)}</h3></div>`;
}

function badge(status) {
  const type = ['passed','available'].includes(status) ? 'good' : ['failed','blocked','interrupted'].includes(status) ? 'bad' : 'warn';
  return `<span class="badge ${type}">${safe(statuses[status] || status)}</span>`;
}

function projectCard(project, index) {
  return `<button class="project-card" data-project="${project.id}" data-project-tab="agents"><div class="card-top"><span>${String(index+1).padStart(2,'0')} //</span><span class="status-dot"></span></div><h3>${safe(project.name)}</h3><div class="project-card-stats"><span>${String(project.agent_count||0).padStart(2,'0')} AGENTS</span><span>${date(project.created)}</span></div><div class="card-footer"><b>OPEN ↗</b></div></button>`;
}

function renderHome() {
  state.project = null;
  state.agent = null;
  setView('home','OVERVIEW');
  const agents = state.projects.reduce((count,project) => count + (project.agent_count || 0),0);
  $('#main').innerHTML = `
    <section class="hero terminal-hero"><div class="hero-visual" id="research-scene"><div class="hero-grid"></div><div class="hero-caption">∫ f(x)dx // RAF.01</div></div><div class="hero-copy"><div class="terminal-kicker"><i></i> SYSTEM READY</div><h1>AGENT<br>FACTORY</h1><div class="hero-command"><span>root@raf:~$</span><button data-action="new-project">new_research ↵</button><i></i></div><div class="hero-counters"><span><b>${String(state.projects.length).padStart(2,'0')}</b> PROJECTS</span><span><b>${String(agents).padStart(2,'0')}</b> AGENTS</span><span><b>${String(state.skills.filter(item=>item.enabled).length).padStart(2,'0')}</b> SKILLS</span></div></div></section>
    ${section('PROJECTS','// 01',`<button class="text-button" data-action="new-project">+ NEW</button>`)}
    <div class="project-grid" id="project-grid">${state.projects.map(projectCard).join('')}<button class="project-card new-card" data-action="new-project"><span class="plus">+</span><h3>NEW_PROJECT</h3></button></div>`;
  mountResearchScene($('#research-scene'));
}

async function refreshProjects() {
  const projects = await api('/projects');
  const counts = await Promise.all(projects.map(async project => {
    const full = await api('/projects/' + project.id);
    return {...project,agent_count:full.jobs.filter(job=>job.kind==='build'&&job.status==='passed').length};
  }));
  state.projects = counts;
}

function projectHeader() {
  const project = state.project;
  const tabs = [['agents','FACTORY']];
  const details = [['overview','OVERVIEW'],['sources','RAG'],['skills','SKILLS'],['wiki','MEMORY'],['activity','LOG']];
  return `<div class="page-heading project-heading"><div><div class="eyebrow">PROJECT // ${safe(project.domain).toUpperCase()}</div><h1>${safe(project.name)}</h1></div><div class="project-heading-actions"><button class="outline-button icon-action" title="Refresh" aria-label="Refresh" data-action="refresh-project">↻</button><details class="project-details-menu"><summary aria-label="Project sections">≡</summary><div class="details-menu-items">${details.map(([key,label])=>`<button class="${state.tab===key?'active':''}" data-tab="${key}">${label}</button>`).join('')}<button class="danger-action" data-action="delete-project">DELETE</button></div></details></div></div><div class="tabs primary-project-tabs" role="tablist">${tabs.map(([key,label])=>`<button class="tab ${state.tab===key?'active':''}" role="tab" aria-selected="${state.tab===key}" data-tab="${key}">${label}</button>`).join('')}</div>`;
}

async function openProject(identifier,tab='agents') {
  state.project = await api('/projects/' + identifier);
  state.agent = null;
  state.tab = tab;
  renderProject();
  location.hash = '#project/' + identifier + '/' + tab;
}

function renderProject() {
  const project = state.project;
  setView('project',project.name.toUpperCase());
  let content = '';
  if (state.tab === 'overview') {
    content = `<div class="panel-grid compact-overview"><section class="card query-card"><div class="kicker">QUERY</div><div class="question">${safe(project.question)}</div></section><section class="card system-grid"><button data-tab="sources"><span>Σ</span><b>${project.documents.length}</b><small>SOURCES</small></button><button data-tab="skills"><span>✳</span><b>${project.skills.length}</b><small>SKILLS</small></button><button data-tab="agents"><span>⌘</span><b>${project.jobs.filter(j=>j.kind==='build'&&j.status==='passed').length}</b><small>AGENTS</small></button></section></div>${section('LOG','// 02')}${project.jobs.slice(0,4).map(jobCard).join('')||empty('NO_LOG','')}`;
  }
  if (state.tab === 'sources') content = sourcesView(project);
  if (state.tab === 'agents') content = agentsView(project);
  if (state.tab === 'skills') content = skillsView(project);
  if (state.tab === 'wiki') {const linked=state.integrations.obsidian?.connected;content = `<div class="memory-io"><span>OBSIDIAN ${linked?'●':'○'}</span><button class="text-button" data-action="${linked?'sync-obsidian':'setup'}">${linked?'SYNC':'LINK'}</button><a class="text-button" href="/api/projects/${project.id}/wiki/export" download>ZIP ↓</a></div><div class="split"><section class="card"><div class="kicker">MEMORY.WRITE</div><form id="wiki-form"><label>TITLE<input name="title" required maxlength="160" placeholder="entry"></label><label>NOTE<textarea name="content" required maxlength="50000" rows="6" placeholder="_"></textarea></label><div class="card-actions"><button class="primary-button">SAVE ↵</button></div></form></section><section><div class="kicker">MEMORY.LOG</div><div id="wiki-entries">...</div></section></div>`;}
  if (state.tab === 'activity') content = `${section('LOG','// AUDIT')}${project.jobs.map(jobCard).join('')||empty('NO_LOG','')}`;
  $('#main').innerHTML = projectHeader() + content;
  if(state.tab==='agents') requestAnimationFrame(()=>{const history=$('#chat-history');if(history)history.scrollTop=history.scrollHeight;});
  if (state.tab === 'wiki') loadWiki();
  if (state.tab === 'skills') renderSkillCards();
  if (state.tab === 'sources') attachDrop();
}

function jobCard(job) {
  const kind = {build:'AGENT BUILD',chat:'RESEARCH QUERY',skills:'SKILL SELECTION'}[job.kind] || job.kind.toUpperCase();
  return `<article class="connection compact-log"><div><div class="kicker">${kind} // ${date(job.created)}</div><h3>${job.kind==='build' ? safe(job.result?.build_id?.slice(0,8) || job.id.slice(0,8)) : safe(job.id.slice(0,8))}</h3><div class="card-actions"><button class="text-button" data-job="${job.id}">LOG</button>${job.kind==='build'&&job.result?.workspace?`<button class="text-button" data-agent="${job.id}">OPEN</button>`:''}${!['queued','running'].includes(job.status)?`<button class="text-button danger-text" data-delete-job="${job.id}">×</button>`:''}</div></div>${badge(job.status)}</article>`;
}

function sourcesView(project) {
  return `<div class="split"><section><label class="dropzone" id="dropzone"><span class="drop-symbol">＋</span><strong>UPLOAD</strong><small>PDF · DOCX · TXT · MD · CSV · JSON</small><input type="file" id="source-files" multiple accept=".pdf,.docx,.txt,.md,.csv,.json" aria-label="Add source documents"></label><div class="card"><div class="kicker">SOURCES // ${project.documents.length}</div>${project.documents.map(document => `<div class="doc-row"><span class="resource-icon">${safe(document.name.split('.').pop().toUpperCase())}</span><div><strong>${safe(document.name)}</strong><small>${(document.size/1024).toFixed(1)} KB</small></div><a href="/api/projects/${project.id}/documents/${document.id}" download aria-label="Download ${safe(document.name)}">↓</a></div>`).join('')||empty('NO_SOURCES','')}</div></section><section><div class="card"><div class="kicker">BM25.SEARCH</div><form id="rag-form" class="inline-form command-search"><span>&gt;</span><input name="query" required placeholder="query_" aria-label="Search sources"><button class="primary-button">RUN</button></form><div id="rag-results"></div></div></section></div>${section('WEB.SEARCH','// SCHOLARLY')}<form id="web-form" class="inline-form command-search"><span>&gt;</span><input name="query" required placeholder="query_" aria-label="Literature query"><select name="provider" aria-label="Provider"><option value="crossref">CROSSREF</option><option value="arxiv">ARXIV</option><option value="openalex">OPENALEX</option><option value="semantic_scholar">SEMANTIC</option></select><button class="secondary-button">RUN</button></form><div id="web-results"></div>`;
}

function agentsView(project) {
  const builds = project.jobs.filter(job=>job.kind==='build');
  const ready = state.session.has_key;
  const briefReady = Boolean(project.research_status?.ready);
  const activeOperation = project.jobs.find(job=>['queued','running'].includes(job.status));
  const activeBuild = builds.find(job=>['queued','running'].includes(job.status));
  const activeLabel=activeOperation?({build:'BUILD',chat:'CHAT',agent_chat:'AGENT',skills:'SKILLS'}[activeOperation.kind]||activeOperation.kind.toUpperCase()):'';
  const progress=activeOperation?`<div class="operation-progress terminal-status" id="operation-progress" role="status"><span class="working-spinner" aria-hidden="true"></span><strong>${safe(activeLabel)}::${safe(statuses[activeOperation.status]||activeOperation.status)}</strong><small>${safe(activeOperation.progress||'...')}</small></div>`:'<div id="operation-progress" hidden></div>';
  const latestOperation=project.jobs[0];
  const failedOperation=['failed','interrupted'].includes(latestOperation?.status)&&
    Date.now()-new Date(latestOperation.created).getTime()<86400000?latestOperation:null;
  const failureNotice=(failedOperation?`<div class="terminal-alert operation-failed">! ${safe(failedOperation.kind.toUpperCase())}::${safe(failedOperation.status.toUpperCase())}</div>`:'')+factoryResponseDiagnostics(project);
  const agentRows=builds.map(job=>`<article class="agent-list-row"><div class="agent-list-mark">∑</div><div class="agent-list-copy"><strong>${safe(job.result?.agent_name || (job.status==='failed'?'FAILED_BUILD':'RESEARCH_AGENT'))}</strong><small>${safe(statuses[job.status]||job.status)} // ${date(job.created)}</small></div>${job.result?.build_id?`<button class="text-button" data-agent="${job.id}" ${job.status==='queued'||job.status==='running'?'disabled':''}>↗</button>`:''}${!['queued','running'].includes(job.status)?`<button class="icon-delete" data-delete-job="${job.id}" aria-label="Delete ${safe(job.result?.agent_name||'build')}">×</button>`:''}</article>`).join('');
  const messages=project.messages.map(message=>`<article class="terminal-line ${message.role==='user'?'from-user':'from-agent'}"><span class="terminal-prompt">${message.role==='user'?'you@research:~$':'factory@raf:~#'}</span><pre>${safe(message.content)}</pre></article>`).join('');
  const evaluations=`<details class="secondary-workflows"><summary>EVAL</summary><section class="card"><form id="evaluation-form"><div class="form-grid"><label>BUILD<select name="job_id" required>${builds.filter(job=>job.status==='passed').map(job=>`<option value="${job.id}">${safe(job.result?.build_id || job.id)}</option>`).join('')}</select></label><label>JSON<input type="file" name="file" accept=".json" required></label></div><button class="secondary-button" ${builds.some(job=>job.status==='passed')?'':'disabled'}>RUN</button></form><button class="text-button" data-action="evaluation-history">LOG</button><pre id="evaluation-output" class="json-view" hidden></pre></section></details>`;
  const factoryModelControl=modelControl(state.session.provider,state.session.model,'MODEL');
  const buildModelControl=modelControl(state.session.provider,state.session.model,'MODEL');
  return `<div class="factory-workspace terminal-workspace"><section class="factory-terminal"><div class="terminal-bar"><div class="terminal-dots"><i></i><i></i><i></i></div><span>factory://${safe(project.name.toLowerCase().replaceAll(' ','_'))}</span><b><i></i> ${briefReady?'READY':'INTAKE'}</b></div>${progress}${failureNotice}<div id="chat-history" class="factory-chat-history terminal-output">${messages||`<article class="terminal-line from-agent"><span class="terminal-prompt">factory@raf:~#</span><pre>${briefReady?'BUILD_READY_':'DEFINE_QUERY_'}</pre></article>`}</div>${ready?'':'<div class="terminal-alert">! API_KEY</div>'}${briefReady?'':'<div class="terminal-alert">! DEFINE_QUERY</div>'}<form id="chat-form" class="terminal-command"><input type="hidden" name="mode" value="live"><div class="terminal-config">${factoryModelControl}</div><div class="terminal-input-row"><span class="terminal-prompt">you@research:~$</span><textarea id="factory-chat-query" name="query" required maxlength="5000" rows="1" aria-label="Factory command" placeholder="_" ${ready&&!activeOperation?'':'disabled'}></textarea><button type="submit" ${ready&&!activeOperation?'':'disabled'}>${activeOperation?'...':'RUN'}</button></div></form><details class="create-agent-details"><summary><span>build_agent</span><b>${activeOperation?(activeBuild?'RUNNING':'LOCKED'):(briefReady?'READY':'DEFINE')}</b></summary><div class="create-agent-body">${harnessSummary()}<form id="build-form"><input type="hidden" name="mode" value="live"><input type="hidden" name="backend" value="configured"><input type="hidden" name="repairs" value="1"><label>QUERY<textarea name="question" maxlength="10000" rows="2" required ${activeOperation?'disabled':''}>${safe(project.question)}</textarea></label><details class="build-settings"><summary>CONFIG // $1.00</summary><div class="settings-body">${buildModelControl}<label>BUDGET<input name="budget_usd" type="number" min="0.01" max="1.00" step="0.01" value="${safe(state.session.default_build_budget_usd || '1.00')}" required ${activeOperation?'disabled':''}></label></div></details><button type="submit" class="primary-button build-submit" ${ready&&briefReady&&!activeOperation?'':'disabled'}>${activeBuild?'RUNNING':activeOperation?'LOCKED':briefReady?'EXECUTE ↵':'DEFINE QUERY'}</button></form></div></details></section><aside class="agent-list-panel"><div class="agent-list-heading"><div class="kicker">AGENTS</div><span class="agent-count">${String(builds.length).padStart(2,'0')}</span></div><div class="agent-list">${agentRows||empty('∅','')}</div>${evaluations}</aside></div>`;
}

function skillsView(project) {
  return `${section('SKILLS','// '+project.skills.length)}<div class="compact-toolbar"><button class="secondary-button" data-action="suggest-skills">BM25</button><button class="secondary-button" data-action="jev-skills">JEV</button><button class="primary-button" data-action="save-skills">SAVE</button><input id="skill-filter" class="search-field" placeholder="filter_" aria-label="Filter skills"></div><div id="skill-grid" class="skill-grid"></div>`;
}

function renderSkillCards(query='') {
  const container = $('#skill-grid');
  if (!container) return;
  const chosen = new Set(state.project?.skills || []);
  container.innerHTML = state.skills.filter(item => (item.id + ' ' + item.description).toLowerCase().includes(query.toLowerCase())).map(item => `<article class="skill-card minimal-skill">${state.project ? `<input type="checkbox" data-skill="${safe(item.id)}" ${chosen.has(item.id)?'checked':''} ${item.enabled?'':'disabled'} aria-label="Select ${safe(item.id)}">` : ''}<div><div class="kicker">${item.kind==='mcp'?'MCP':'SKILL'}</div><h3>${safe(item.id)}</h3><div class="card-actions"><span class="status-dot ${item.enabled?'':'off'}"></span>${item.enabled?`<button class="text-button" data-skill-detail="${safe(item.id)}">READ</button>`:''}<a href="${safe(item.repository)}" target="_blank" rel="noopener noreferrer">↗</a></div></div></article>`).join('');
}

function renderLibrary() {
  state.project=null;
  setView('library','SKILL LIBRARY');
  $('#main').innerHTML = `<div class="page-heading compact-heading"><div><div class="eyebrow">LIBRARY</div><h1>SKILLS</h1></div><b class="page-count">${state.skills.length}</b></div>${section('INDEX','// 03',`<input id="skill-filter" class="search-field" placeholder="filter_" aria-label="Filter skills">`)}<div id="skill-grid" class="skill-grid"></div>`;
  renderSkillCards();
}

async function renderMcps() {
  state.project=null;
  setView('mcps','MCP SYSTEMS');
  const data = await api('/mcps');
  $('#main').innerHTML = `<div class="page-heading compact-heading"><div><div class="eyebrow">SYSTEMS</div><h1>MCP</h1></div><b class="page-count">${data.local.length}</b></div>${section('LOCAL','// ONLINE')}<div class="split">${data.local.map(item=>`<article class="connection compact-system"><div><div class="kicker">PYTHON.STDIO</div><h3>${safe(item.id)}</h3><code>${item.id==='factory-bm25'?'bm25':'web'}</code></div>${badge(item.status)}</article>`).join('')}</div>${section('CATALOGUE','// OFFLINE')}${data.external.map(item=>`<article class="connection compact-system"><div><h3>${safe(item.id)}</h3><a href="${safe(item.repository)}" target="_blank" rel="noopener noreferrer">↗</a></div><span class="badge warn">OFFLINE</span></article>`).join('')}`;
}

async function renderAllAgents() {
  state.project=null;
  setView('agents','ALL AGENTS');
  const projects = await Promise.all(state.projects.map(project=>api('/projects/' + project.id)));
  const agents = projects.flatMap(project=>project.jobs.filter(job=>job.kind==='build').map(job=>({project,job})));
  $('#main').innerHTML = `<div class="page-heading compact-heading"><div><div class="eyebrow">REGISTER</div><h1>AGENTS</h1></div><b class="page-count">${agents.length}</b></div><div class="agent-grid">${agents.map(({project,job})=>`<button class="agent-card" data-all-agent="${project.id}|${job.id}"><div class="agent-top"><span class="kicker">${safe(project.name)}</span>${badge(job.status)}</div><h3>${safe(job.result?.agent_name || job.result?.build_id?.slice(0,8) || job.id.slice(0,8))}</h3><div class="card-footer"><span>${date(job.created)}</span><b>↗</b></div></button>`).join('')||empty('NO_AGENTS','')}</div>`;
}

async function showAgent(projectId,jobId) {
  const details = await api(`/projects/${projectId}/agents/${jobId}`);
  state.project = await api('/projects/' + projectId);
  state.agent = details;
  setView('agent','AGENT / ' + (details.job.result?.build_id || jobId).slice(0,8));
  location.hash = '#agent/' + projectId + '/' + jobId;
  const spec = details.spec || {};
  const cost = details.costs || {};
  const tools = details.chat_tools || details.mcp?.tools || [];
  const hits = details.rag?.hits || [];
  const files = details.code_files || [];
  $('#main').innerHTML = `<button class="text-button" data-project="${projectId}" data-project-tab="agents">← FACTORY</button><div class="agent-profile compact-agent-profile"><div><div class="eyebrow">AGENT // ${safe(details.job.status).toUpperCase()}</div><h2>${safe(spec.name || 'AGENT')}</h2></div><div class="agent-quick-stats"><span>${safe(spec.model?.model || '—')}</span><span>${money(cost.budget_usd)}</span><span>${(details.chat_skills||details.skills).length} SKILLS</span><span>${tools.length} MCP</span><span>${details.research_library?.papers?.length||0} PAPERS</span></div></div><div class="agent-dossier-nav"><button class="tab active" role="tab" aria-selected="true" data-agent-tab="chat">TERMINAL</button><details class="agent-details-menu"><summary>≡</summary><div class="details-menu-items">${[['profile','PROFILE'],['code','CODE'],['rag','RAG'],['skills','SKILLS'],['mcp','MCP'],['memory','MEMORY'],['protocol','PROTOCOL']].map(([key,label])=>`<button data-agent-tab="${key}">${label}</button>`).join('')}</div></details></div><div id="agent-panel"></div>`;
  renderAgentTab('chat');
}

function renderAgentTab(tab) {
  const details=state.agent, spec=details.spec || {}, projectId=state.project.id, jobId=details.job.id;
  document.querySelectorAll('[data-agent-tab]').forEach(button=>{
    button.classList.toggle('active',button.dataset.agentTab===tab);
    button.setAttribute('aria-selected',String(button.dataset.agentTab===tab));
  });
  const panel=$('#agent-panel');
  if (tab==='profile') panel.innerHTML=`<div class="split"><section class="card"><div class="kicker">DESIGN CONTRACT</div><h2>${safe(spec.name || 'Awaiting plan')}</h2><p>${safe(spec.objective || 'The agent specification is not available for this build.')}</p><div class="resource-row"><span class="resource-icon">I</span><div><strong>Inputs</strong><small>${safe((spec.inputs||[]).join(', ')||'—')}</small></div></div><div class="resource-row"><span class="resource-icon">O</span><div><strong>Outputs</strong><small>${safe((spec.outputs||[]).join(', ')||'—')}</small></div></div><div class="resource-row"><span class="resource-icon">A</span><div><strong>Architecture</strong><small>${safe(spec.architecture||'—')}</small></div></div></section><section class="card"><div class="kicker">BUILD RECORD</div><h2>${safe(statuses[details.job.status]||details.job.status)}</h2><p>${safe(details.job.result?.errors?.join('; ') || 'No validation errors recorded.')}</p><div class="resource-row"><span class="resource-icon accent">$</span><div><strong>Reported cost</strong><small>${money(details.costs?.reported_cost_usd)}</small></div></div><div class="resource-row"><span class="resource-icon dark">⌘</span><div><strong>Files</strong><small>${details.code_files.length} viewable artifacts</small></div></div><button class="secondary-button" data-project="${projectId}" data-project-tab="wiki">OPEN RESEARCH WIKI ↗</button></section></div>`;
  if (tab==='chat') panel.innerHTML=`<section class="factory-terminal agent-terminal"><div class="terminal-bar"><div class="terminal-dots"><i></i><i></i><i></i></div><span>agent://${safe((spec.name||'agent').toLowerCase().replaceAll(' ','_'))}</span><b><i></i> ${safe(details.job.status.toUpperCase())}</b></div><div class="terminal-tools">${(details.chat_tools||[]).map(tool=>`<span>${safe(tool)}</span>`).join('')}</div>${responseDiagnostics(details)}${details.chat_available?'':`<div class="terminal-alert">! ${safe(details.chat_unavailable_reason || 'OFFLINE')}</div>`}<div id="agent-chat-progress" hidden></div><div id="agent-chat-history" class="agent-chat-history terminal-output">${(details.messages||[]).map(message=>`<article class="terminal-line ${message.role==='user'?'from-user':'from-agent'}"><span class="terminal-prompt">${message.role==='user'?'you@research:~$':safe(spec.name||'agent')+'@raf:~#'}</span><pre>${safe(message.content)}</pre></article>`).join('')||`<article class="terminal-line from-agent"><span class="terminal-prompt">${safe(spec.name||'agent')}@raf:~#</span><pre>READY_</pre></article>`}</div><form id="agent-chat-form" class="terminal-command"><div class="terminal-config">${modelControl(spec.model?.provider,spec.model?.model,'MODEL')}</div><div class="terminal-input-row"><span class="terminal-prompt">you@research:~$</span><textarea id="agent-chat-query" name="query" maxlength="5000" required rows="1" placeholder="_" ${details.chat_available?'':'disabled'}></textarea><button type="submit" ${details.chat_available?'':'disabled'}>RUN</button></div></form></section>`;
  if (tab==='profile') panel.innerHTML=`<div class="split"><section class="card"><div class="kicker">DESIGN CONTRACT</div><h2>${safe(spec.name || 'Awaiting plan')}</h2><p>${safe(spec.objective || 'The agent specification is not available for this build.')}</p><div class="resource-row"><span class="resource-icon">I</span><div><strong>Inputs</strong><small>${safe((spec.inputs||[]).join(', ')||'—')}</small></div></div><div class="resource-row"><span class="resource-icon">O</span><div><strong>Outputs</strong><small>${safe((spec.outputs||[]).join(', ')||'—')}</small></div></div><div class="resource-row"><span class="resource-icon">A</span><div><strong>Architecture</strong><small>${safe(spec.architecture||'—')}</small></div></div></section><section class="card"><div class="kicker">BUILD RECORD</div><h2>${safe(statuses[details.job.status]||details.job.status)}</h2><p>${safe(details.job.result?.errors?.join('; ') || 'No validation errors recorded.')}</p><div class="resource-row"><span class="resource-icon accent">$</span><div><strong>Reported cost</strong><small>${money(details.costs?.reported_cost_usd)}</small></div></div><div class="resource-row"><span class="resource-icon dark">⌘</span><div><strong>Files</strong><small>${details.code_files.length} viewable artifacts</small></div></div><button class="secondary-button" data-project="${projectId}" data-project-tab="wiki">OPEN RESEARCH WIKI ↗</button></section></div>`;
  if (tab==='code') {
    const files=details.code_files.filter(file=>file.path.endsWith('.py')||file.path.endsWith('.md')||file.path.endsWith('.json'));
    panel.innerHTML=files.length?`<div class="code-layout"><div class="file-list">${files.map(file=>`<button data-code-path="${safe(file.path)}" class="${file===files[0]?'active':''}">${safe(file.path)}</button>`).join('')}</div><div class="code-area"><span class="code-label" id="code-label">${safe(files[0].path)}</span><code id="code-content">Loading…</code></div></div>`:empty('No code files','This build did not produce a viewable workspace.');
    if(files.length) loadCode(files[0].path,jobId);
  }
  if (tab==='rag') panel.innerHTML=`<div class="card"><div class="kicker">EVIDENCE SNAPSHOT / BUILD TIME</div><h2>Associated RAG.</h2><p>The source register and retrieved passages below belong to this build. Later uploads do not change this snapshot.</p><div class="metadata-grid"><div><small>STRATEGY</small><strong>BM25 / local</strong></div><div><small>DOCUMENTS</small><strong>${details.rag?.documents?.length||0}</strong></div><div><small>INDEXED CHUNKS</small><strong>${details.rag?.total_chunks||0}</strong></div><div><small>RETRIEVED</small><strong>${details.rag?.hits?.length||0}</strong></div></div><div class="kicker">SOURCE REGISTER</div>${(details.rag?.documents||[]).map(doc=>`<div class="resource-row"><span class="resource-icon">Σ</span><div><strong>${safe(doc.name)}</strong><small>SHA-256 ${safe(doc.sha256)}</small></div></div>`).join('')||'<p>No documents were present at build time.</p>'}<div class="section-heading"><div><div class="section-index">RETRIEVAL</div><h2>Passages.</h2></div></div>${(details.rag?.hits||[]).map(hit=>`<div class="hit"><h3>${safe(hit.source)}</h3><code>[${safe(hit.citation)}] · BM25 ${Number(hit.score).toFixed(3)}</code><p>${safe(hit.text)}</p></div>`).join('')||empty('No passages selected','The build had no matching source passages at creation time.')}</div>`;
  if (tab==='skills') panel.innerHTML=`<div class="card"><div class="kicker">ACTIVE RESEARCH METHODS</div><h2>Skills available in chat.</h2><p>The factory routes the research question to these methodological guides. A literature request automatically applies the relevant subset.</p><div class="pill-list">${(details.chat_skills||[]).map(id=>`<span class="pill">${safe(id)}</span>`).join('')||'<p>No runtime skills are available.</p>'}</div><div class="section-heading"><div><div class="section-index">BUILD SNAPSHOT</div><h2>Original selection.</h2></div></div><div class="pill-list">${details.skills.map(id=>`<span class="pill">${safe(id)}</span>`).join('')||'<p>No skills were selected at build time.</p>'}</div></div>`;
  if (tab==='mcp') panel.innerHTML=`<div class="card"><div class="kicker">RUNTIME APPROVALS</div><h2>MCP tools.</h2><p>New builds persist these read-only tools in the build contract. Older agents inherit the same bounded factory runtime for chat.</p><div class="pill-list">${(details.chat_tools||[]).map(tool=>`<span class="pill">${safe(tool)}</span>`).join('')}</div><pre class="json-view">${safe(JSON.stringify({build_selection:details.mcp,effective_chat_tools:details.chat_tools,runtime:details.runtime},null,2))}</pre></div>`;
  if (tab==='memory') {
    panel.innerHTML=`<div class="card"><div class="kicker">BUILD-TIME PROJECT MEMORY</div><h2>What this agent knew.</h2><p>These entries were included when the agent was planned. Later notes belong to the evolving project journal.</p>${(details.rag?.wiki_entries||[]).map(entry=>`<article class="wiki-entry"><div class="kicker">${safe(entry.kind).toUpperCase()} / ${date(entry.created)}</div><h3>${safe(entry.title)}</h3><p>${safe(entry.content)}</p></article>`).join('')||empty('No memory at build time','Add notes in the project wiki before the next build.')}<div class="section-heading"><div><div class="section-index">EVOLUTION</div><h2>Linked journal.</h2></div></div><div id="agent-memory">Loading…</div><button class="secondary-button" data-project="${projectId}" data-project-tab="wiki">OPEN PROJECT WIKI ↗</button></div>`;
    api(`/projects/${projectId}/wiki`).then(entries=>{
      if(!$('#agent-memory'))return;
      const linked=entries.filter(entry=>entry.agent_id===jobId);
      $('#agent-memory').innerHTML=linked.map(entry=>`<article class="wiki-entry"><div class="kicker">${safe(entry.kind).toUpperCase()} / ${date(entry.created)}</div><h3>${safe(entry.title)}</h3><p>${safe(entry.content)}</p></article>`).join('')||empty('No linked entries yet','Record this agent’s next step in the project wiki.');
    }).catch(error=>toast(error.message));
  }
  if(tab==='chat') requestAnimationFrame(()=>{const history=$('#agent-chat-history');if(history)history.scrollTop=history.scrollHeight;});
  if (tab==='protocol') panel.innerHTML=`<div class="card"><div class="kicker">RESEARCH CONTRACT</div><h2>Protocol & measures.</h2><pre class="json-view">${safe(JSON.stringify(details.protocol,null,2))}</pre></div>`;
}

async function loadCode(path,jobId) {
  try {
    const file = await api(`/projects/${state.project.id}/file?job_id=${jobId}&path=${encodeURIComponent(path)}`);
    $('#code-label').textContent=file.path;
    $('#code-content').textContent=file.content;
    document.querySelectorAll('[data-code-path]').forEach(button=>button.classList.toggle('active',button.dataset.codePath===path));
  } catch(error) { toast(error.message); }
}

async function loadWiki() {
  const entries = await api(`/projects/${state.project.id}/wiki`);
  const target=$('#wiki-entries');
  if(!target) return;
  target.innerHTML=entries.map(entry=>`<article class="wiki-entry"><div class="kicker">${safe(entry.kind).toUpperCase()} / ${date(entry.created)}</div><h3>${safe(entry.title)}</h3><p>${safe(entry.content)}</p>${entry.agent_id?`<button class="text-button" data-agent="${safe(entry.agent_id)}">RELATED AGENT ↗</button>`:''}</article>`).join('')||empty('The journal is empty','Write a note or add a source to start the chronology.');
}

function attachDrop() {
  const drop=$('#dropzone');
  drop?.addEventListener('dragover',event=>{event.preventDefault();drop.classList.add('drag');});
  drop?.addEventListener('dragleave',()=>drop.classList.remove('drag'));
  drop?.addEventListener('drop',event=>{event.preventDefault();drop.classList.remove('drag');uploadSources(event.dataTransfer.files);});
}

async function uploadSources(files) {
  if(!files?.length) return;
  try {
    for(const file of files){const data=new FormData();data.append('file',file);await api(`/projects/${state.project.id}/documents`,{method:'POST',body:data});}
    toast(`${files.length} source file(s) processed.`);
    await openProject(state.project.id,'sources');
  } catch(error) {toast(error.message);}
}

async function startJob(kind,payload) {
  const projectId=state.project.id;
  const result=await api(`/projects/${projectId}/${kind}`,{method:'POST',body:JSON.stringify(payload)});
  toast('Operation started. Progress will appear above the conversation.');
  await openProject(projectId,kind==='skills/select'?'skills':'agents');
  const id=result.job_id;
  for(let attempt=0;attempt<240;attempt++){
    await new Promise(resolve=>setTimeout(resolve,1500));
    const job=await api('/jobs/'+id);
    if(state.project?.id===projectId&&state.tab==='agents'){
      const progress=$('#operation-progress');
      if(progress&&['queued','running'].includes(job.status)){
        progress.hidden=false;
        progress.className='operation-progress';
        progress.innerHTML=`<span class="working-spinner" aria-hidden="true"></span><div><strong>${safe(({build:'Agent build',chat:'Factory reply',skills:'Skill selection'}[job.kind]||job.kind)+' · '+(statuses[job.status]||job.status))}</strong><small>${safe(job.progress||'Working…')}</small></div>`;
      }
    }
    if(!['queued','running'].includes(job.status)){
      if(state.project?.id===projectId) await openProject(projectId,state.tab==='skills'&&kind==='skills/select'?'skills':'agents');
      if(job.status==='passed')toast(kind==='build'?'Research agent created. Open it from Your research agents.':'AI reply received and added to the conversation.');
      else toast(job.error || `Operation ${job.status}. No AI reply was produced.`);
      return;
    }
  }
  if(state.project?.id===projectId)await openProject(projectId,'agents');
  toast('The operation is still running. Its current stage is shown above the chat.');
}

async function sendAgentMessage(form) {
  const projectId=state.project.id, agentId=state.agent.job.id;
  const payload=selectedModelFields(Object.fromEntries(new FormData(form)));
  const submit=form.querySelector('button[type="submit"]');
  if(submit)submit.disabled=true;
  try {
    const started=await api(`/projects/${projectId}/agents/${agentId}/chat`,{
      method:'POST',body:JSON.stringify(payload)
    });
    const progress=$('#agent-chat-progress');
    if(progress){progress.hidden=false;progress.className='operation-progress';progress.innerHTML='<span class="working-spinner" aria-hidden="true"></span><div><strong>Agent reply · RUNNING</strong><small>Preparing evidence and instructions…</small></div>';}
    if(submit)submit.disabled=true;
    for(let attempt=0;attempt<240;attempt++){
      await new Promise(resolve=>setTimeout(resolve,1000));
      const job=await api('/jobs/'+started.job_id);
      if(['queued','running'].includes(job.status)){
        if(progress)progress.innerHTML=`<span class="working-spinner" aria-hidden="true"></span><div><strong>Agent reply · ${safe(statuses[job.status]||job.status)}</strong><small>${safe(job.progress||'The agent is preparing a response…')}</small></div>`;
        continue;
      }
      if(job.status!=='passed')throw new Error(job.error||'The agent could not complete this reply.');
      const details=await api(`/projects/${projectId}/agents/${agentId}`);
      if(state.agent?.job.id===agentId){state.agent=details;renderAgentTab('chat');}
      toast(`AI reply received · ${money(job.result?.costs?.reported_cost_usd)} reported.`);
      return;
    }
    toast('This reply is still running. Check the project activity log.');
  } catch(error) {
    try {
      const details=await api(`/projects/${projectId}/agents/${agentId}`);
      if(state.agent?.job.id===agentId){state.agent=details;renderAgentTab('chat');}
    } catch{}
    const progress=$('#agent-chat-progress');
    if(progress){progress.hidden=false;progress.className='notice warn';progress.textContent=`No AI reply was produced. ${error.message} Your message is saved above; you can retry after the current operation clears.`;}
    toast(error.message);
  }
  finally {if(submit?.isConnected)submit.disabled=false;}
}

async function boot() {
  try {
    state.session=await api('/session');
    state.token=state.session.token;
    [state.skills,state.harness,state.integrations]=await Promise.all([api('/skills'),api('/harness'),api('/integrations')]);
    await refreshProjects();
    const hash=location.hash.slice(1).split('/');
    if(hash[0]==='agent'&&hash[1]&&hash[2]) await showAgent(hash[1],hash[2]);
    else if(hash[0]==='project'&&hash[1]) await openProject(hash[1],hash[2]||'agents');
    else renderHome();
    if(!state.session.has_key)setTimeout(openSetup,120);
  } catch(error) {
    $('#main').innerHTML=`<div class="card"><h2>Workspace unavailable.</h2><p>${safe(error.message)}</p><button class="secondary-button" data-action="reload">RETRY</button></div>`;
  }
}

document.addEventListener('click',async event=>{
  const button=event.target.closest('button');
  if(!button) return;
  try {
    if(button.dataset.deleteJob){
      const jobId=button.dataset.deleteJob;
      if(!window.confirm('Delete this agent or operation and its stored build files? This cannot be undone.'))return;
      await api(`/projects/${state.project.id}/jobs/${jobId}`,{method:'DELETE'});
      toast('Agent or operation deleted.');
      await refreshProjects();await openProject(state.project.id,'agents');return;
    }
    if(button.dataset.removeProvider){
      await api(`/integrations/providers/${button.dataset.removeProvider}`,{method:'DELETE'});
      await refreshConnections();renderSetup();toast('OFF');return;
    }
    if(button.dataset.view){if(button.dataset.view==='home'){await refreshProjects();renderHome();}if(button.dataset.view==='agents')await renderAllAgents();if(button.dataset.view==='library')renderLibrary();if(button.dataset.view==='mcps')await renderMcps();return;}
    if(button.dataset.project){await openProject(button.dataset.project,button.dataset.projectTab||'overview');return;}
    if(button.dataset.allAgent){const [projectId,jobId]=button.dataset.allAgent.split('|');await showAgent(projectId,jobId);return;}
    if(button.dataset.agent){await showAgent(state.project.id,button.dataset.agent);return;}
    if(button.dataset.tab){state.tab=button.dataset.tab;renderProject();location.hash='#project/'+state.project.id+'/'+state.tab;return;}
    if(button.dataset.agentTab){renderAgentTab(button.dataset.agentTab);return;}
    if(button.dataset.codePath){await loadCode(button.dataset.codePath,state.agent.job.id);return;}
    if(button.dataset.skillDetail){const detail=await api('/skills/'+button.dataset.skillDetail);showDetail(button.dataset.skillDetail,detail.content);return;}
    if(button.dataset.job){showDetail('OPERATION RECORD',await api('/jobs/'+button.dataset.job));return;}
    const action=button.dataset.action;
    if(action==='setup')openSetup();
    if(action==='new-project')$('#project-dialog').showModal();
    if(action==='close-dialog'){if(button.closest('#setup-dialog'))mountSetupScene(null);button.closest('dialog').close();}
    if(action==='disconnect-obsidian'){
      await api('/integrations/obsidian',{method:'DELETE'});await refreshConnections();renderSetup();toast('OFF');return;
    }
    if(action==='sync-obsidian'){
      const result=await api(`/projects/${state.project.id}/obsidian/sync`,{method:'POST'});
      await openProject(state.project.id,'wiki');toast(`SYNC ${result.imported}↑ ${result.exported}↓`);return;
    }
    if(action==='refresh-project')await openProject(state.project.id,state.tab);
    if(action==='delete-project'){
      const projectId=state.project.id;
      if(!window.confirm(`Delete “${state.project.name}” and all of its documents, agents and memory? This cannot be undone.`))return;
      await api(`/projects/${projectId}`,{method:'DELETE'});
      state.project=null;state.agent=null;location.hash='';await refreshProjects();renderHome();toast('Project deleted.');return;
    }
    if(action==='reload')await boot();
    if(action==='suggest-skills')await startJob('skills/select',{backend:'configured'});
    if(action==='jev-skills')await startJob('skills/select',{backend:'jev'});
    if(action==='save-skills'){await api(`/projects/${state.project.id}/skills`,{method:'PUT',body:JSON.stringify(state.project.skills)});toast('Skill selection saved.');}
    if(action==='evaluation-history'){$('#evaluation-output').hidden=false;$('#evaluation-output').textContent=JSON.stringify(await api(`/projects/${state.project.id}/evaluations`),null,2);}
  } catch(error) {toast(error.message);}
});

function showDetail(title,content) {
  $('#detail-title').textContent=title;
  const body=$('#detail-body');
  body.innerHTML='';
  const pre=document.createElement('pre');
  pre.textContent=typeof content==='string'?content:JSON.stringify(content,null,2);
  body.append(pre);
  $('#detail-dialog').showModal();
}

document.addEventListener('input',event=>{
  if(event.target.id==='skill-filter')renderSkillCards(event.target.value);
});
document.addEventListener('change',event=>{
  if(event.target.id==='source-files')uploadSources(event.target.files);
  if(event.target.dataset.skill){
    const selected=new Set(state.project.skills);
    if(event.target.checked)selected.add(event.target.dataset.skill);
    else selected.delete(event.target.dataset.skill);
    if(selected.size>8){event.target.checked=false;toast('Choose up to eight skills.');return;}
    state.project.skills=[...selected];
  }
});

document.addEventListener('submit',async event=>{
  event.preventDefault();
  const form=event.target;
  const submit=form.querySelector('[type=submit],button:not([type])');
  if(submit)submit.disabled=true;
  try {
    const data=Object.fromEntries(new FormData(form));
    if(form.dataset.providerForm){
      await api(`/integrations/providers/${form.dataset.providerForm}`,{method:'PUT',body:JSON.stringify({...data,persist:true})});
      form.reset();await refreshConnections();renderSetup();toast('CONNECTED');return;
    }
    if(form.id==='obsidian-form'){
      await api('/integrations/obsidian',{method:'PUT',body:JSON.stringify(data)});
      await refreshConnections();renderSetup();toast('LINKED');return;
    }
    if(form.id==='new-project-form'){
      const project=await api('/projects',{method:'POST',body:JSON.stringify(data)});
      $('#project-dialog').close();form.reset();await refreshProjects();await openProject(project.id,'agents');
    }
    if(form.id==='rag-form'){
      const result=await api(`/projects/${state.project.id}/search`,{method:'POST',body:JSON.stringify(data)});
      $('#rag-results').innerHTML=result.hits.map(hit=>`<article class="hit"><h3>${safe(hit.source)}${hit.page?' · p. '+hit.page:''}</h3><code>[${safe(hit.citation)}] · BM25 ${hit.score.toFixed(3)}</code><p>${safe(hit.text)}</p></article>`).join('')||empty('No matching passages','Try another query or add more sources.');
    }
    if(form.id==='web-form'){
      const result=await api(`/projects/${state.project.id}/web-search`,{method:'POST',body:JSON.stringify(data)});
      $('#web-results').innerHTML=result.results.map(paper=>`<article class="hit"><h3>${safe(paper.title)}</h3><p>${safe(paper.summary||'No abstract available.')}</p>${/^https:\/\//.test(paper.url)?`<a href="${safe(paper.url)}" target="_blank" rel="noopener noreferrer">OPEN PUBLICATION ↗</a>`:''}</article>`).join('')||empty('No results','Try more specific search terms.');
    }
    if(form.id==='build-form'){
      selectedModelFields(data);
      const turns=(state.project.messages||[]).filter(message=>message.role==='user').slice(-5).map(message=>message.content.trim()).filter(Boolean);
      const conversation=turns.length?`\n\nFACTORY CHAT — ADDITIONAL USER REQUIREMENTS:\n${turns.map((turn,index)=>`${index+1}. ${turn}`).join('\n')}`:'';
      await startJob('build',{...data,question:(data.question+conversation).slice(0,10000),mode:'live',backend:'configured',repairs:Number(data.repairs)});
    }
    if(form.id==='chat-form')await startJob('chat',selectedModelFields(data));
    if(form.id==='agent-chat-form')await sendAgentMessage(form);
    if(form.id==='wiki-form'){
      await api(`/projects/${state.project.id}/wiki`,{method:'POST',body:JSON.stringify(data)});
      form.reset();await loadWiki();toast('Research note saved.');
    }
    if(form.id==='evaluation-form'){
      const upload=new FormData(form);const jobId=upload.get('job_id');upload.delete('job_id');
      const report=await api(`/projects/${state.project.id}/evaluations?job_id=${encodeURIComponent(jobId)}`,{method:'POST',body:upload});
      $('#evaluation-output').hidden=false;$('#evaluation-output').textContent=JSON.stringify(report,null,2);toast('Evaluation archived.');
    }
  } catch(error) {
    if(/already running|still running|operation .* in progress/i.test(error.message)&&state.project?.id){
      const projectId=state.project.id;
      try{await openProject(projectId,'agents');}catch{}
    }
    toast(error.message);
  } finally {if(submit)submit.disabled=false;}
});

boot();
