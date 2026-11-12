'use strict';
const $=id=>document.getElementById(id);
const state={instance:null,view:null,selected:new Set(),run:null,attempt:null,busy:false,queueKey:null,settingsVersion:null,profileCandidate:null,profileDirty:false,answerKey:null,answerDrafts:new Map()};
state.activity={period:'7d',offset:0,limit:25};state.activityRequest=0;
state.jobSort={key:'added',direction:'desc'};
function el(tag,text,cls,children){const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;if(Array.isArray(children)){for(const c of children)if(c)n.append(c);}return n;}
function badge(value){const n=el('span',value??'Unknown','badge');n.dataset.state=value??'unknown';return n;}
function notice(message,error=false){$('notice').textContent=message;$('notice').classList.toggle('error',error);}
function stamp(value){if(!value)return '—';const d=new Date(value);if(Number.isNaN(d.getTime()))return 'Unknown';return new Intl.DateTimeFormat(undefined,{dateStyle:'short',timeStyle:'medium',timeZone:state.view?.settings?.values?.timezone||'UTC'}).format(d);}
function duration(n){return typeof n==='number'?`${n.toFixed(1)} s`:'Unknown';}
async function request(path,body,method='POST'){
 const headers={};if(body!==undefined)headers['Content-Type']='application/json';if(state.instance)headers['X-JobBot-Instance']=state.instance;
 const options={method,headers,credentials:'same-origin',body:body===undefined?undefined:JSON.stringify(body)};
 let r=await fetch(path,options);
 if(r.status===401&&path!='/login'){
  const opened=await fetch('/',{credentials:'same-origin',cache:'no-store'});
  if(opened.ok)r=await fetch(path,options);
 }
 const data=r.status===204?{}:await r.json();
 if(!r.ok){if(r.status===401&&path!='/login')showLogin();throw new Error(data.error||`HTTP ${r.status}`);}return data;
}
const api=(operation,payload={})=>request('/v1/'+operation,payload);
function newRequestId(){
 const source=globalThis.crypto;
 if(typeof source.randomUUID==='function')return source.randomUUID();
 // LAN HTTP pages retain getRandomValues even when randomUUID is unavailable.
 const bytes=source.getRandomValues(new Uint8Array(16));
 bytes[6]=(bytes[6]&0x0f)|0x40;bytes[8]=(bytes[8]&0x3f)|0x80;
 const hex=Array.from(bytes,value=>value.toString(16).padStart(2,'0')).join('');
 return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
const LEGACY_ALLOWED=new Set(['identity','summary','years_experience','target_roles','industries','skills','leadership_scope','work_authorization','work_preferences','dealbreakers','eeo_information','standard_answers','experience','education','certifications','projects','languages','links','resume','profile_answer_sources']);
const LEGACY_EXCLUDED=new Set(['accounts','cover_letter','login','greenhouse','automation_preferences','application_answer_policy']);
const LEGACY_IDENTITY=new Set(['full_name','first_name','middle_name','last_name','preferred_name','email','phone','country code','address','location','linkedin','website','github']);
function sanitizeLegacyClient(data){
 const clean={},skipped=[];
 for(const [k,v] of Object.entries(data||{})){
  if(LEGACY_EXCLUDED.has(k)||!LEGACY_ALLOWED.has(k)){skipped.push(k);continue;}
  if(k==='identity'&&typeof v==='object'&&v!==null){
   clean.identity={};for(const [ik,iv] of Object.entries(v)){if(LEGACY_IDENTITY.has(ik))clean.identity[ik]=iv;else skipped.push('identity.'+ik);}
  }else if(k==='resume'&&typeof v==='object'&&v!==null){
   clean.resume={};if(v.path)clean.resume.path=v.path;if(v.text)skipped.push('resume.text');
   for(const rk of Object.keys(v)){if(rk!=='path'&&rk!=='text')skipped.push('resume.'+rk);}
  }else{clean[k]=v;}
 }
 return {clean,skipped:skipped.sort()};
}
function showLogin(){state.profileEditor=null;state.profileHash=null;state.profilePromotions=new Map();for(const id of ['profile-question-sections','profile-suggestions','profile-file-sync','profile-json-error'])$(id)?.replaceChildren();resetActivity();if($('portal-password-dialog')?.open)$('portal-password-dialog').close();$('portal-password-form')?.reset();if($('library-dialog')?.open)$('library-dialog').close();state.libraryEditing=null;state.answerPage=0;state.learnedPage=0;state.answerSelections={};state.answerMode='inbox';state.learnedMode='current';state.answerHistory=null;state.answerHistoryRequest=null;state.answerReceipt=null;state.learnedKey=null;state.answerDrafts.clear();state.answerKey=null;for(const id of ['answer-groups','answer-list','answer-pagination','learned-list','learned-detail','learned-pagination','answer-receipt'])$(id)?.replaceChildren();if($('answer-receipt'))$('answer-receipt').hidden=true;if($('answer-count'))$('answer-count').textContent='';state.instance=null;state.view=null;state.run=null;state.attempt=null;state.queueKey=null;state.settingsVersion=null;state.profileCandidate=null;state.selected.clear();for(const id of ['queue-rows','account-rows','history','attempts','events','health','instance','run-owner','focused-context','target-list','extension-list','lesson-list','helper-list','asset-list','assessment-list','profile-import-skipped'])$(id)?.replaceChildren();for(const f of document.querySelectorAll('form'))f.reset();$('console').hidden=true;$('login-panel').hidden=false;$('refresh').hidden=true;$('mode').textContent='Disconnected';if($('profile-hash'))$('profile-hash').textContent='';if($('profile-id'))$('profile-id').textContent='';if($('profile-person-key'))$('profile-person-key').textContent='';if($('profile-resume'))$('profile-resume').textContent='None';if($('main-resume-filename'))$('main-resume-filename').textContent='None registered';}
function showConsole(){state.profileDirty=false;$('console').hidden=false;$('login-panel').hidden=true;$('refresh').hidden=false;}
function choice(id,items,value){const select=$(id),before=value??select.value;select.replaceChildren();for(const [v,label]of items){const option=el('option',label);option.value=v;select.append(option);}if(items.some(x=>x[0]===before))select.value=before;}
function submitted(job){return ['applied','already_applied'].includes(job.status);}
function unfinished(job){return !submitted(job)&&job.disposition!=='canceled'&&!job.archived;}
function latestDispatch(v,job){return v.dispatch_queue?.latest_by_job?.[job.id]||v.dispatch_queue?.items?.find(q=>q.job_id===job.id);}
function postingMetadata(job){let metadata=job.metadata||{};try{if(job.metadata_json)metadata=JSON.parse(job.metadata_json);}catch{}return metadata;}
function discoverySkipped(job){return job.eligibility==='held'&&String(postingMetadata(job).verdict||'').trim().toLowerCase()==='skip';}
function postingCountry(job){const metadata=postingMetadata(job);const country=metadata.country||(/(?:, |\()United States\)?$/.test(metadata.location||'')?'US':'');if(!country)return 'Unavailable';try{return /^[A-Z]{2}$/.test(country)?new Intl.DisplayNames(['en'],{type:'region'}).of(country):country;}catch{return country;}}
function postingDate(job){const value=postingMetadata(job).posted_at;if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}(?:$|T)/.test(value))return 'Unavailable';const day=value.slice(0,10);const parsed=new Date(day+'T00:00:00Z');return !Number.isNaN(parsed.getTime())&&parsed.toISOString().slice(0,10)===day?day:'Unavailable';}
function queueJobStatus(job,queued,local){
 if(job.disposition==='canceled')return 'Canceled';
 if(submitted(job))return displayStatus(job.status);
 if(queued?.waiting_for_retry)return 'Retry scheduled';
 if(queued?.state==='queued'&&queued.immediate_requested_at)return 'Apply now requested';
 if(queued?.automatic_limit_reached)return 'Needs attention';
 if(queued?.state==='queued')return 'Queued';
 if(queued?.state==='dispatched')return 'In progress';
 if(discoverySkipped(job))return 'Not selected for application';
 const outcome=queued?.outcome==='canceled'?job.status:queued?.outcome||job.status;
 return local&&outcome==='queued'?(job.eligibility==='excluded'?'Excluded':job.intervention_reason?'Needs attention':'Awaiting automatic pickup'):displayStatus(outcome);
}
function visibleJobs(v){
 const filter=$('job-filter').value,query=$('job-search').value.trim().toLocaleLowerCase();
 const source=$('job-source-filter').value,country=$('job-country-filter').value,assessment=$('job-assessment-filter').value;
 const from=$('job-added-from').value,to=$('job-added-to').value;
 return v.jobs.filter(job=>{
  if(query&&![job.seq_id==null?'':'#'+job.seq_id,job.company,job.title,job.url,...(job.sources||[]).flatMap(s=>[sourceLabel(s.source_type),s.source_id])].filter(Boolean).join(' ').toLocaleLowerCase().includes(query))return false;
  if(source&&!(job.sources||[]).some(s=>s.source_type===source))return false;
  if(country&&postingCountry(job)!==country)return false;
  if(assessment&&(job.assessment?.recommendation||'Unassessed')!==assessment)return false;
  if(from||to){const day=addedDay(job.created_at);if(!day||(from&&day<from)||(to&&day>to))return false;}
  if(filter==='canceled')return job.disposition==='canceled';
  if(filter==='submitted')return submitted(job);
  if(filter==='active')return unfinished(job);
  if(filter==='attention'){
   const queued=latestDispatch(v,job);
   const problems=['blocked','failed','interrupted','submission_unknown','ready_for_review','skipped'];
   return unfinished(job)&&(problems.includes(job.status)||!!job.failure_reason||(queued?.state==='finished'&&problems.includes(queued.outcome)));
  }
  return true;
 }).sort((a,b)=>{
  const av=jobSortValue(v,a),bv=jobSortValue(v,b);
  if(av==null||bv==null)return av==null?(bv==null?0:1):-1;
  const order=typeof av==='number'&&typeof bv==='number'?av-bv:String(av).localeCompare(String(bv),undefined,{numeric:true,sensitivity:'base'});
  return state.jobSort.direction==='asc'?order:-order;
 });
}
function addedDay(value){
 const date=new Date(value);if(!value||Number.isNaN(date.getTime()))return null;
 const parts=new Intl.DateTimeFormat('en-US',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:state.view?.settings?.values?.timezone||'UTC'}).formatToParts(date);
 const part=type=>parts.find(p=>p.type===type).value;return `${part('year')}-${part('month')}-${part('day')}`;
}
function jobSortValue(v,job){
 const time=value=>value&&Number.isFinite(Date.parse(value))?Date.parse(value):null;
 switch(state.jobSort.key){
  case 'sequence':return Number.isFinite(job.seq_id)?job.seq_id:null;
  case 'company':return [job.company,job.title].filter(Boolean).join(' ')||null;
  case 'status':return queueJobStatus(job,latestDispatch(v,job),!!v.local_runtime?.workspaces?.length);
  case 'assessment':return job.assessment?.recommendation||null;
  case 'country':return postingCountry(job)==='Unavailable'?null:postingCountry(job);
  case 'posted':return time(postingDate(job));
  case 'source':return job.sources?.length?sourceLabel(job.sources[0].source_type):null;
  case 'reference':return job.sources?.map(s=>s.source_id).filter(Boolean).join(' ')||null;
  case 'disposition':return time(job.last_disposition?.at);
  case 'duration':return submitted(job)&&Number.isFinite(job.application_timing?.elapsed_seconds)?job.application_timing.elapsed_seconds:null;
  default:return time(job.created_at);
 }
}
function renderJobFilters(v){
 const options=(id,values,label,display=x=>x)=>{
  const select=$(id),before=select.value,unique=[...new Set(values.filter(Boolean))].sort((a,b)=>display(a).localeCompare(display(b)));
  if(before&&!unique.includes(before))unique.push(before);
  const items=[['',label],...unique.map(x=>[x,display(x)])],key=JSON.stringify(items);
  if(select.dataset.options!==key){choice(id,items,before);select.dataset.options=key;}
 };
 options('job-source-filter',v.jobs.flatMap(j=>(j.sources||[]).map(s=>s.source_type)),'All sources',sourceLabel);
 options('job-country-filter',v.jobs.map(postingCountry),'All countries');
 options('job-assessment-filter',v.jobs.map(j=>j.assessment?.recommendation||'Unassessed'),'All assessments');
 for(const button of document.querySelectorAll('[data-job-sort]')){
  button.dataset.label??=button.textContent;
  const active=button.dataset.jobSort===state.jobSort.key;
  button.textContent=button.dataset.label+(active?(state.jobSort.direction==='asc'?' ↑':' ↓'):' ↕');
  button.closest('th').setAttribute('aria-sort',active?(state.jobSort.direction==='asc'?'ascending':'descending'):'none');
 }
 const sortButton=document.querySelector(`[data-job-sort="${state.jobSort.key}"]`);
 $('queue-selection-order').textContent=`Selected jobs queue in table order: ${sortButton.dataset.label}, ${state.jobSort.direction==='asc'?'ascending':'descending'}. Available slots take earlier manual requests first, ahead of automatic pickups.`;
}
function selection(){
 const selected=(state.view?.jobs||[]).filter(j=>state.selected.has(j.id));
 const cancelable=selected.filter(unfinished),restorable=selected.filter(j=>j.disposition==='canceled');
 $('selection').textContent=state.selected.size?`${state.selected.size} job${state.selected.size===1?'':'s'} selected`:'No jobs selected';
 $('start-application-btn').disabled=!!state.queueSubmitting||!cancelable.length||cancelable.length!==selected.length;
 $('queue-selected-jobs').disabled=$('start-application-btn').disabled;
 $('cancel-selected').disabled=!cancelable.length;
 $('restore-selected').disabled=!restorable.length;
 $('clear-selection').disabled=!state.selected.size;
 const visible=state.view?visibleJobs(state.view):[];
 $('select-unfinished').disabled=!visible.some(unfinished);
 $('select-visible').disabled=!visible.some(j=>j.disposition==='canceled');
 const canceledView=$('job-filter').value==='canceled';
 const selectable=visible.filter(canceledView?j=>j.disposition==='canceled':unfinished);
 const count=selectable.filter(j=>state.selected.has(j.id)).length,all=$('select-all-jobs');
 all.disabled=!selectable.length;
 all.checked=!!selectable.length&&count===selectable.length;
 all.indeterminate=count>0&&count<selectable.length;
 all.title=canceledView?'Select all canceled jobs shown by the current filters':'Select all unfinished jobs shown by the current filters';
 all.setAttribute('aria-label',canceledView?'Select all canceled jobs shown':'Select all unfinished jobs shown');
}
function link(url,label){try{const u=new URL(url);if(!['http:','https:'].includes(u.protocol))return el('span',label);const a=el('a',label);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a;}catch{return el('span',label);}}
function postingLabel(job){
 const known=[job.company,job.title||job.job_title].filter(Boolean);if(known.length)return known.join(' · ');
 let metadata=job.metadata||{};try{if(job.metadata_json||job.job_metadata_json)metadata=JSON.parse(job.metadata_json||job.job_metadata_json);}catch{}
 return metadata.label_discovery?.status==='unavailable'?'Company and role unavailable':'Identifying company and role';
}
function postingHeading(job){const n=el('div',undefined,'posting-heading');n.append(el('strong',postingLabel(job)));
 const url=job.url||job.job_url;if(url){let hostname='View job posting';try{hostname=new URL(url).hostname;}catch{}n.append(link(url,hostname));}return n;}
const progressExpansion=new Map();
function rememberProgress(root){for(const node of root.querySelectorAll('details[data-progress-key]'))progressExpansion.set(node.dataset.progressKey,node.open);}
function progressDetails(key,title,open=false,cls='progress-stage'){
 const n=el('details',undefined,cls);n.dataset.progressKey=key;n.open=progressExpansion.has(key)?progressExpansion.get(key):open;n.append(el('summary',title));return n;
}
function renderProgress(progress,key){
 const root=el('div',undefined,'application-progress');
 const states={in_progress:'In progress',completed:'Completed',recovering:'Recovering',awaiting_input:'Awaiting your input',unsuccessful:'Unsuccessful'};
 if(!progress?.details_recorded)root.append(el('p','Details not recorded.','progress-empty'));
 for(const stage of progress?.stages||[]){
  const section=progressDetails(key+':stage:'+stage.id,stage.title,stage.state!=='completed');
  section.querySelector('summary').append(badge(states[stage.state]||'In progress'));
  for(const task of stage.tasks||[]){
   const row=el('div',undefined,'progress-task');row.append(el('span',task.title),badge(states[task.state]||'In progress'));
   if(typeof task.elapsed_seconds==='number')row.append(el('small',`Elapsed ${duration(task.elapsed_seconds)}${task.wait_seconds?' · Waiting for your input '+duration(task.wait_seconds):''}${typeof task.action_seconds==='number'?' · Recorded actions '+duration(task.action_seconds):''}`));
   section.append(row);
  }
  if(stage.omitted_completed_tasks)section.append(el('small',`${stage.omitted_completed_tasks} earlier completed tasks in the full application history.`));root.append(section);
 }
 const debug=progressDetails(key+':debug','Debug details',false,'debug-details');
 for(const event of progress?.debug||[])debug.append(el('pre',JSON.stringify(event,null,2)));
 root.append(debug);return root;
}
function sourceLabel(value){return ({manual:'Manual',legacy_cli:'Legacy CLI',
 'job_harvester:google_jobs':'Job Harvester / Google Jobs','job_harvester:linkedin':'Job Harvester / LinkedIn',
 linkedin_alert_email:'LinkedIn alert email',employer_search:'Employer search'})[value]||value||'Unknown';}
function producerLabel(value){return ({dashboard:'Dashboard',queue_cli:'Queue CLI',legacy_cli:'Legacy CLI',managed_cli:'Managed CLI',
 application_runtime:'Application runtime',discovery_intake:'Discovery import',queue_worker:'Queue worker',
 hermes_scheduled_discovery:'Hermes scheduled discovery',hermes_manual_discovery:'Hermes manual discovery'})[value]||value||'Not recorded';}
function enqueueLabel(value){return ({discovery:'Discovery handoff',manual_enqueue:'Manual enqueue',api_request:'API request',
 manual_retry:'Manual retry',automatic_intake:'Automatic pickup',automatic_retry:'Automatic retry',
 automatic_restore:'Automatic pickup after restoration',answer_retry:'Retry after answer'})[value]||value||'Not recorded';}
function processDetails(parent,item){
 parent.append(el('small','Process: '+producerLabel(item.producer)));
 if(item.discovery_profile)parent.append(el('small','Profile: '+item.discovery_profile));
 if(item.discovery_run_id)parent.append(el('small','Discovery run: '+item.discovery_run_id));
}
function sourceCell(job,queued){
 const td=el('td'),sources=job.sources||[];
 td.append(el('span',sourceLabel(sources[0]?.source_type)));
 const firstObservation=sources[0]?.observations?.[0];
 td.append(el('small',firstObservation?'Seen by '+producerLabel(firstObservation.producer):'Discovery process: Not recorded'));
 const detail=progressDetails(job.id+':sources',`Origin details · ${sources.length} source${sources.length===1?'':'s'}`);
 for(const source of sources){
  const row=el('div');row.append(el('strong',sourceLabel(source.source_type)),
   el('small',`First recorded ${stamp(source.discovered_at)}`));
  if(source.original_url)row.append(link(source.original_url,'Discovery link'));
  if(!source.observations?.length)row.append(el('small','Discovery process: Not recorded'));
  for(const observation of source.observations||[]){
   const seen=el('div');processDetails(seen,observation);
   seen.append(el('small','Observed '+stamp(observation.recorded_at)));row.append(seen);
  }
  detail.append(row);
 }
 const hasHistory=!!job.queue_origins?.length;
 const entries=hasHistory?job.queue_origins:queued?[queued]:[];
 if(entries.length){
  td.append(el('small',(hasHistory?'First queued: ':'Latest queue entry: ')+enqueueLabel(entries[0].enqueue_origin)));
  detail.append(el('strong','Queue entry history'));
  for(const entry of entries){
   const row=el('div');row.append(el('span',enqueueLabel(entry.enqueue_origin)));
   processDetails(row,entry);row.append(el('small','Queued '+stamp(entry.created_at)));
   if(entry.request_id)row.append(el('small','Request: '+entry.request_id));detail.append(row);
  }
 }else detail.append(el('small','No queue entry recorded'));
 td.append(detail);return td;
}
function sourceReferenceCell(job){
 const td=el('td',undefined,'source-reference');
 if(!job.sources?.length)td.append(el('span','Not recorded'));
 for(const source of job.sources||[]){
  const row=el('div'),reference=source.source_id||'Reference unavailable';
  row.title=sourceLabel(source.source_type);
  row.append(source.original_url?link(source.original_url,reference):el('span',reference));td.append(row);
 }
 return td;
}
function applicationTimeCell(job){
 const td=el('td',undefined,'application-time'),timing=job.application_timing;
 if(!submitted(job)){td.textContent='—';return td;}
 if(!Number.isFinite(timing?.elapsed_seconds)||timing.elapsed_seconds<0){td.textContent='Not recorded';return td;}
 const seconds=Math.round(timing.elapsed_seconds),hours=Math.floor(seconds/3600),minutes=Math.floor(seconds%3600/60);
 td.textContent=(timing.uncertain_duration?'Approx. ':'')+(hours?`${hours}h ${minutes}m ${seconds%60}s`:minutes?`${minutes}m ${seconds%60}s`:`${seconds}s`);
 td.title=`Successful attempt: ${stamp(timing.started_at)} to ${stamp(timing.completed_at)}. Includes waits during this attempt; excludes earlier attempts and queue time.`;
 if(timing.uncertain_duration)td.title+=' Some timing evidence is incomplete.';
 return td;
}
function dispositionCell(job){
 const td=el('td'),last=job.last_disposition;
 if(!last){td.append(el('span','Not recorded'));return td;}
 const label=last.source==='operator'?(last.value==='active'?'Restored':'Canceled'):displayStatus(last.value);
 td.append(el('span',label),el('small',stamp(last.at)),el('small',({operator:'By you',application:'Application outcome',queue:'Queue outcome'})[last.source]||last.source));
 return td;
}
function renderOverview(v){
 const active=v.jobs.filter(unfinished), attention=active.filter(j=>{
  const q=latestDispatch(v,j);return ['blocked','failed','interrupted','submission_unknown','ready_for_review','skipped'].includes(j.status)||!!j.failure_reason||(q?.state==='finished'&&['blocked','failed','interrupted','submission_unknown','ready_for_review','skipped'].includes(q.outcome));
 });
 $('overview-active').textContent=active.length;$('overview-submitted').textContent=v.jobs.filter(submitted).length;$('overview-attention').textContent=attention.length;
 const q=v.dispatch_queue||{};
 $('overview-worker').textContent=q.automation_paused?'Paused':!q.worker_online?'Offline':q.enabled?'Automatic':'Manual';
 $('overview-running').textContent=`${q.counts?.dispatched||0} running · ${q.counts?.queued||0} queued`;
 for(const button of document.querySelectorAll('[data-overview-filter]'))button.setAttribute('aria-pressed',String(button.dataset.overviewFilter===$('job-filter').value));
}
function renderQueue(v){
 renderOverview(v);
 renderJobFilters(v);
 renderSessions(v);
 renderAnswers(v);
 renderDispatcher(v);
 const jobs=visibleJobs(v),visibleIds=new Set(jobs.map(j=>j.id));
 for(const id of state.selected)if(!visibleIds.has(id))state.selected.delete(id);
 const key=JSON.stringify([jobs,v.answer_queue,v.dispatch_queue?.items,v.dispatch_queue?.latest_by_job,[...state.selected],$('job-filter').value,state.jobSort]);if(key===state.queueKey){selection();return;}state.queueKey=key;
 rememberProgress($('queue-rows'));
 const canceledView=$('job-filter').value==='canceled';
 $('select-visible').hidden=!canceledView;$('select-unfinished').hidden=canceledView;
 $('restore-selected').hidden=!jobs.some(j=>j.disposition==='canceled');
 $('cancel-selected').hidden=canceledView;$('cancel-reason').closest('label').hidden=canceledView;
 $('queue-count').textContent=`${jobs.length} shown · ${v.jobs.length} total`;$('queue-rows').replaceChildren();
 for(const job of jobs){
  const tr=el('tr');tr.dataset.jobId=job.id;
  const check=el('input');check.type='checkbox';check.checked=state.selected.has(job.id);
  check.disabled=submitted(job)&&job.disposition!=='canceled';
  check.setAttribute('aria-label','Select '+postingLabel(job));
  check.onchange=()=>{if(check.checked)state.selected.add(job.id);else state.selected.delete(job.id);selection();};
  const cell=el('td');cell.append(el('span',job.seq_id==null?'—':'#'+job.seq_id,'job-sequence'),check);tr.append(cell);
  const title=el('td');title.append(postingHeading(job));
  const edit=el('button','Edit URL','edit-job-url');edit.type='button';edit.dataset.editJobUrl=job.id;
  edit.setAttribute('aria-label','Edit URL for '+postingLabel(job));edit.onclick=()=>editJobUrl(job);title.append(edit);tr.append(title);
  const queued=latestDispatch(v,job);
  const statusTd=el('td');statusTd.append(badge(queueJobStatus(job,queued,!!v.local_runtime?.workspaces?.length)));
  if(v.local_runtime?.workspaces?.length&&unfinished(job)&&!['queued','dispatched'].includes(queued?.state)){
   statusTd.append(el('small',queued?.automatic_limit_reached?'Six attempts ended without completion. Review the reason; Queue selected starts a new attempt series.':discoverySkipped(job)?'Discovery marked this job Skip. Review its match before explicitly choosing Queue selected.':queued?.state==='finished'?'The worker schedules recovery for interrupted or failed attempts. Review-only results and user stops stay here.':job.intervention_reason||'Active jobs enter the execution queue automatically.'));
  }
  if(queued?.attempt_number)statusTd.append(el('small',`Attempt ${queued.attempt_number} of ${v.dispatch_queue?.automatic_attempt_limit||3}`));
  if(queued?.waiting_for_retry)statusTd.append(el('small',`Retry at ${stamp(queued.next_attempt_at)}. Other ready jobs can run first.`));
  if(v.local_runtime?.workspaces?.length&&unfinished(job)){
   const apply=el('button',queued?.state==='dispatched'?'In progress':'Apply now','primary');
   apply.type='button';apply.dataset.applyNow=job.id;apply.disabled=queued?.state==='dispatched';
   apply.setAttribute('aria-label',apply.textContent+' · '+postingLabel(job));
   apply.onclick=()=>applyNow(job,apply);statusTd.append(apply);
   if(queued?.state==='queued'&&queued.immediate_requested_at)statusTd.append(el('small','Starts when the worker is free, ahead of automatic jobs.'));
  }
  if(job.disposition==='canceled')statusTd.append(el('small',job.disposition_reason||'Canceled by you'),el('small','Last outcome: '+displayStatus(job.status)));
  const unanswered=v.answer_queue?.groups.find(g=>g.job_id===job.id&&g.pending_count);
  if(unanswered&&job.disposition!=='canceled'){const review=el('button',`Answer ${unanswered.pending_count} question${unanswered.pending_count===1?'':'s'}`);review.onclick=()=>tab('answers');statusTd.append(review);}
  if(job.failure_reason||queued?.detail){const details=progressDetails(job.id+':outcome','Outcome details',false,'job-outcome');details.append(el('p','Reason: '+(job.failure_reason||queued.detail)));statusTd.append(details);}
  for(const match of job.duplicate_matches||[]){
   const dismissed=match.operator_state==='dismissed';
   const label=(dismissed?'Dismissed match':match.decision==='confirmed'?'Matching posting':'Possible duplicate')+` · #${match.other_seq_id??'?'}`;
   const details=progressDetails(job.id+':duplicate:'+match.id,label,false,'job-duplicate');
   details.append(el('p',match.evidence.join('. ')));
   const button=el('button',dismissed?'Reconsider match':'These are different jobs');button.type='button';
   button.onclick=async()=>{try{await api('set_duplicate_match_state',{match_id:match.id,state:dismissed?'automatic':'dismissed'});notice(dismissed?'Automatic matching restored.':'Match dismissed. You can queue this job if needed.');await refresh();}catch(err){notice(err.message,true);}};
   details.append(button);statusTd.append(details);
  }
  tr.append(statusTd);
  const assessment=job.assessment;tr.append(el('td',assessment?(assessment.recommendation||'Assessment available'):'Unassessed'));
  tr.append(el('td',postingCountry(job)),el('td',postingDate(job)));
  tr.append(sourceCell(job,queued),sourceReferenceCell(job),el('td',stamp(job.created_at)),dispositionCell(job),applicationTimeCell(job));
  $('queue-rows').append(tr);
 }
 if(!jobs.length){const tr=el('tr'),td=el('td',v.jobs.length?'No jobs match this view.':'No postings in this instance.');td.colSpan=11;tr.append(td);$('queue-rows').append(tr);}
 selection();
}
function renderSessions(v){
 const runtime=v.local_runtime||{sessions:[],workspaces:[]};
 if($('start-application-btn'))$('start-application-btn').textContent=runtime.workspaces.length?'Queue selected':'Start application';
 $('local-sessions-card').hidden=!runtime.workspaces.length&&!runtime.sessions.length;
 const historyScroll=$('session-history')?.scrollTop||0;
 rememberProgress($('local-sessions'));$('local-sessions').replaceChildren();
 const active=runtime.sessions.filter(s=>!s.ended_at);
 const past=runtime.sessions.filter(s=>s.ended_at);
 $('activity-count').textContent=active.length?`${active.length} in progress`:'No application running';
 const history=progressDetails('session-history',`Recent history · ${past.length} application${past.length===1?'':'s'}`,false,'session-history');history.id='session-history';
 if(!active.length)$('local-sessions').append(el('p','Current work will appear here. Open recent history to review earlier applications.','activity-empty'));
 for(const s of [...active,...past]){
  const job=v.jobs.find(j=>j.id===s.job_id)||{};
  const candidate=v.candidates.find(c=>c.id===s.identity_id)||{};
  const metadata=s.metadata||{},n=progressDetails(s.id+':application',postingLabel(job),false,'application-row');
  const summary=n.querySelector('summary');
  summary.append(badge(!s.ended_at&&s.host_alive===false&&s.state==='connected'?'Needs attention':displayStatus(s.state)));
  n.append(postingHeading(job));
  if(metadata.application_kind)n.append(badge(metadata.application_kind==='reattempt'?'Reattempt':'First attempt'));
  if(candidate.email)n.append(el('p',candidate.email));
  const progress=renderProgress(s.progress||{debug:s.steps||[]},s.id),debug=progress.querySelector('.debug-details');n.append(progress);
  debug.append(el('p',`Host ${s.host_alive?'running':'offline'} · Driver ${s.driver_recently_active?'recently active':'idle or disconnected'} · Writer ${s.writer_state}`));
  debug.append(el('p',`Executor: ${metadata.provider||'unknown'} / ${metadata.model||'unknown'} · effort ${metadata.reasoning_effort||'unknown'}`));
  n.append(el('small',`Requested ${stamp(s.requested_at)} · Connected ${stamp(s.connected_at)} · Ended ${stamp(s.ended_at)} · Total ${duration(s.elapsed_seconds)}`));
  const deadline=s.metadata?.application_deadline;
  if(deadline)n.append(el('small',deadline.expires_at?`Time limit: ${deadline.limit_seconds/60} minutes · Deadline ${stamp(deadline.expires_at)}`:'Application time limit: Off'));
  n.append(el('small',`Queue ${duration(s.queue_seconds)} · Browser startup ${duration(s.startup_seconds)} · Last verified progress ${stamp(s.last_verified_progress_at)}`));
  if(s.first_autofill_at)n.append(el('small',`First Autofill ${stamp(s.first_autofill_at)} · Ready to Autofill ${duration(s.ready_to_autofill_seconds)}`));
  if(s.reason)debug.append(el('p',s.reason,'job-reason'));
  debug.append(el('small',`Session ${s.id} · Attempt ${s.attempt_id||'not started'} · Config ${metadata.config_path||'unknown'}`,'mono'));
  if(s.run_id&&!s.ended_at){
   for(const command of ['pause','stop']){
    const button=el('button',command==='pause'?'Pause this application':'Stop this application');
    button.disabled=s.state==='paused'&&command==='pause';
    button.onclick=async()=>{try{await api('control',{run_id:s.run_id,command});await refresh();}catch(e){notice(e.message,true);}};
    n.append(button);
   }
  }
  (s.ended_at?history:$('local-sessions')).append(n);
 }
 if(past.length){$('local-sessions').append(history);history.scrollTop=historyScroll;}
}
function displayStatus(value){return ({connected:'In progress',preparing:'In progress',waiting:'In progress',running:'In progress',finishing:'In progress',capacity_wait:'Waiting to start',applied:'Applied',already_applied:'Already applied',ready_for_review:'Ready for review',submission_unknown:'Submission uncertain',blocked:'Needs attention',failed:'Needs attention',interrupted:'Interrupted',paused:'Paused',queued:'Queued',completed:'Completed',stopped:'Stopped',skipped:'Skipped'})[value]||value||'Not started';}
async function applyNow(job,button){
 if(button.disabled)return;
 button.disabled=true;
 try{
  const identity_id=$('candidate').value;
  const asset=(state.view.assets||[]).find(a=>a.id===$('queue-resume').value&&a.identity_id===identity_id&&a.kind==='resume'&&a.status==='available');
  if(!asset)throw Error('Choose a candidate with a registered resume.');
  const submission_mode=$('main-submission-mode').value;
  if(submission_mode!==state.view.settings.values.submission_mode)await api('configure',{changes:{submission_mode,mode:submission_mode==='submit'?'pilot':'development'},expected_version:state.settingsVersion});
  const result=await api('queue_enqueue',{job_ids:[job.id],identity_id,resume_asset_id:asset.id,request_id:newRequestId(),retry:true,start_now:true,producer:'dashboard',enqueue_origin:'manual_retry'});
  const q=result.queue||{},item=result.items[0];
  const message=item.state==='dispatched'?'This application is already in progress.':
   q.automation_paused?'Request saved. Choose Resume Jobot to start queued applications.':
   !q.worker_online?'Request saved, but the queue worker is offline. It will start this job when the service is back online.':
   q.counts?.dispatched?(q.concurrency_limit||1)>1?'Request saved. This job will start when a slot is available, after earlier Apply now requests.':'Request saved. This job will run after the current application and any earlier Apply now requests.':
   'Request saved. The worker will start this job as soon as its browser is free, ahead of automatic jobs.';
  notice(postingLabel(job)+': '+message);
  await refresh();
 }catch(error){notice(error.message,true);}
 finally{button.disabled=false;}
}
function runNextMessage(q){
 if(q.automation_paused)return 'Request saved. Applications and discovery are paused. Choose Resume Jobot to run queued work.';
 if(!q.counts?.queued)return q.counts?.dispatched?'An application is already in progress. No other jobs are waiting.':'No eligible jobs are waiting. Active jobs are picked up automatically; check job reasons below.';
 if(!q.worker_online)return 'Request saved, but the queue worker is offline. Start the Jobot queue service to run queued jobs.';
 if(q.ready_count===0&&q.scheduled_count)return `Retries are scheduled for later. Next retry: ${stamp(q.next_job_at)}.`;
 return (q.concurrency_limit||1)>1?'Request saved. The worker will fill available application slots from the queue.':q.counts?.dispatched?'Request saved. The next queued job will wait for the current application to finish.':'Request saved. The worker will start the next queued job when its browser is free.';
}
function renderDispatcher(v){
 const q=v.dispatch_queue||{};
 const discovery=v.discovery;
 const paused=!!q.automation_paused;
 const draining=!!q.counts?.dispatched||discovery?.last_run?.state==='running'||(v.local_runtime?.sessions||[]).some(s=>!s.ended_at);
 if($('automation-toggle')){
  $('automation-toggle').hidden=!q.installed||q.automation_pause_supported===false;
  $('automation-toggle').textContent=paused?'Resume Jobot':'Pause Jobot';
 }
 if($('automation-status')){
  $('automation-status').hidden=!q.installed||q.automation_pause_supported===false;
  $('automation-status').classList.toggle('paused',paused);
  $('automation-status').textContent=paused?
   (draining?'Finishing current work, then paused. No new queued applications or discovery will start until you choose Resume Jobot.':
    'Paused. Applications and discovery will wait until you choose Resume Jobot.'):
   'Pause Jobot finishes current work, then pauses the application queue and discovery until you resume.';
 }
 if($('discovery-status')){
  const last=discovery?.last_run;
  $('discovery-status').textContent=!discovery?.installed?'Discovery status unavailable until the updated discovery service is installed.':
   `Discovery: up to ${discovery.batch_size} jobs every ${discovery.interval_hours} hours · Runner: ${discovery.runner}. `+
   `${last?`Last started ${stamp(last.started_at)} · ${last.state==='completed'?'Executor finished; see discovered jobs':last.state==='incomplete'?'Incomplete: executor ended without saving discovery results':displayStatus(last.state)}. `:'No discovery run recorded yet. '}`+
   `${paused?'New discovery is paused until Resume Jobot. ':last?.state==='running'?'Discovery is running. ':`Next due: ${discovery.next_due_at?stamp(discovery.next_due_at):'next scheduler check'}. `}`+
   `${discovery.scheduler_recent?'Scheduler checked recently.':last?.state==='running'?`Last scheduler check: ${stamp(discovery.scheduler_last_checked_at)}.`:'No recent scheduler check; check the discovery service.'} Change frequency and job limit in Settings.`;
 }
 if($('main-resume-filename'))$('main-resume-filename').hidden=!!v.local_runtime?.workspaces?.length;
 const candidate=$('candidate')?.value;
 if($('queue-resume')){
  const assets=(v.assets||[]).filter(a=>a.identity_id===candidate&&a.kind==='resume'&&a.status==='available');
  const options=assets.map(a=>[a.id,(a.provenance?.filename||a.storage_ref.split('/').pop())+' · '+a.version]);
  const selected=$('queue-resume').value||((q.selection?.identity_id===candidate)?q.selection?.resume_asset_id:null);
  choice('queue-resume',options,selected);
 }
 const startupWait=q.worker_online&&!paused?({waiting_for_executor_startup:'Waiting for Hermes to finish starting. Jobs stay queued and resume automatically.',waiting_for_browser_startup:'Waiting for the application browser to become available. Jobs stay queued and resume automatically.'}[q.detail]||''):'';
 if($('dispatcher-status'))$('dispatcher-status').textContent=!q.installed?'Queue upgrade required: restart with the current queue dashboard launcher.':
  `${q.worker_online?'Worker online':'Worker offline — start the Jobot queue service'} · ${q.ready_count??q.counts?.queued??0} ready · ${q.scheduled_count||0} scheduled retries · ${q.active_count??q.counts?.dispatched??0} of ${q.concurrency_limit||1} applications active · ${paused?'Jobot paused. Queued jobs are saved until you resume.':startupWait||`Automatic queue ${q.enabled?'on':'paused'}. Available application slots fill automatically from the queue.`}`;
 if($('application-schedule'))$('application-schedule').textContent=
  paused?'New applications are paused, including Queue selected, Apply now and Wake existing queue requests. Current work finishes normally.':
  `${q.counts?.dispatched?'Applications are running. Ready jobs start as slots become available. ':''}`+
  `${q.enabled?`Next application check: ${q.next_automatic_at?stamp(q.next_automatic_at):'worker’s next check'}.`:'Automatic applications are paused; Queue selected or Apply now can request work immediately.'}`+
  `${q.ready_count===0&&q.next_job_at?` Next scheduled retry: ${stamp(q.next_job_at)}.`:''} Up to 6 attempts: 4 in the first 24 hours, then 2 the next day. Targets: 0, 2, 4, 6, 24 and 28 hours; busy or long runs move later. After 6 attempts, review the failure reason.`;
 if($('queue-toggle'))$('queue-toggle').textContent=q.enabled?'Pause automatic queue':'Enable automatic queue';
 // The local queue uses Hermes' configured model and the runtime's actual workspace.
 // Do not imply that legacy model/browser controls can change that configuration.
 for(const id of ['main-model-picker','main-effort-picker','browser-profile','main-browser-mode']){
  const label=$(id)?.closest?.('label');if(label)label.hidden=!!v.local_runtime?.workspaces?.length;
 }
}
function canQueueAnswers(group){return group.disposition!=='canceled'&&!group.pending_count&&!['applied','already_applied'].includes(group.status)&&group.retry?.state!=='queued';}
function answerError(error){return ({library_answer_exists:'A reusable answer already covers this question. Edit it in Learned answers.',unanswered_questions:'Answer every required question before queueing a retry.',answer_revision_conflict:'This answer changed elsewhere. Refresh and review the latest saved answer.',question_changed:'The employer changed this question. Review its current choices.',owned_elsewhere:'Save your answers now; queue a retry after the current application closes.',reconciliation_required:'The previous browser must finish closing before another attempt can start.',already_applied:'This application was already submitted.'})[error.message]||error.message;}
async function saveAnswerGroup(group,queue){
 const changes=group.questions.filter(q=>state.answerDrafts.has(q.id)).map(q=>{const draft=state.answerDrafts.get(q.id);return {question_id:q.id,answer:draft.value,expected_revision:draft.revision};});
 let saved=false;
 try{
  if(changes.length){await api('answer_questions',{answers:changes});for(const change of changes)state.answerDrafts.delete(change.question_id);saved=true;}
  if(queue)await api('queue_answer_retries',{job_ids:[group.job_id],identity_id:group.identity_id});
  notice(queue?'Answers saved and application queued for the next batch.':saved?'Answers saved.':'No answer changes to save.');
  }catch(error){
   if(error.message==='answer_revision_conflict')for(const change of changes)state.answerDrafts.delete(change.question_id);
   notice((saved?'Answers saved. ':'')+answerError(error),true);
  }
 state.answerKey=null;await refresh();
}
state.answerMode='inbox';state.answerBulk=true;state.answerSelections={};state.learnedMode='current';state.learnedPage=0;
const ANSWER_PAGE_SIZE=12;
function answerText(value){return value==null?'No answer recorded':typeof value==='object'?value.label:String(value);}
function applicationContext(requests){
 const context=el('section',undefined,'answer-context');context.setAttribute('aria-label','Companies and positions asking this question');
 const applications=[...new Map(requests.map(r=>[r.job_id||r.id,r])).values()];
 context.append(el('p',applications.length===1?'APPLICATION':'APPLICATIONS ASKING THIS QUESTION','eyebrow'));
 const rows=el('div',undefined,'answer-context-rows');
 for(const job of applications){const row=el('div',undefined,'answer-context-row');const title=el('div');
  title.append(el('strong',job.company||'Company not recorded'),el('span',job.title||job.job_title||'Position not recorded'));row.append(title,link(job.url,'Open job posting'));rows.append(row);}
 context.append(rows);return context;
}
function learnedScope(entry,v){
 if(entry.scope==='global')return 'All matching applications';
 if(entry.scope==='company'){const job=v.jobs?.find(j=>(j.company||'').normalize('NFKC').trim().toLowerCase()===entry.scope_key);return 'Company: '+(job?.company||entry.scope_key);}
 const job=entry.application||v.jobs?.find(j=>j.id===entry.scope_key);return job?postingLabel(job):'One application';
}
function workspaceList(prefix,items,selected,renderDetail,total=items.length,serverPaged=false){
 const learned=prefix==='learned',mode=learned?state.learnedMode:state.answerMode;
 const selectionKey=prefix+':'+mode,old=state.answerSelections[selectionKey];
 let page=learned?state.learnedPage:state.answerPage||0;
 let index=items.findIndex(item=>item.id===old?.id);
 if(index<0)index=Math.min(old?.index??(serverPaged?0:page),Math.max(0,items.length-1));
 if(!serverPaged){page=Math.floor(index/ANSWER_PAGE_SIZE)*ANSWER_PAGE_SIZE;if(learned)state.learnedPage=page;else state.answerPage=page;}
 const chosen=items[index];state.answerSelections[selectionKey]=chosen?{id:chosen.id,index}:null;
 const list=$(prefix+'-list'),detail=$(learned?'learned-detail':'answer-groups');
 const same=chosen?.id===old?.id,listScroll=list.scrollTop,detailScroll=detail.scrollTop;
 const focused=document.activeElement,focusId=same&&detail.contains(focused)?focused.id:null;
 const caret=focusId&&typeof focused.selectionStart==='number'?[focused.selectionStart,focused.selectionEnd]:null;
 list.replaceChildren();detail.replaceChildren();detail.classList.remove('answer-editor-host');$(prefix+'-pagination').replaceChildren();
 const shown=serverPaged?items:items.slice(page,page+ANSWER_PAGE_SIZE);
 for(const item of shown){const row=el('button',undefined,'answer-list-item');row.type='button';row.dataset.answerId=item.id;row.setAttribute('aria-pressed',String(item===chosen));
  row.append(el('strong',item.company),el('span',item.role,'answer-list-role'),el('span',item.question,'answer-list-question'));
  if(item.meta)row.append(el('small',item.meta));
  row.onclick=()=>{state.answerSelections[selectionKey]={id:item.id,index:items.indexOf(item)};if(learned)state.learnedKey=null;else state.answerKey=null;renderAnswers(state.view);};list.append(row);}
 if(chosen)renderDetail(chosen.value,detail);
 else{list.append(el('p','No matching items.','answer-empty'));detail.append(el('h3',mode==='inbox'?'You’re caught up.':'Nothing selected'),el('p',mode==='inbox'?'Saved answers are in Learned answers. Applications with all answers saved are in Ready to retry.':'Try another view or search.','answer-empty'));}
 const pager=$(prefix+'-pagination');
 for(const [direction,label,disabled,next] of [['previous','Previous',page===0,Math.max(0,page-ANSWER_PAGE_SIZE)],['next','Next',page+ANSWER_PAGE_SIZE>=total,page+ANSWER_PAGE_SIZE]]){
  const button=el('button',label);button.type='button';button.dataset.page=direction;button.disabled=disabled;
  button.onclick=()=>{state.answerSelections[selectionKey]={index:serverPaged?0:next};if(learned){state.learnedPage=next;state.learnedKey=null;}else{state.answerPage=next;state.answerKey=null;}renderAnswers(state.view);};pager.append(button);}
 pager.insertBefore(el('span',`${total?page+1:0}–${Math.min(page+ANSWER_PAGE_SIZE,total)} of ${total}`),pager.lastChild);
 const picker=$(prefix+'-picker');picker.replaceChildren();for(const item of shown){const option=el('option',[item.company,item.role,item.question].join(' · '));option.value=item.id;picker.append(option);}picker.value=chosen?.id||'';picker.disabled=!chosen;
 picker.onchange=()=>{const item=items.find(i=>i.id===picker.value);state.answerSelections[selectionKey]={id:item.id,index:items.indexOf(item)};if(learned)state.learnedKey=null;else state.answerKey=null;renderAnswers(state.view);};
 list.scrollTop=listScroll;if(same)detail.scrollTop=detailScroll;fitAnswerWorkspace();
 if(focusId&&$(focusId)){const input=$(focusId);input.focus({preventScroll:true});if(caret)input.setSelectionRange(...caret);}
}
function fitAnswerWorkspace(){
 for(const workspace of document.querySelectorAll('.answer-workspace')){const rect=workspace.getBoundingClientRect();if(window.innerWidth<=850)workspace.style.height='';else if(rect.width)workspace.style.height=Math.max(380,Math.min(820,window.innerHeight-rect.top-62))+'px';}
}
globalThis.addEventListener?.('resize',fitAnswerWorkspace);
function renderAnswerReceipt(){
 const receipt=$('answer-receipt');receipt.replaceChildren();receipt.hidden=!state.answerReceipt;if(!state.answerReceipt)return;
 const saved=state.answerReceipt;
 const activity=(state.view?.answer_library?.suggestions||[]).filter(a=>saved.questionIds?.includes(a.source?.question_id||a.source_id));
 const learned=new Set(activity.filter(a=>a.state==='learned').map(a=>a.source_id||a.source?.question_id)).size;
 receipt.append(el('span',(saved.questionCount?`${saved.questionCount} question${saved.questionCount===1?'':'s'} saved for ${saved.applicationCount} application${saved.applicationCount===1?'':'s'}.`:'Answer saved for the selected applications.')+(learned?` AI has processed ${learned} saved replies into reusable knowledge.`:' AI will extract reusable knowledge in the background.')));
 const view=el('button','View AI learning');view.type='button';view.onclick=()=>{state.learnedMode='suggestions';state.learnedPage=0;$('learned-search').value='';state.answerSelections['learned:suggestions']=activity[0]?{id:activity[0].id}:null;state.learnedKey=null;renderLearnedAnswers(state.view);tab('learned');};receipt.append(view);
 const dismiss=el('button','Dismiss');dismiss.type='button';dismiss.onclick=()=>{state.answerReceipt=null;renderAnswerReceipt();};receipt.append(dismiss);
}
function openLearnedAnswer(id){
 state.learnedMode='current';state.learnedPage=0;$('learned-search').value='';state.answerSelections['learned:current']={id};state.learnedKey=null;
 renderLearnedAnswers(state.view);tab('learned');
}
function renderAnswers(v){
 if(!$('answer-groups'))return;
 renderLearnedAnswers(v);renderAnswerReceipt();
 updateDraftToolbar();
 $('answer-picker').closest('label').hidden=!!state.answerBulk&&state.answerMode==='inbox';
 $('answer-groups').closest('.answer-workspace').classList.toggle('answer-bulk-workspace',!!state.answerBulk&&state.answerMode==='inbox');
 const active=(v.answer_queue?.groups||[]).filter(g=>g.disposition!=='canceled'&&!['applied','already_applied'].includes(g.status));
 const pending=v.answer_queue?.clusters?.length??active.reduce((count,g)=>count+g.pending_count,0),ready=v.answer_queue?.ready||active.filter(canQueueAnswers);
 $('answer-count').textContent=pending?`(${pending})`:'';$('inbox-count').textContent=pending;$('ready-count').textContent=ready.length;$('answer-history-count').textContent=v.answer_queue?.history_count??0;
 $('queue-answered-batch').disabled=!active.some(canQueueAnswers);$('queue-answered-batch').hidden=state.answerMode!=='ready';
 for(const button of document.querySelectorAll('[data-answer-mode]'))button.setAttribute('aria-pressed',String(button.dataset.answerMode===state.answerMode));
 $('answer-heading').textContent={inbox:'Needs your answer',ready:'Ready to retry',history:'Answer history'}[state.answerMode];
 const term=$('answer-search').value.trim().toLowerCase(),mode=state.answerMode;
 if(mode==='history'){
  const key=JSON.stringify([term,state.answerPage||0,v.answer_queue?.history_count]);
  if(state.answerHistory?.key!==key){if(state.answerHistoryRequest!==key){state.answerHistoryRequest=key;loadAnswerHistory(term,state.answerPage||0,key);}return;}
  const result=state.answerHistory.result;$('answer-summary').textContent=`${result.total} historical application${result.total===1?'':'s'}`;
  workspaceList('answer',result.groups.map(g=>({id:g.job_id,value:g,company:g.company||'Company not recorded',role:g.title||'Position not recorded',question:`${g.questions.length} recorded questions`,meta:g.disposition==='canceled'?'Canceled':g.retry?.state==='queued'?'Queued for retry':g.status})),null,renderHistoryDetail,result.total,true);return;
 }
 const key=JSON.stringify([mode,term,state.answerBulk,state.answerPage||0,state.answerSelections['answer:'+mode],v.answer_queue]);if(key===state.answerKey)return;state.answerKey=key;
 if(mode==='inbox'){
  const clusters=v.answer_queue?.clusters||active.flatMap(g=>g.questions.filter(q=>q.state==='pending').map(q=>({...q,id:q.id,identity_id:g.identity_id,email:g.email,aliases:[],scope:'job',requests:[{...g,question_id:q.id,revision:q.revision}],request_count:1})));
  const filtered=clusters.filter(c=>!term||JSON.stringify(c).toLowerCase().includes(term));
  $('answer-summary').textContent=`${filtered.length} question${filtered.length===1?'':'s'}${term?' matching your search':' to answer'}`;
  if(state.answerBulk){renderBulkAnswers(filtered);return;}
  workspaceList('answer',filtered.map(c=>{const first=c.requests[0],count=new Set(c.requests.map(r=>r.job_id)).size;return {id:c.id,value:c,company:first.company||'Company not recorded',role:(first.title||'Position not recorded')+(count>1?` + ${count-1} other position${count===2?'':'s'}`:''),question:c.question,meta:`${count} application${count===1?'':'s'}`};}),null,renderClusterDetail);
 }else{
  const groups=ready.filter(g=>!term||JSON.stringify(g).toLowerCase().includes(term));$('answer-summary').textContent=`${groups.length} application${groups.length===1?'':'s'} ready to retry`;
  workspaceList('answer',groups.map(g=>({id:g.job_id,value:g,company:g.company||'Company not recorded',role:g.title||'Position not recorded',question:`${g.questions.filter(q=>q.state!=='superseded').length} answers saved`,meta:g.email})),null,renderReadyDetail);
 }
}
function answerInput(question,id,current){
 let input;
 if(question.kind==='text'){input=el('textarea');input.rows=4;input.maxLength=4000;input.value=current??'';}
 else{input=el('select');const blank=el('option','Choose your answer');blank.value='';blank.disabled=true;input.append(blank);
  for(const option of question.kind==='check'?[{value:'true',label:'Yes'},{value:'false',label:'No'}]:question.options){
   const choice=el('option',option.label);choice.value=question.kind==='check'?option.value:JSON.stringify([option.value,option.label]);input.append(choice);}
  input.value=current==null?'':question.kind==='check'?String(current):JSON.stringify([current.value,current.label]);}
 input.id=id;input.setAttribute('aria-label',question.question);input.required=true;return input;
}
function inputAnswer(input,kind){return kind==='check'?input.value==='true':kind==='text'?input.value:((parts)=>({value:parts[0],label:parts[1]}))(JSON.parse(input.value));}
function answerDraftKey(cluster){return cluster.requests.map(r=>r.question_id).find(id=>state.answerDrafts.get(id)?.requests)||cluster.requests[0].question_id;}
function rememberAnswerDraft(cluster,change){
 const first=cluster.requests[0],key=answerDraftKey(cluster),old=state.answerDrafts.get(key);
 state.answerDrafts.set(key,{kind:cluster.kind,scope:cluster.scope,scope_key:cluster.scope==='company'?first.company:first.job_id,
  requests:cluster.requests.map(r=>({...r})),revision:first.revision,...old,...change});updateDraftToolbar();
}
function pendingAnswerDrafts(){return [...state.answerDrafts].filter(([,d])=>d.requests?.length&&draftRequests(d).length&&d.value!==undefined&&String(typeof d.value==='object'?d.value?.label:d.value).trim()!=='');}
function draftRequests(draft){return draft.requests.filter(r=>draft.scope==='global'||(draft.scope==='company'?r.company===draft.scope_key:r.job_id===draft.scope_key));}
function updateDraftToolbar(){
 const drafts=pendingAnswerDrafts(),apps=new Set(drafts.flatMap(([,d])=>draftRequests(d).map(r=>r.job_id)));
 $('answer-draft-toolbar').hidden=state.answerMode!=='inbox';
 $('answer-bulk-toggle').textContent=state.answerBulk?'Focus on one question':'Answer in bulk';$('answer-bulk-toggle').setAttribute('aria-pressed',String(!!state.answerBulk));
 $('answer-save-drafts').textContent=state.answerSaving?'Saving…':drafts.length?`Save ${drafts.length} drafts`:'Save drafts';$('answer-save-drafts').disabled=!!state.answerSaving||!drafts.length;
 $('answer-draft-count').textContent=drafts.length?`${apps.size} application${apps.size===1?'':'s'} · includes drafts on other pages`:'Drafts stay here while you switch questions. Save before leaving this page.';
}
async function saveAnswerDrafts(){
 if(state.answerSaving)return;const drafts=pendingAnswerDrafts();if(!drafts.length)return;
 const changes=drafts.flatMap(([key,d])=>draftRequests(d).map(r=>({key,draft:d,job_id:r.job_id,change:{question_id:r.question_id,expected_revision:r.revision,
  answer:typeof d.value==='object'?((r.options||[]).find(o=>o.label.trim().toLowerCase()===d.value.label.trim().toLowerCase())||d.value.label):d.value}})));
 state.answerSaving=true;updateDraftToolbar();const completed=[];
 try{
  for(let offset=0;offset<changes.length;offset+=100){const batch=changes.slice(offset,offset+100);await api('answer_questions',{answers:batch.map(x=>x.change)});completed.push(...batch);
   for(const item of batch){const current=state.answerDrafts.get(item.key);if(!current)continue;
    // Keep edits made while the request was in flight, using the new server revision.
    const requests=current.requests.map(r=>r.question_id===item.change.question_id?{...r,revision:r.revision+1}:r);
    const submitted=drafts.find(([key])=>key===item.key)?.[1];
    const remaining=current.value===submitted?.value&&current.scope===submitted?.scope&&current.scope_key===submitted?.scope_key?requests.filter(r=>draftRequests(submitted).some(s=>s.question_id===r.question_id)&&!completed.some(x=>x.change.question_id===r.question_id)):requests;
    if(remaining.length)state.answerDrafts.set(item.key,{...current,requests:remaining});else state.answerDrafts.delete(item.key);
   }
  }
  notice('Answers saved. Review Ready to retry to resume fully answered applications.');
 }catch(error){notice((completed.length?`${completed.length} application replies saved. Remaining drafts are kept. `:'Drafts kept. ')+answerError(error),true);}
 finally{state.answerSaving=false;if(completed.length){state.answerReceipt={questionCount:new Set(completed.map(x=>x.key)).size,applicationCount:new Set(completed.map(x=>x.job_id)).size,questionIds:completed.map(x=>x.change.question_id)};renderAnswerReceipt();}updateDraftToolbar();state.answerKey=null;await refresh();}
}
function renderBulkAnswers(clusters){
 const container=$('answer-groups'),focused=document.activeElement,focusId=container.contains(focused)?focused.id:null;
 const caret=focusId&&typeof focused.selectionStart==='number'?[focused.selectionStart,focused.selectionEnd]:null,scroll=container.scrollTop;
 container.replaceChildren();container.classList.remove('answer-editor-host');$('answer-list').replaceChildren();$('answer-picker').closest('label').hidden=true;
 const page=Math.min(state.answerPage||0,Math.max(0,Math.floor((clusters.length-1)/ANSWER_PAGE_SIZE)*ANSWER_PAGE_SIZE));state.answerPage=page;
 for(const cluster of clusters.slice(page,page+ANSWER_PAGE_SIZE)){
  const first=cluster.requests[0],draft=state.answerDrafts.get(answerDraftKey(cluster)),row=el('article',undefined,'answer-bulk-row');
  const context=el('div');context.append(el('h3',cluster.question.length>240?cluster.question.slice(0,237)+'…':cluster.question));
  if(cluster.question.length>240){const full=el('details');full.append(el('summary','Read full question'),el('p',cluster.question));context.append(full);}
  context.append(el('p',`${first.company||'Company not recorded'} · ${first.title||'Position not recorded'}`,'answer-meta'));
  const count=new Set(cluster.requests.map(r=>r.job_id)).size,applications=el('details');applications.append(el('summary',`${count} matching application${count===1?'':'s'} · ${cluster.email}`),applicationContext(cluster.requests));context.append(applications);
  const editor=el('div'),input=answerInput(cluster,'answer-'+first.question_id,draft?.value);if(cluster.kind==='text')input.rows=3;
  input.oninput=()=>rememberAnswerDraft(cluster,{value:inputAnswer(input,cluster.kind)});editor.append(input);
  const scope=el('select');scope.setAttribute('aria-label','Applications for '+cluster.question);
  const all=el('option','All matching applications shown');all.value='global';scope.append(all);
  for(const request of new Map(cluster.requests.map(r=>[r.job_id,r])).values()){const option=el('option',postingLabel(request));option.value=request.job_id;scope.append(option);}
  scope.value=draft?.scope==='job'?draft.scope_key:'global';
  scope.onchange=()=>rememberAnswerDraft(cluster,{scope:scope.value==='global'?'global':'job',scope_key:scope.value==='global'?'':scope.value});
  // Company clusters already contain only that company. Preserve a narrower focused draft.
  if(draft?.scope==='company'){const option=el('option','Company: '+draft.scope_key);option.value='company';scope.append(option);scope.value='company';scope.onchange=()=>rememberAnswerDraft(cluster,{scope:scope.value==='company'?'company':scope.value==='global'?'global':'job',scope_key:scope.value==='company'?draft.scope_key:scope.value});}
  editor.append(scope);row.append(context,editor);container.append(row);
 }
 if(!clusters.length)container.append(el('p','No unanswered questions match this view.','answer-empty'));
 const pager=$('answer-pagination');pager.replaceChildren();
 for(const [label,next,disabled] of [['Previous',page-ANSWER_PAGE_SIZE,page===0],['Next',page+ANSWER_PAGE_SIZE,page+ANSWER_PAGE_SIZE>=clusters.length]]){const button=el('button',label);button.disabled=disabled;button.dataset.page=label.toLowerCase();button.onclick=()=>{state.answerPage=next;state.answerKey=null;renderAnswers(state.view);};pager.append(button);}
 pager.insertBefore(el('span',`${clusters.length?page+1:0}–${Math.min(page+ANSWER_PAGE_SIZE,clusters.length)} of ${clusters.length}`),pager.lastChild);
 container.scrollTop=scroll;fitAnswerWorkspace();if(focusId&&$(focusId)){$(focusId).focus({preventScroll:true});if(caret)$(focusId).setSelectionRange(...caret);}
}
$('answer-bulk-toggle').onclick=()=>{state.answerBulk=!state.answerBulk;state.answerPage=0;state.answerKey=null;$('answer-picker').closest('label').hidden=false;renderAnswers(state.view);};
$('answer-save-drafts').onclick=saveAnswerDrafts;
function renderClusterDetail(cluster,container){
 container.classList.add('answer-editor-host');
 const form=el('form',undefined,'answer-application');form.append(applicationContext(cluster.requests));
 form.append(el('h3',cluster.question,'answer-question-heading'),el('p',`Answering for ${cluster.email}`,'answer-meta'));
 const question=cluster.requests[0],draftKey=answerDraftKey(cluster),draft=state.answerDrafts.get(draftKey);
 const field=el('label',undefined,'answer-field');field.append(el('span','Your answer'));
 const input=answerInput(cluster,'answer-'+question.question_id,draft?.value);field.append(input);form.append(field);
 input.oninput=()=>rememberAnswerDraft(cluster,{value:inputAnswer(input,cluster.kind)});
 const scopeLabel=el('label',undefined,'answer-field');scopeLabel.append(el('span','Answer these applications'));
 const scope=el('select');scope.setAttribute('aria-label','Answer these applications');
 for(const [value,label] of [['global','All applications shown here'],['company','One company shown here'],['job','One position only']]){const option=el('option',label);option.value=value;scope.append(option);}scope.value=draft?.scope||cluster.scope;
 const target=el('select');target.setAttribute('aria-label','Company or position to reuse this answer for');
 const update=()=>{target.replaceChildren();target.hidden=scope.value==='global';const seen=new Set();
  for(const request of cluster.requests){const value=scope.value==='company'?request.company:request.job_id;if(!value||seen.has(value))continue;seen.add(value);const option=el('option',scope.value==='company'?request.company:postingLabel(request));option.value=value;target.append(option);}};
 const remember=()=>rememberAnswerDraft(cluster,{scope:scope.value,scope_key:target.value});
 scope.onchange=()=>{update();remember();};target.onchange=remember;update();if(draft?.scope_key)target.value=draft.scope_key;scopeLabel.append(scope,target);form.insertBefore(scopeLabel,field);
 const body=el('div',undefined,'answer-editor-body');for(const child of [...form.children])body.append(child);form.append(body);
 const actions=el('div',undefined,'answer-actions answer-save-bar'),save=el('button','Save answer','primary');save.type='submit';const add=el('button','Add reusable answer');add.type='button';add.onclick=()=>editLibraryAnswer({identity_id:cluster.identity_id,question:cluster.question,answer:input.value?((value)=>typeof value==='object'?value.label:value)(inputAnswer(input,cluster.kind)):'',aliases:cluster.aliases,scope:scope.value,scope_key:target.hidden?'':target.value});actions.append(save,add);form.append(actions);

 form.onsubmit=async event=>{event.preventDefault();if(save.disabled||!input.reportValidity())return;save.disabled=true;save.textContent='Saving…';
  const submittedDraft=state.answerDrafts.get(draftKey);
  try{if(submittedDraft?.value===undefined)throw Error('Enter your answer.');
   const requests=draftRequests({...submittedDraft,scope:scope.value,scope_key:target.value});
   const meaning=typeof submittedDraft.value==='object'?submittedDraft.value.label:submittedDraft.value;
   await api('answer_questions',{answers:requests.map(r=>({question_id:r.question_id,expected_revision:r.revision,answer:cluster.kind==='select'||cluster.kind==='radio'?((r.options||cluster.options).find(o=>o.label.trim().toLowerCase()===String(meaning).trim().toLowerCase())?.label||meaning):meaning}))});
   if(state.answerDrafts.get(draftKey)===submittedDraft)state.answerDrafts.delete(draftKey);
   state.answerReceipt={saved:true,questionIds:requests.map(r=>r.question_id)};renderAnswerReceipt();updateDraftToolbar();notice('Application answer saved. AI learning runs in the background.');state.answerKey=null;await refresh();
  }catch(error){notice(answerError(error),true);}finally{save.disabled=false;save.textContent='Save answer';}};
 container.append(form);
}
function renderReadyDetail(group,container){
 const card=el('article',undefined,'answer-application');card.append(applicationContext([group]),el('h3','Answers saved — ready to retry','answer-question-heading'),el('p',group.email,'answer-meta'));
 for(const question of group.questions.filter(q=>q.state!=='superseded')){
  const label=el('label',undefined,'answer-field');label.append(el('span',question.question));
  const input=answerInput(question,'answer-'+question.id,state.answerDrafts.get(question.id)?.value??question.answer);
  input.oninput=()=>state.answerDrafts.set(question.id,{value:inputAnswer(input,question.kind),revision:state.answerDrafts.get(question.id)?.revision??question.revision});label.append(input);
  if(question.library_entry_id){const view=el('button','View learned answer');view.type='button';view.onclick=()=>openLearnedAnswer(question.library_entry_id);label.append(view);}
  card.append(label);
 }
 const actions=el('div',undefined,'answer-actions'),save=el('button','Save answers'),retry=el('button','Save and queue retry','primary');
 save.onclick=()=>saveAnswerGroup(group,false);retry.onclick=()=>saveAnswerGroup(group,true);actions.append(save,retry);card.append(actions);
 if(!group.browser_stopped)card.append(el('p','Save your answers to continue in the active application.'));
 container.append(card);
}
function renderHistoryDetail(group,container){
 const card=el('article',undefined,'answer-application');card.append(applicationContext([group]),el('h3','Recorded questions and responses','answer-question-heading'),el('p',group.email,'answer-meta'));
 for(const [index,question] of group.questions.entries()){
  const details=el('details',undefined,'answer-library-history');details.open=index===0;details.append(el('summary',question.question),el('p',answerText(question.answer)),el('small',question.answer_source||question.state));
  for(const response of question.answer_history||[])details.append(el('p',`Version ${response.revision} · ${stamp(response.created_at)} · ${response.source}\n${answerText(response.answer)}`));
  if(question.answer!=null){const reuse=el('button','Add reusable answer manually');reuse.onclick=()=>editLibraryAnswer({identity_id:group.identity_id,question:question.question,answer:answerText(question.answer),scope:group.company?'company':'job',scope_key:group.company||group.job_id,aliases:[],conditions:{}});details.append(reuse);}card.append(details);
 }container.append(card);
}
function learningLabel(value){return ({learned:'Reusable knowledge saved',pending:'Waiting for AI learning',processing:'AI is extracting reusable knowledge',error:'AI learning could not finish; will retry',context_only:'Application-specific response — kept in history',conflict:'Different from current knowledge — review before replacing',changed:'Source changed — your latest response is preserved'})[value]||value||'Waiting for AI learning';}
function renderLearningImpact(library){
 const impact=library.impact||{},entries=library.entries||[],panel=$('learning-impact');panel.replaceChildren();
 for(const [value,label] of [[entries.filter(e=>e.state==='active'&&e.origin!=='legacy').length,'Reusable answers'],[impact.applications||0,'Applications with recorded reuse'],[impact.resolved_questions||0,'Matched questions'],[impact.recorded_form_uses||0,'Recorded form uses']]){
  const card=el('div');card.append(el('strong',value),el('span',label));panel.append(card);
 }
 const applications=$('learning-applications');applications.replaceChildren();applications.append(el('summary','Which applications used these answers?'),el('p','Matched questions and recorded form uses are evidence of reuse, not proof of submission. Unrecorded agent use is not counted.'));
 if(impact.recent_applications?.length){applications.append(el('p',`Showing ${impact.recent_applications.length} most recently recorded applications.`),applicationContext(impact.recent_applications));}
 else applications.append(el('p','No application reuse has been recorded yet. Open an answer to inspect its source and history.'));
}
function renderLearnedAnswers(v){
 const library=v.answer_library||{entries:[],suggestions:[]},entries=library.entries||[],suggestions=library.suggestions||[];
 const learning=library.learning||{};const status=$('learning-status');if(status)status.textContent=`AI learning: ${learning.pending||0} waiting · ${learning.processing||0} processing${learning.error?' · '+learning.error+' will retry':''}. Your application answers are already saved.`;
 renderLearningImpact(library);
 $('learned-count').textContent=`(${entries.filter(e=>e.state==='active'&&e.origin!=='legacy').length})`;
 $('learned-current-count').textContent=entries.filter(e=>e.state==='active'&&e.origin!=='legacy').length;$('learned-retired-count').textContent=entries.filter(e=>e.state==='retired').length;$('learned-suggestion-count').textContent=learning.total??suggestions.length;
 for(const button of document.querySelectorAll('[data-learned-mode]'))button.setAttribute('aria-pressed',String(button.dataset.learnedMode===state.learnedMode));
 const term=$('learned-search').value.trim().toLowerCase(),mode=state.learnedMode;
 const key=JSON.stringify([library,term,mode,state.learnedPage,state.answerSelections['learned:'+mode]]);if(key===state.learnedKey)return;state.learnedKey=key;
 const items=(mode==='suggestions'?suggestions:entries.filter(e=>e.state===(mode==='retired'?'retired':'active')&&(mode==='retired'||e.origin!=='legacy'))).filter(e=>!term||JSON.stringify([e,learnedScope(e,v),v.candidates?.find(c=>c.id===e.identity_id)?.email]).toLowerCase().includes(term));
 $('learned-summary').textContent=mode==='suggestions'?(term?`${items.length} matching record${items.length===1?'':'s'} in the latest ${suggestions.length} of ${learning.total??suggestions.length} learning records`:`${items.length} latest records of ${learning.total??suggestions.length}`):`${items.length} ${mode==='retired'?'retired answers':'learned answers'}`;
 workspaceList('learned',items.map((e,i)=>({id:e.id||'suggestion-'+i,value:e,company:e.question,role:learnedScope(e,v),question:mode==='suggestions'?learningLabel(e.state):answerText(e.answer),meta:mode==='suggestions'?`${e.source?.company||''} · ${e.source?.title||''}`:v.candidates?.find(c=>c.id===e.identity_id)?.email||e.identity_id})),null,(entry,container)=>{
  const card=el('article',undefined,'answer-application');card.append(el('p',learnedScope(entry,v),'eyebrow'),el('h3',entry.question,'answer-question-heading'));
  if(entry.scope==='job'){const job=entry.application||v.jobs?.find(j=>j.id===entry.scope_key);if(job)card.prepend(applicationContext([job]));}
  if(mode==='suggestions'){
   if(entry.source?.applications?.length)card.prepend(applicationContext(entry.source.applications));else if(entry.source?.job_id)card.prepend(applicationContext([entry.source]));
   card.append(el('p',learningLabel(entry.state),'answer-meta'));
   if(entry.updated_at)card.append(el('p',`Updated ${stamp(entry.updated_at)} · ${entry.attempts||0} learning attempts`,'answer-meta'));
   if(entry.state==='error')card.append(el('p',`${entry.error_code==='learning_model_unavailable'?'The learning model is unavailable.':'AI learning could not finish this response.'}${entry.retry_at?' Next retry after '+stamp(entry.retry_at)+'.':''}`));
   if(entry.entry_id&&entry.state==='learned'){const result=entries.find(e=>e.id===entry.entry_id);if(result)card.append(el('p',answerText(result.answer),'learned-answer-value'));const view=el('button','View learned answer','primary');view.onclick=()=>openLearnedAnswer(entry.entry_id);card.append(view);}
   const source=el('details');source.append(el('summary','Original question and response'),el('p',entry.source?.question||''),el('p',answerText(entry.source?.answer)));card.append(source);
   if(entry.state==='conflict'&&entry.answer!=null){const current=entries.find(e=>e.id===entry.existing_entry_id);const comparison=el('div',undefined,'learning-comparison');
    for(const [label,value] of [['Current answer',current?answerText(current.answer):'No current answer'],['Proposed answer',answerText(entry.answer)]]){const side=el('div');side.append(el('h4',label),el('p',value,'learned-answer-value'));comparison.append(side);}card.append(comparison);
    const review=el('button','Review proposed knowledge');review.onclick=()=>editLibraryAnswer(current?{...current,answer:entry.answer}:{...entry,id:undefined,answer:entry.answer},current);card.append(review);}
  }else{
   card.append(el('p',entry.origin==='legacy'?'ORIGINAL RESPONSE · ARCHIVED':entry.origin==='ai'?'LEARNED BY AI':entry.origin==='ai_edited'?'LEARNED BY AI · EDITED BY YOU':'ADDED BY YOU','eyebrow'),el('p',answerText(entry.answer),'learned-answer-value'),el('p',`Updated ${stamp(entry.updated_at)} · Version ${entry.revision}`,'answer-meta'));
   if(Object.keys(entry.conditions||{}).length)card.append(el('p',Object.entries(entry.conditions).map(([k,value])=>k+': '+value).join(' · ')));
   const usage=entry.usage||{},uses=el('details',undefined,'answer-library-history');
   card.append(el('p',`${usage.resolved_questions||0} matched questions · ${usage.recorded_form_uses||0} recorded form uses · ${usage.applications||0} applications`,'answer-meta'));
   uses.append(el('summary',usage.last_used_at?`Reuse evidence · Last used ${stamp(usage.last_used_at)}`:'No recorded reuse yet'));
   uses.append(el('p','Matched means the answer was selected for a saved question. Form use means a private form journal recorded it. Neither proves submission. Unrecorded agent use is not counted.'));
   for(const use of usage.recent||[]){const item=el('div');item.append(applicationContext([use]),el('p',`${use.kind==='form'?'Recorded form use':'Matched question'} · Version ${use.library_revision} · ${stamp(use.at)}${use.attempt_id?' · Attempt '+use.attempt_id:''}`),el('p',use.question||''));uses.append(item);}card.append(uses);
   const actions=el('div',undefined,'answer-actions'),edit=el('button','Edit answer','primary'),retire=el('button',entry.state==='active'?'Retire answer':'Restore answer');
   edit.onclick=()=>editLibraryAnswer(entry);retire.onclick=async()=>{retire.disabled=true;try{await api('set_library_answer_state',{entry_id:entry.id,state:entry.state==='active'?'retired':'active',expected_revision:entry.revision});notice('Learned answer updated. Earlier responses kept.');state.learnedKey=null;state.answerKey=null;await refresh();}catch(error){notice(answerError(error),true);}finally{retire.disabled=false;}};actions.append(edit,retire);card.append(actions);
   if(entry.sources?.length){const sources=el('details',undefined,'answer-library-history');sources.append(el('summary',`Learned from ${entry.sources.length} response${entry.sources.length===1?'':'s'}`));for(const source of entry.sources){if(source.applications?.length)sources.append(applicationContext(source.applications));else if(source.job_id)sources.append(applicationContext([source]));sources.append(el('p',source.question),el('p',answerText(source.answer)));}card.append(sources);}
   if(entry.aliases?.length){const wording=el('details');wording.append(el('summary',`${entry.aliases.length} other question wordings`));for(const alias of entry.aliases)wording.append(el('p',alias));card.append(wording);}
   const history=el('details',undefined,'answer-library-history');history.append(el('summary',`${entry.history?.length||0} saved versions`));for(const version of entry.history||[])history.append(el('p',`Version ${version.revision} · ${stamp(version.updated_at)} · ${version.state}\n${version.question}\n${answerText(version.answer)}`));card.append(history);
  }container.append(card);
 });
}
function libraryScopeControls(){const scope=$('library-scope').value;$('library-company-label').hidden=scope!=='company';$('library-job-label').hidden=scope!=='job';}
function editLibraryAnswer(entry={},previous=null){
 const form=$('library-form');form.reset();state.libraryEditing=entry.id?entry:null;$('library-error').textContent='';
 const comparison=$('library-comparison');comparison.replaceChildren();comparison.hidden=!previous;$('library-answer-label').textContent=previous?'Proposed answer':'Current answer';
 if(previous)comparison.append(el('h3','Current saved answer'),el('p',answerText(previous.answer),'learned-answer-value'),el('p',`Scope: ${learnedScope(previous,state.view)}. Saving replaces this answer; earlier versions remain in history.`));
 choice('library-candidate',(state.view?.candidates||[]).map(c=>[c.id,c.email]),entry.identity_id||$('candidate').value);$('library-candidate').disabled=!!entry.id;
 const jobs=[...(state.view?.jobs||[])];if(entry.scope==='job'&&!jobs.some(j=>j.id===entry.scope_key))jobs.push(entry.application||{id:entry.scope_key,title:'Saved application'});
 choice('library-job',jobs.map(j=>[j.id,postingLabel(j)]),entry.scope==='job'?entry.scope_key:undefined);
 $('library-question').value=entry.question||'';$('library-answer').value=entry.answer===true?'Yes':entry.answer===false?'No':entry.answer??'';
 $('library-aliases').value=(entry.aliases||[]).join('\n');$('library-scope').value=entry.scope||'global';$('library-company').value=entry.scope==='company'?entry.scope_key:'';
 for(const key of ['country','currency','period'])$('library-'+key).value=entry.conditions?.[key]||'';
 libraryScopeControls();$('library-editor-title').textContent=entry.id?'Edit reusable answer':'Add reusable answer manually';$('library-dialog').showModal();
}
async function loadAnswerHistory(term,offset,key){
 $('answer-list').replaceChildren(el('p','Loading history…','answer-empty'));$('answer-groups').replaceChildren();$('answer-pagination').replaceChildren();
 try{const result=await api('answer_queue_history',{search:term,offset,limit:ANSWER_PAGE_SIZE});if(state.answerHistoryRequest!==key||state.answerMode!=='history')return;
  state.answerHistory={key,result};state.answerHistoryRequest=null;renderAnswers(state.view);
 }catch(error){if(state.answerHistoryRequest===key){state.answerHistoryRequest=null;$('answer-list').replaceChildren(el('p','Could not load history. Try again.','answer-empty'));notice(error.message,true);}}
}
function setAnswerMode(mode){state.answerMode=mode;state.answerPage=0;state.answerKey=null;state.answerHistoryRequest=null;renderAnswers(state.view);}
for(const button of document.querySelectorAll('[data-answer-mode]'))button.onclick=()=>setAnswerMode(button.dataset.answerMode);
for(const button of document.querySelectorAll('[data-learned-mode]'))button.onclick=()=>{state.learnedMode=button.dataset.learnedMode;state.learnedPage=0;state.learnedKey=null;renderLearnedAnswers(state.view);};
$('answer-search').oninput=()=>{state.answerPage=0;state.answerSelections['answer:'+state.answerMode]=null;state.answerKey=null;renderAnswers(state.view);};
$('learned-search').oninput=()=>{state.learnedPage=0;state.answerSelections['learned:'+state.learnedMode]=null;state.learnedKey=null;renderLearnedAnswers(state.view);};
$('add-library-answer').onclick=()=>editLibraryAnswer();$('library-cancel').onclick=()=>$('library-dialog').close();$('library-scope').onchange=libraryScopeControls;
$('library-form').onsubmit=async event=>{event.preventDefault();const save=event.currentTarget.querySelector('[type=submit]');if(save.disabled)return;save.disabled=true;
 try{const conditions={};for(const key of ['country','currency','period'])if($('library-'+key).value.trim())conditions[key]=$('library-'+key).value.trim();
  const entry=await api('save_library_answer',{identity_id:$('library-candidate').value,question:$('library-question').value,answer:$('library-answer').value,
   aliases:$('library-aliases').value.split('\n').map(q=>q.trim()).filter(Boolean),scope:$('library-scope').value,
   scope_key:$('library-scope').value==='company'?$('library-company').value:$('library-scope').value==='job'?$('library-job').value:'',conditions,
   ...(state.libraryEditing?{entry_id:state.libraryEditing.id}:{}),expected_revision:state.libraryEditing?.revision||0});
  $('library-dialog').close();notice('Saved to Learned answers. Matching outstanding questions checked.');state.answerKey=null;state.learnedKey=null;await refresh();openLearnedAnswer(entry.id);
 }catch(error){$('library-error').textContent=answerError(error);}finally{save.disabled=false;}};
$('retry-learning').onclick=async()=>{try{const result=await api('retry_answer_learning');notice(`AI learning queued: ${result.pending} responses.`);state.learnedKey=null;await refresh();}catch(error){notice(error.message,true);}};
$('reconcile-answers').onclick=async()=>{try{const result=await api('reconcile_answers');notice(`${result.resolved} questions resolved; ${result.updated} answers updated. History kept.`);state.answerKey=null;await refresh();}catch(error){notice(error.message,true);}};

const ACTIVITY_OUTCOMES={applied:'New submissions',already_applied:'Already applied',blocked:'Blocked',interrupted:'Interrupted',submission_unknown:'Submission unknown',failed:'Failed',ready_for_review:'Ready for review',skipped:'Skipped',active:'In progress',unrecorded:'Outcome not recorded'};
function resetActivity(){
 ++state.activityRequest;state.activity={period:'7d',offset:0,limit:25};
 for(const id of ['activity-metrics','activity-outcomes','activity-attempt-rows'])$(id).replaceChildren();
 $('activity-cohort').textContent='Open Activity to load results.';$('activity-page').textContent='';$('activity-custom').hidden=true;
 $('activity-prev').disabled=true;$('activity-next').disabled=true;$('activity-title').closest('section').setAttribute('aria-busy','false');
}
function renderActivity(stats){
 const number=n=>Number(n).toLocaleString(),rate=n=>n==null?'—':n.toFixed(1)+'%';
 const ids=stats.attempt_ids,span=ids.first==null?'':ids.first===ids.last?` · Attempt #${ids.first}`:` · Attempt IDs #${ids.first}–${ids.last} (range)`;
 const dates=stats.start_date?(stats.start_date===stats.end_date?stats.start_date:`${stats.start_date} through ${stats.end_date}`):`All history through ${stats.end_date}`;
 $('activity-cohort').textContent=`${dates} · ${stats.timezone}${span} · Updated ${stamp(stats.as_of)}`;
 $('activity-metrics').replaceChildren();
 for(const [value,label] of [[number(stats.attempts),'Application attempts'],[number(stats.dispatches),'Queue dispatches'],[number(stats.jobs),'Distinct jobs'],
  [number(stats.submitted_jobs??stats.outcomes.applied??0),'Jobs with new submissions'],[rate(stats.submission_rate_per_attempt),'New submissions / attempts'],[rate(stats.submission_rate_per_job),'Jobs with new submission / jobs']]){
  const metric=el('div',undefined,'stat');metric.append(el('strong',value),el('span',label));$('activity-metrics').append(metric);
 }
 $('activity-outcomes').replaceChildren();
 const keys=[...Object.keys(ACTIVITY_OUTCOMES),...Object.keys(stats.outcomes).filter(k=>!(k in ACTIVITY_OUTCOMES))];
 for(const key of keys){const count=stats.outcomes[key]||0;if(!count)continue;
  const row=el('div',undefined,'activity-outcome');row.append(badge(ACTIVITY_OUTCOMES[key]||key),el('strong',number(count)),el('span',`${(100*count/stats.attempts).toFixed(1)}% of attempts`,'muted'));$('activity-outcomes').append(row);
 }
 if(!stats.attempts)$('activity-outcomes').append(el('p','No attempts started in this period.','muted'));
 $('activity-attempt-rows').replaceChildren();
 for(const a of stats.recent_attempts){
  const row=el('tr'),cell=el('td'),button=el('button','#'+a.id);button.onclick=()=>{loadAttempt(a.id);$('attempt-summary').scrollIntoView?.({behavior:'smooth',block:'start'});};cell.append(button);
  const job=el('td');job.append(el('strong',a.company||'Company not recorded'),el('div',a.title||'Title not recorded'));
  const result=el('td');result.append(badge(ACTIVITY_OUTCOMES[a.outcome]||a.outcome));
  row.append(cell,job,el('td',stamp(a.started_at)),result);$('activity-attempt-rows').append(row);
 }
 $('activity-prev').disabled=stats.offset===0;
 $('activity-next').disabled=stats.offset+stats.limit>=stats.attempts;
 $('activity-page').textContent=stats.attempts?`${number(stats.offset+1)}–${number(Math.min(stats.offset+stats.recent_attempts.length,stats.attempts))} of ${number(stats.attempts)} attempts`:'0 attempts';
}
async function loadActivity(){
 const ticket=++state.activityRequest,selection={...state.activity};
 if(selection.period==='custom'&&(!selection.start_date||!selection.end_date))return;
 $('activity-title').closest('section').setAttribute('aria-busy','true');
 try{const stats=await api('activity_stats',selection);if(ticket!==state.activityRequest)return;
  if(stats.offset>=stats.attempts&&stats.offset>0){state.activity.offset=0;return await loadActivity();}
  renderActivity(stats);
 }catch(error){if(ticket!==state.activityRequest)return;
  for(const id of ['activity-metrics','activity-outcomes','activity-attempt-rows'])$(id).replaceChildren();
  $('activity-cohort').textContent='Results unavailable: '+error.message;$('activity-page').textContent='';$('activity-prev').disabled=true;$('activity-next').disabled=true;
 }finally{if(ticket===state.activityRequest)$('activity-title').closest('section').setAttribute('aria-busy','false');}
}
$('activity-period').onchange=async()=>{
 ++state.activityRequest;state.activity={period:$('activity-period').value,offset:0,limit:25};
 const custom=state.activity.period==='custom';$('activity-custom').hidden=!custom;
 if(custom){$('activity-cohort').textContent='Choose a start and end date, then show results.';for(const id of ['activity-metrics','activity-outcomes','activity-attempt-rows'])$(id).replaceChildren();$('activity-page').textContent='';$('activity-prev').disabled=true;$('activity-next').disabled=true;$('activity-title').closest('section').setAttribute('aria-busy','false');return;}
 await loadActivity();
};
$('activity-custom').onsubmit=async event=>{event.preventDefault();
 const start=$('activity-from').value,end=$('activity-to').value;
 if(!start||!end||start>end){notice('Choose an end date on or after the start date.',true);return;}
 state.activity={period:'custom',start_date:start,end_date:end,offset:0,limit:25};await loadActivity();
};
$('activity-prev').onclick=async()=>{state.activity.offset=Math.max(0,state.activity.offset-state.activity.limit);await loadActivity();};
$('activity-next').onclick=async()=>{state.activity.offset+=state.activity.limit;await loadActivity();};

function renderRun(v){
 choice('run-picker',v.runs.map(r=>[r.id,`${stamp(r.requested_at)} · ${r.state}`]),state.run||v.current_run?.run_id);
 const r=v.current_run;$('run-counts').replaceChildren();$('attempts').replaceChildren();
 const done=!!r&&(r.state==='completed'||(r.selected>0&&r.completed===r.selected&&!r.remaining&&!r.current));
 document.querySelectorAll('[data-control]').forEach(b=>b.disabled=!r||done);
 if(!r){$('run-state').textContent='No run selected.';$('run-owner').textContent='';return;}
 const activeAttempt=r.attempts?.find(a=>!a.completed_at);
 const leaseSec=v.settings?.values?.lease_seconds||60;
 const localSession=v.local_runtime?.sessions.find(s=>s.run_id===r.run_id);
 const connected=localSession?(!done&&localSession.host_alive&&localSession.driver_recently_active):(!done&&!!activeAttempt&&activeAttempt.heartbeat_age_seconds!==null&&activeAttempt.heartbeat_age_seconds<=leaseSec&&activeAttempt.writer_state!=='expired');
 $('run-state').replaceChildren(badge(done?'Completed':r.state));
 if(done){
  $('run-state').append(document.createTextNode(' — No active application worker.'));
 } else if(r.control==='stop_requested'){
  const b=badge('Stop request pending');b.dataset.state='stop_requested';
  $('run-state').append(b,document.createTextNode(connected?' — awaiting worker acknowledgement.':' — worker disconnected; no acknowledgement.'));
 } else if(r.control==='pause_requested'){
  const b=badge('Pause request pending');b.dataset.state='pause_requested';
  $('run-state').append(b,document.createTextNode(' — acknowledgement pending.'));
 } else if(connected) {
  $('run-state').append(badge(r.control));
 }
 if(r.state==='awaiting_worker'){
  $('run-state').append(document.createTextNode(' — Waiting for worker acceptance.'));
 } else if(localSession&&!done){
  $('run-state').append(document.createTextNode(` · Host ${localSession.host_alive?'running':'offline'}; driver ${localSession.driver_recently_active?'recently active':'idle or disconnected'}`));
 } else if(activeAttempt && (activeAttempt.heartbeat_age_seconds>leaseSec || activeAttempt.writer_state==='expired')){
  const dis=badge('Worker disconnected / not running');dis.dataset.state='stalled';
  $('run-state').append(document.createTextNode(' · '),dis);
 }
 for(const [key,label]of [['selected','Selected'],['completed','Processed'],['applied','Applied'],['blocked','Blocked / uncertain'],['current','Active'],['remaining','Remaining']]){const n=el('div',undefined,'stat');n.append(el('strong',r[key]),el('span',label));$('run-counts').append(n);}
 let requestedSettings={};try{requestedSettings=JSON.parse(r.settings_json||'{}');}catch{}
 const reqModel=requestedSettings.reasoning_model||r.settings?.reasoning_model||'—';
 const reqEffort=r.requested_reasoning_effort||v.settings?.values?.reasoning_effort||'low';
 const verifiedEffort=r.actual_reasoning_effort||r.observed_reasoning_effort||'—';
 const actualModel=r.focused_context?.worker_metadata?.model;
 const workerInfo=actualModel?`${connected?'Connected worker':'Last worker'}: ${actualModel} · verified effort ${verifiedEffort}`:'Model execution not yet verified';
 $('run-owner').textContent=`Requested: ${reqModel} (${reqEffort}) | ${workerInfo}`;
 if(r.state!=='awaiting_worker'&&$('notice').textContent.startsWith('Application run started;'))notice('');
 rememberProgress($('focused-context'));$('focused-context').replaceChildren();const focused=r.focused_context;
 if(focused){
  $('focused-context').append(el('p',focused.is_active?'Current job':'Last completed job'),postingHeading(focused.job));
  const progress=renderProgress(focused.progress,'focus:'+focused.attempt_id),debug=progress.querySelector('.debug-details');
  debug.append(el('p',`Page: ${focused.page||'Unknown'} · Activity: ${focused.activity||'Unknown'}`),el('pre',JSON.stringify(focused.worker_metadata,null,2)));
  if(focused.latest_unresolved_issue)debug.append(el('p',focused.latest_unresolved_issue));$('focused-context').append(progress);
 }
 $('target-list').replaceChildren();for(const t of r.targets||[]){const n=el('p');n.append(badge(t.state),document.createTextNode(` · attempt ${t.attempt_id} · ${t.target_id} · `),link(t.url,t.url));$('target-list').append(n);}
 $('extension-list').replaceChildren();for(const e of r.budget_extensions||[])$('extension-list').append(el('p',`Attempt ${e.attempt_id}: +${e.seconds}s · ${e.reason} · ${stamp(e.created_at)}`));
 for(const a of r.attempts){
  const n=el('div',undefined,'attempt');const b=el('button',`Attempt ${a.id}`);b.onclick=()=>loadAttempt(a.id);n.append(b,badge(a.outcome||'active'),document.createTextNode(' '+duration(a.elapsed_seconds)));
  n.append(el('small',`Heartbeat ${duration(a.heartbeat_age_seconds)} ago · verified progress ${duration(a.progress_age_seconds)} ago · writer ${a.writer_state}`));if(a.stalled)n.append(badge('stalled'));if(a.over_target)n.append(el('p','Target exceeded — bounded extension or intervention required.'));
  const evidence=a.confirmation_evidence||a.evidence;
  if(a.failure_reason){
    n.append(el('div',`Reason: ${a.failure_reason}`,'attempt-reason'));
  }
  if(evidence||a.outcome==='applied'||a.outcome==='completed'){
   n.append(el('div',`${a.outcome==='applied'?'Employer confirmation':'Outcome details'}: ${evidence||'No confirmation evidence recorded'}`,'verified-evidence'));
  }
  $('attempts').append(n);
 }
}
function renderPortalAccounts(v){
 const query=$('account-search').value.trim().toLowerCase();
 const accounts=v.accounts.filter(a=>[a.namespace,a.portal_key,a.company_key,a.email,a.identity_id].some(value=>String(value||'').toLowerCase().includes(query)));
 $('account-search-count').textContent=`${accounts.length} of ${v.accounts.length} accounts`;
 $('account-rows').replaceChildren();for(const a of accounts){const tr=el('tr');tr.append(el('td',a.namespace||a.portal_key||a.company_key),el('td',a.identity_id?(a.email||a.identity_id):'Legacy / unresolved'),el('td',a.status||'unknown'),el('td',stamp(a.last_confirmed_at)));
 const source=({override:'Custom password',default:'Default password',saved:'Saved credential',unavailable:'Unavailable'})[a.password_source]||'Unavailable';tr.append(el('td',source));
 const action=el('td');if(a.password_editable){const button=el('button',a.password_source==='override'?'Update override':'Set password override');button.type='button';button.onclick=()=>openPortalPassword(a);action.append(button);}else action.textContent=a.identity_id?'Private credentials unavailable':'Account identity unresolved';tr.append(action);$('account-rows').append(tr);}
 if(!accounts.length){const row=el('tr'),cell=el('td',v.accounts.length?'No portal accounts match your search. Try another site name, address or account email.':'No tracked portal accounts yet. Accounts appear as Jobot encounters employer sign-in or registration.');cell.colSpan=6;row.append(cell);$('account-rows').append(row);}
}
$('account-search').oninput=()=>{if(state.view)renderPortalAccounts(state.view);};
$('account-search-clear').onclick=()=>{$('account-search').value='';if(state.view)renderPortalAccounts(state.view);$('account-search').focus();};
function renderAccounts(v){renderPortalAccounts(v);
 $('history').replaceChildren();for(const r of v.runs){const n=el('p');const b=el('button',`${stamp(r.requested_at)} · ${r.state}`);b.onclick=async()=>{state.run=r.id;await tab('run');await refresh();};n.append(b,document.createTextNode(' '+r.id));$('history').append(n);}}
let portalPasswordAccount=null,portalPasswordSaving=false;
function openPortalPassword(account){
 portalPasswordAccount=account.id;$('portal-password-form').reset();$('portal-password-error').textContent='';
 $('portal-password-account').textContent=`${account.namespace} · ${account.email||account.identity_id}`;
 $('remove-portal-password').hidden=account.password_source!=='override';$('portal-password-fallback').hidden=account.password_source!=='override';
 $('portal-password-dialog').showModal();$('portal-password').focus();
}
function closePortalPassword(){if(!portalPasswordSaving)$('portal-password-dialog').close();}
$('close-portal-password').onclick=closePortalPassword;
$('portal-password-dialog').addEventListener('cancel',e=>{if(portalPasswordSaving)e.preventDefault();});
$('portal-password-dialog').addEventListener('close',()=>{$('portal-password-form').reset();$('portal-password-account').textContent='';$('portal-password-error').textContent='';portalPasswordAccount=null;});
async function changePortalPassword(remove=false){
 if(portalPasswordSaving||portalPasswordAccount===null)return;
 if(!remove&&$('portal-password').value!==$('portal-password-confirm').value){$('portal-password-error').textContent='Passwords do not match.';return;}
 portalPasswordSaving=true;for(const id of ['save-portal-password','remove-portal-password','close-portal-password'])$(id).disabled=true;
 $('portal-password-error').textContent='';
 try{
  const payload={account_id:portalPasswordAccount};if(!remove)payload.password=$('portal-password').value;
  await api(remove?'remove_portal_password':'set_portal_password',payload);
  $('portal-password-dialog').close();notice(remove?'Password override removed. Jobot will use the previously configured credential.':'Password override saved for this portal.');await refresh();
 }catch(error){$('portal-password-error').textContent=({password_required:'Enter a password.',credential_profile_not_configured:'The runtime has no private credential file configured.',credential_profile_unavailable:'The private credential file could not be read.',credential_profile_write_failed:'The private credential file could not be saved.',local_lock_busy:'Another password update is being saved. Please try again.',account_identity_unresolved:'This account does not yet have a resolved candidate and portal.',candidate_credential_identity_mismatch:'The account email does not match the candidate.'})[error.message]||'Could not update the password override. Please try again.';}
 finally{portalPasswordSaving=false;for(const id of ['save-portal-password','remove-portal-password','close-portal-password'])$(id).disabled=false;}
}
$('portal-password-form').onsubmit=async e=>{e.preventDefault();await changePortalPassword();};
$('remove-portal-password').onclick=()=>changePortalPassword(true);
function renderResources(v){
 $('lesson-list').replaceChildren();for(const lesson of v.lessons||[]){const row=el('div',undefined,'event');row.append(el('strong',lesson.condition),el('p',lesson.action),badge(lesson.status),el('p',JSON.stringify(lesson.scope)));for(const status of ['active','demoted','retired']){const b=el('button',status==='active'?'Activate':status==='demoted'?'Demote':'Retire');b.disabled=lesson.kind!=='procedure'||lesson.status===status;b.onclick=async()=>{const reason=prompt('Verification or transition reason:');if(!reason)return;try{await api('lesson_set_status',{lesson_id:lesson.id,status,reason});await refresh();}catch(e){notice(e.message,true);}};row.append(b);}const history=el('details');history.append(el('summary',`${(lesson.history||[]).length} verification/history records`));for(const h of lesson.history||[])history.append(el('p',`${stamp(h.created_at)} · ${h.success===null?h.status:h.success?'verified':'failed'} · ${h.reason}`));row.append(history);$('lesson-list').append(row);}if(!v.lessons?.length)$('lesson-list').append(el('p','No observations recorded.'));
 $('helper-list').replaceChildren();for(const helper of v.helpers||[]){const row=el('div',undefined,'event');row.append(el('strong',helper.helper_id+' · '+helper.version),el('p',helper.capability),badge(helper.status),el('p',helper.path,'mono'));const b=el('button','Activate verified version');b.disabled=helper.status==='active';b.onclick=async()=>{const verification_evidence=prompt('Verification evidence reference:');if(!verification_evidence)return;try{await api('helper_activate',{helper_id:helper.helper_id,version:helper.version,verification_evidence});await refresh();}catch(e){notice(e.message,true);}};row.append(b);$('helper-list').append(row);}if(!v.helpers?.length)$('helper-list').append(el('p','No helper versions registered.'));
 $('asset-list').replaceChildren();for(const asset of v.assets||[]){const row=el('div',undefined,'event');row.append(el('strong',asset.kind+' · '+asset.version),badge(asset.status),el('p',asset.identity_id+' · '+asset.storage_ref,'mono'),el('p',asset.sha256,'mono'));for(const selection of v.document_selections||[])if(selection.asset_id===asset.id)row.append(el('p',`Selected for ${selection.job_id}${selection.attempt_id?' · attempt '+selection.attempt_id:''}`));for(const upload of v.document_uploads||[])if(upload.asset_id===asset.id)row.append(el('p',`${upload.status} · attempt ${upload.attempt_id} · ${stamp(upload.created_at)}`));$('asset-list').append(row);}if(!v.assets?.length)$('asset-list').append(el('p','No document metadata registered.'));
 $('assessment-list').replaceChildren();for(const a of v.assessments||[]){const row=el('div',undefined,'event');row.append(el('strong',a.recommendation),el('p',a.score===null?'Unassessed':`${a.score} on scale ${a.scale_min}–${a.scale_max}; not a probability`),el('p',`${a.evaluator} / ${a.model} · ${stamp(a.evaluated_at)}`),el('p',(a.reasons||[]).join('; ')));$('assessment-list').append(row);}if(!v.assessments?.length)$('assessment-list').append(el('p','No external assessments registered.'));
 choice('asset-identity',[['','Select candidate'],...v.candidates.filter(c=>c.state==='active').map(c=>[c.id,c.email+' · '+c.id])]);choice('select-asset',[['','Select version'],...(v.assets||[]).map(a=>[a.id,a.identity_id+' · '+a.kind+' '+a.version])]);choice('select-asset-job',[['','Select job'],...v.jobs.map(j=>[j.id,j.title||j.id])]);
}
async function loadModelCatalog(refresh=false){
 if(state.modelCatalogLoading)return;
 state.modelCatalogLoading=true;$('refresh-models').disabled=true;
 $('model-catalog-status').textContent='Loading models from the executor…';
 try{state.modelCatalog=await api('model_catalog',{refresh});}
 catch{state.modelCatalog={executor:state.view?.local_runtime?.workspaces?.length?'unknown':'external',status:'unavailable',providers:[]};}
 finally{state.modelCatalogLoading=false;$('refresh-models').disabled=false;renderModelSelection();}
}
function renderModelSelection(){
 if(!state.modelDraft)return;
 const catalog=state.modelCatalog||{},draft=state.modelDraft;
 const local=state.view?.local_runtime?.workspaces?.length||['hermes_desktop','hermes_cli'].includes(catalog.executor);
 const inherits=local&&!draft.override;
 const providers=catalog.providers||[];
 const options=[['','Use executor default'],...providers.map(p=>[p.id,p.name]),['__manual__','Custom…']];
 const selected=draft.manual?'__manual__':inherits||!draft.provider?'':providers.some(p=>p.id===draft.provider)?draft.provider:'__manual__';
 choice('settings-provider',options,selected);
 $('settings-custom-provider').value=draft.provider||'';
 $('settings-custom-model').value=draft.model||'';
 $('settings-effort').value=draft.effort||'low';
 $('settings-worker-label').hidden=Boolean(local);
 $('model-executor-note').textContent=local
  ?`Worker: ${catalog.executor==='hermes_cli'?'Hermes CLI':catalog.executor==='hermes_desktop'?'Hermes Desktop':'configured application executor'}. The runtime selects this worker; model choices come from its configured providers.`
  :'Worker selects the application executor. Provider and model request a matching worker; Custom accepts the IDs configured in that worker.';
 const current=catalog.model?` Executor default: ${providers.find(p=>p.id===catalog.provider)?.name||catalog.provider} / ${catalog.model}.`:'';
 $('model-catalog-status').textContent=(catalog.status==='available'?'Models supplied by Hermes.':catalog.status==='unavailable'
  ?'Model list unavailable. Your selection is preserved; retry Refresh models or enter Custom IDs.'
  :catalog.status==='manual'?'This worker does not expose a model catalog. Use Custom IDs or its default.':'Loading available models…')+current;
 updateModelControls();
 renderTaskModelSettings();
}
function taskModelSummary(task){
 const draft=state.taskModelDraft?.[task];if(!draft)return;
 const app=state.modelDraft||{},catalog=state.modelCatalog||{};
 const shared=draft.mode==='same_application';
 const provider=shared?(app.override?app.provider:catalog.provider):draft.provider;
 const model=shared?(app.override?app.model:catalog.model):draft.model;
 const target=$(task+'-model-summary');
 if(target)target.textContent=`${shared?'Same as application model':'Separate model'}: ${provider&&model?provider+' / '+model:'executor default (not yet resolved)'}. Applies to the next ${task==='discovery'?'discovery run':'answer-learning or matching call'}.`;
}
function rememberTaskModelSelection(task){
 if(!$(task+'-model-mode'))return;
 const provider=$(task+'-provider').value,model=$(task+'-model').value;
 state.taskModelDraft[task]={mode:$(task+'-model-mode').value,
  provider:provider==='__manual__'?$(task+'-custom-provider').value.trim():provider,
  model:provider==='__manual__'||model==='__manual__'?$(task+'-custom-model').value.trim():model,
  effort:$(task+'-effort').value||'low',manual:provider==='__manual__'};
 taskModelSummary(task);
}
function renderTaskModelSettings(){
 const box=$('task-model-settings');if(!box||!state.taskModelDraft)return;
 box.replaceChildren();
 for(const task of ['discovery','learning']){
  const draft=state.taskModelDraft[task],providers=state.modelCatalog?.providers||[];
  box.append(el('h3',task==='discovery'?'Discovery model':'Answer learning model'));
  const modeLabel=el('label','Model choice'),mode=el('select');mode.id=task+'-model-mode';modeLabel.append(mode);box.append(modeLabel);
  choice(mode.id,[['same_application','Same as application model'],['separate','Separate model']],draft.mode);
  const fields=el('div',undefined,'settings-grid');fields.id=task+'-model-fields';fields.hidden=draft.mode!=='separate';box.append(fields);
  for(const [suffix,labelText,isInput] of [['provider','Provider'],['model','Model'],['custom-provider','Custom provider',true],['custom-model','Model ID',true],['effort','Reasoning effort']]){
   const label=el('label',labelText),input=el(isInput?'input':'select');label.id=task+'-'+suffix+'-label';input.id=task+'-'+suffix;label.append(input);fields.append(label);
  }
  const provider=draft.manual?'__manual__':providers.some(p=>p.id===draft.provider)?draft.provider:draft.provider?'__manual__':'';
  choice(task+'-provider',[['','Choose provider'],...providers.map(p=>[p.id,p.name]),['__manual__','Custom…']],provider);
  $(task+'-custom-provider').value=draft.provider||'';$(task+'-custom-model').value=draft.model||'';
  choice(task+'-effort',['low','medium','high','xhigh'].map(x=>[x,x]),draft.effort||'low');
  const summary=el('p');summary.id=task+'-model-summary';summary.setAttribute('role','status');box.append(summary);
  updateTaskModelControls(task);taskModelSummary(task);
  mode.onchange=()=>{draft.mode=mode.value;state.taskModelDraft[task].mode=mode.value;fields.hidden=mode.value!=='separate';taskModelSummary(task);};
  $(task+'-provider').onchange=()=>{
   state.taskModelDraft[task]={...state.taskModelDraft[task],provider:$(task+'-provider').value,model:''};
   $(task+'-custom-provider').value='';$(task+'-custom-model').value='';updateTaskModelControls(task);rememberTaskModelSelection(task);
  };
  $(task+'-model').onchange=()=>{rememberTaskModelSelection(task);updateTaskModelVisibility(task);};
  for(const suffix of ['custom-provider','custom-model','effort'])$(task+'-'+suffix).oninput=()=>rememberTaskModelSelection(task);
 }
}
function updateTaskModelControls(task){
 const draft=state.taskModelDraft[task],provider=$(task+'-provider').value;
 const row=state.modelCatalog?.providers?.find(p=>p.id===provider);
 const models=(row?.models||[]).map(m=>[m,m]);
 if(draft.model&&!models.some(m=>m[0]===draft.model))models.unshift([draft.model,draft.model+' (saved)']);
 models.push(['__manual__','Enter model ID…']);choice(task+'-model',models,draft.model);
 updateTaskModelVisibility(task);
}
function updateTaskModelVisibility(task){
 const provider=$(task+'-provider').value,model=$(task+'-model').value;
 $(task+'-model-label').hidden=!provider||provider==='__manual__';
 $(task+'-custom-provider-label').hidden=provider!=='__manual__';
 $(task+'-custom-model-label').hidden=!provider||(provider!=='__manual__'&&model!=='__manual__');
 const row=state.modelCatalog?.providers?.find(p=>p.id===provider);
 $(task+'-effort-label').hidden=!provider||row?.capabilities?.[model]?.reasoning===false;
}
function taskModelSettingsChanges(){
 const changes={};
 for(const task of ['discovery','learning']){
  rememberTaskModelSelection(task);const draft=state.taskModelDraft[task];
  if(draft.mode==='separate'&&(!draft.provider||!draft.model))throw Error(`Choose a provider and model for ${task}.`);
  changes[task+'_model_mode']=draft.mode;
  changes[task+'_provider']=draft.provider||null;changes[task+'_model']=draft.provider?(draft.model||null):null;
  changes[task+'_effort']=draft.effort;
 }
 return changes;
}
function updateModelControls(){
 const provider=$('settings-provider').value,draft=state.modelDraft;
 const row=state.modelCatalog?.providers?.find(p=>p.id===provider);
 const models=(row?.models||[]).map(m=>[m,m]);
 if(draft?.provider===provider&&draft.model&&!models.some(m=>m[0]===draft.model))models.unshift([draft.model,draft.model+' (saved)']);
 models.push(['__manual__','Enter model ID…']);
 choice('settings-model',models,draft?.provider===provider?draft.model:undefined);
 const manual=provider==='__manual__'||$('settings-model').value==='__manual__';
 $('settings-model-label').hidden=!provider||provider==='__manual__';
 $('settings-custom-provider-label').hidden=provider!=='__manual__';
 $('settings-custom-model-label').hidden=!provider||!manual;
 const model=manual?$('settings-custom-model').value:$('settings-model').value;
 $('settings-effort-label').hidden=!provider||row?.capabilities?.[model]?.reasoning===false;
}
function rememberModelSelection(){
 const provider=$('settings-provider').value;
 state.modelDraft={provider:provider==='__manual__'?$('settings-custom-provider').value.trim():provider,
  model:provider?((provider==='__manual__'||$('settings-model').value==='__manual__')?$('settings-custom-model').value.trim():$('settings-model').value):'',
  effort:$('settings-effort').value,override:Boolean(provider),manual:provider==='__manual__'};
 for(const task of ['discovery','learning'])taskModelSummary(task);
}
function modelSettingsChanges(){
 rememberModelSelection();const draft=state.modelDraft;
 if(draft.override&&(!draft.provider||!draft.model))throw Error('Choose a provider and model, or use the executor default.');
 return {reasoning_provider:draft.provider||null,reasoning_model:draft.model||null,
  reasoning_effort:draft.effort||'low',application_model_override:draft.override,...taskModelSettingsChanges()};
}
$('settings-provider').onchange=()=>{
 const provider=$('settings-provider').value;
 state.modelDraft={...state.modelDraft,provider,model:'',override:Boolean(provider)};
 $('settings-custom-provider').value=provider==='__manual__'?'':provider;
 $('settings-custom-model').value='';$('settings-model').value='';updateModelControls();rememberModelSelection();
};
$('settings-model').onchange=()=>{const manual=$('settings-model').value==='__manual__';
 $('settings-custom-model-label').hidden=!manual;rememberModelSelection();
 const row=state.modelCatalog?.providers?.find(p=>p.id===$('settings-provider').value);
 $('settings-effort-label').hidden=row?.capabilities?.[state.modelDraft.model]?.reasoning===false;
};
for(const id of ['settings-custom-provider','settings-custom-model','settings-effort'])$(id).oninput=rememberModelSelection;
$('refresh-models').onclick=()=>{rememberModelSelection();loadModelCatalog(true);};
function renderSettings(s){
 $('settings-version').textContent=`Version ${s.version}`;
 if(state.settingsVersion===s.version)return;state.settingsVersion=s.version;
 const limit=s.values.application_time_limit_minutes??30;
 $('settings-time-limit-enabled').checked=limit>0;
 $('settings-time-limit-minutes').value=limit||30;
 $('settings-time-limit-minutes').disabled=limit===0;
 $('settings-concurrency').value=s.values.application_concurrency??1;
 state.modelDraft={provider:s.values.reasoning_provider,model:s.values.reasoning_model,
  effort:s.values.reasoning_effort,override:s.values.application_model_override};
 state.taskModelDraft={};
 for(const task of ['discovery','learning'])state.taskModelDraft[task]={
  mode:s.values[task+'_model_mode']||'same_application',provider:s.values[task+'_provider'],
  model:s.values[task+'_model'],effort:s.values[task+'_effort']||'low'};
 choice('settings-worker',(s.supported?.worker||['external','hermes']).map(x=>[x,x]),s.values.worker);
 choice('settings-effort',(s.supported?.reasoning_effort||['low','medium','high','xhigh']).map(x=>[x,x]),s.values.reasoning_effort);
 renderModelSelection();
 if(!state.modelCatalog)loadModelCatalog();
 const modelPicker=$('main-model-picker');
 if(modelPicker){
  const models=[['gpt-5.6-luna','Luna (gpt-5.6-luna)'],['gpt-5.6-terra','Terra (gpt-5.6-terra)']];
  const curModel=s.values.reasoning_model;
  if(curModel&&!models.some(m=>m[0]===curModel))models.push([curModel,curModel]);
  choice('main-model-picker',models,curModel||'gpt-5.6-luna');
 }
 if($('main-effort-picker'))$('main-effort-picker').value=s.values.reasoning_effort||'low';
 if($('main-submission-mode'))$('main-submission-mode').value=s.values.submission_mode||'review';
 if($('main-browser-mode'))$('main-browser-mode').value=s.values.browser_mode||'headed';
 const box=$('setting-fields');box.replaceChildren();const discoveryBox=$('discovery-setting-fields');discoveryBox?.replaceChildren();
 const discoveryLabels={discovery_batch_size:'Maximum jobs per discovery run',discovery_interval_hours:'Discover jobs every (hours)'};
 for(const [key,value]of Object.entries(s.values)){const label=el('label',key==='duplicate_matching_mode'?'Duplicate jobs':discoveryLabels[key]||key.replaceAll('_',' '));let input;
  if(['worker','reasoning_provider','reasoning_model','reasoning_effort','application_model_override','application_time_limit_minutes','application_concurrency'].includes(key))continue;
  if(['discovery','learning'].some(task=>['model_mode','provider','model','effort'].some(field=>key===task+'_'+field)))continue;
  if(s.supported?.[key]){input=el('select');for(const x of s.supported[key]){const name=key==='duplicate_matching_mode'?({off:'Off',shadow:'Show matches only',enforce:'Skip applied or canceled duplicates'})[x]:x;const o=el('option',name);o.value=x;input.append(o);}input.value=value;}
  else {input=el('input');if(typeof value==='boolean'){input.type='checkbox';input.checked=value;}else if(typeof value==='number'){input.type='number';input.value=value;const range=s.budget_ranges?.[key];if(range){input.min=range[0];input.max=range[1];}}else{input.type='text';input.value=Array.isArray(value)?value.join(', '):(value??'');}}
  if(key==='discovery_batch_size'){input.min=1;input.max=100;input.step=1;}
  if(key==='discovery_interval_hours'){input.min=1;input.max=168;input.step='any';}
  input.dataset.setting=key;input.dataset.kind=Array.isArray(value)?'list':(value===null?'nullable':typeof value);label.append(input);(discoveryLabels[key]&&discoveryBox?discoveryBox:box).append(label);
 }
}
function profileValue(profile,path){return path.split('.').reduce((v,k)=>v&&typeof v==='object'?v[k]:undefined,profile);}
function setProfileValue(profile,path,value){const keys=path.split('.');let at=profile;for(const key of keys.slice(0,-1)){if(!at[key]||typeof at[key]!=='object'||Array.isArray(at[key]))at[key]=key==='work_authorization'&&typeof at[key]==='string'?{status:at[key]}:{};at=at[key];}at[keys.at(-1)]=value;}
function profileDraft(){const data=JSON.parse($('profile-json').value);if(!data||typeof data!=='object'||Array.isArray(data))throw Error('Profile JSON must be an object.');return data;}
function profileDisplay(value){return value===true?'Yes':value===false?'No':value===null||value===undefined||value===''?'Not answered':String(value);}
function profileFieldValue(profile,field){let value=profileValue(profile,field.path);if(field.path==='work_authorization.status'&&typeof profile.work_authorization==='string')value=profile.work_authorization;if(value===null||value===undefined){const values=(field.mirrors||[]).map(path=>profileValue(profile,path)).filter(v=>v!==null&&v!==undefined);if(values.length&&values.every(v=>v===values[0]))value=values[0];}if(field.path==='standard_answers.authorized_to_work_us'&&!Object.hasOwn(profile.standard_answers||{},'authorized_to_work_us')&&!Object.hasOwn(profile.work_authorization||{},'legally_authorized_us'))value=profile.standard_answers?.legally_authorized_to_work??value;return value;}
function editProfileField(field,value,source){
 const profile=profileDraft();setProfileValue(profile,field.path,value);for(const mirror of field.mirrors||[])setProfileValue(profile,mirror,value);
 state.profilePromotions??=new Map();if(source)state.profilePromotions.set(field.path,source);else state.profilePromotions.delete(field.path);
 $('profile-json').value=JSON.stringify(profile,null,2);$('profile-json-error').textContent='';state.profileDirty=true;return profile;
}
function renderProfileFields(profile,sections){
 const box=$('profile-question-sections'),open=new Map([...box.querySelectorAll('details[data-section]')].map(n=>[n.dataset.section,n.open]));box.replaceChildren();
 for(const section of sections||[]){
  const detail=el('details',undefined,'profile-section');detail.dataset.section=section.id;detail.open=open.get(section.id)??section.id==='screening';
  const answered=section.fields.filter(f=>![undefined,null,''].includes(profileFieldValue(profile,f))).length;
  const summary=el('summary');summary.append(el('span',section.title),el('small',`${answered} of ${section.fields.length} answered${section.optional?' · Optional':''}`));detail.append(summary);
  const grid=el('div',undefined,'profile-fields');
  for(const field of section.fields){
   const label=el('label',undefined,'profile-field');label.append(el('span',field.label));let input;const value=profileFieldValue(profile,field);
   if(field.kind==='boolean'){input=el('select');for(const [val,text] of [['','Not answered'],['true','Yes'],['false','No']]){const option=el('option',text);option.value=val;input.append(option);}input.value=typeof value==='boolean'?String(value):'';}
   else if(field.kind==='number'){input=el('input');input.type='number';input.step='any';if(field.min!==undefined)input.min=field.min;if(field.max!==undefined)input.max=field.max;input.value=typeof value==='number'?value:'';input.placeholder='Not answered';}
   else{input=el('textarea');input.rows=2;input.value=value??'';input.placeholder='Not answered';}
   input.id='profile-field-'+field.path.replaceAll('.','-');input.dataset.profileField=field.path;input.dataset.profileKind=field.kind;
   const source=profile.profile_answer_sources?.[field.path],evidence=el('small',source?`${source.source_type==='profile_edit'?'Updated in Profile':'From a saved answer'} · ${stamp(source.saved_at)}`:'','profile-field-source');if(source?.question)evidence.title=source.question;
   input.oninput=()=>{try{const answer=field.kind==='boolean'?(input.value===''?null:input.value==='true'):field.kind==='number'?(input.value===''?null:Number(input.value)):input.value;editProfileField(field,answer);evidence.textContent='Unsaved change';}catch{notice('Correct the Advanced Factual JSON before editing these questions.',true);}};
   label.append(input);if(field.help)label.append(el('small',field.help));label.append(evidence);grid.append(label);
  }
  detail.append(grid);box.append(detail);
 }
}
function renderProfileSuggestions(editor){
 const box=$('profile-suggestions');box.replaceChildren();const unique=new Map();
 for(const item of editor.suggestions||[]){if(item.status==='current')continue;const key=item.field+':'+JSON.stringify(item.value);if(!unique.has(key))unique.set(key,item);}
 if(!unique.size){box.append(el('p','Your compatible saved answers are already represented, or no new suggestions are available.','profile-suggestion-note'));return;}
 const detail=el('details',undefined,'profile-section profile-suggestion-section');detail.append(el('summary',`${unique.size} suggestions from saved answers`));
 detail.append(el('p','Choose answers to add to your profile, then save. Company and job-specific answers are kept separate.'));
 for(const item of unique.values()){
  const card=el('div',undefined,'profile-suggestion');card.append(el('strong',item.label));
  card.append(el('p',`Current: ${profileDisplay(item.current)} · Suggested: ${profileDisplay(item.value)}`));
  if(item.status==='conflict')card.append(el('small','Saved responses differ. Choose the response that applies now.','profile-conflict'));
  const source=el('details');source.append(el('summary',`Source: ${item.source_type==='answer_library'?'learned answer':'saved response'} · ${stamp(item.saved_at)}`),el('p',item.question));card.append(source);
  const use=el('button','Use saved answer');use.type='button';use.onclick=()=>{try{const field=editor.sections.flatMap(s=>s.fields).find(f=>f.path===item.field);const profile=editProfileField(field,item.value,{field:item.field,entry_id:item.entry_id,question_id:item.question_id,revision:item.revision});renderProfileFields(profile,editor.sections);use.textContent='Added to draft';notice('Answer added to the draft. Save profile to keep it.');}catch(error){notice(error.message,true);}};
  card.append(use);detail.append(card);
 }
 box.append(detail);
}
function profileSaveMessage(sync){return sync?.status==='synced'?' Saved to the database and private profile JSON.':sync?.status==='error'?' Saved to the database; private JSON sync needs attention.':' Saved to the database.';}
function renderProfileFileSync(sync){
 const box=$('profile-file-sync');box.replaceChildren();const status=sync?.status||'not_configured';
 box.append(el('span',({synced:'Saved profile is synced to the private JSON file.',not_configured:'Profile is stored in the database. Private JSON export is not configured for this candidate.',out_of_date:'The private JSON file needs syncing with the saved profile.',error:'The profile is saved in the database; the private JSON file could not be synced.'})[status]));
 if(['out_of_date','error'].includes(status)){const retry=el('button','Sync saved profile to JSON');retry.type='button';retry.onclick=async()=>{try{const result=await api('sync_profile_file',{identity_id:state.profileCandidate});renderProfileFileSync(result);notice(result.status==='synced'?'Saved profile synced to private JSON.':'Private JSON sync needs attention. The database profile remains saved.',result.status==='error');}catch(error){notice(error.message,true);}};box.append(retry);}
}
async function renderProfile(v){
 const candidates=v.candidates||[];
 if(!candidates.length){
  if(state.profileDirty)return;
  $('profile-candidate')?.replaceChildren();
  if($('profile-hash'))$('profile-hash').textContent='';
  if($('profile-id'))$('profile-id').textContent='';
  if($('profile-person-key'))$('profile-person-key').textContent='';
  if($('profile-email'))$('profile-email').value='';
  if($('profile-full-name'))$('profile-full-name').value='';
  if($('profile-work-auth'))$('profile-work-auth').value='';
  if($('profile-json'))$('profile-json').value='{}';
  $('profile-question-sections').replaceChildren();$('profile-suggestions').replaceChildren();$('profile-file-sync').replaceChildren();state.profileEditor=null;
  if($('profile-resume'))$('profile-resume').textContent='None';
  if($('main-resume-filename'))$('main-resume-filename').textContent='None registered';
  return;
 }
 const currentId=candidates.find(c=>c.id===state.profileCandidate)?.id||candidates.find(c=>c.id===v.dispatch_queue?.selection?.identity_id)?.id||candidates[0].id;
 state.profileCandidate=currentId;
 const knowledge=$('profile-knowledge');knowledge.replaceChildren();const learned=(v.answer_library?.entries||[]).filter(e=>e.identity_id===currentId&&e.state==='active'&&e.origin!=='legacy');
 knowledge.append(el('h3','Experience & application answers'),el('p',`${learned.length} reusable answers belong to this profile. These supplement your profile facts and keep their original sources, scope and reuse evidence.`));
 const browse=el('button','View this profile’s learned answers');browse.type='button';browse.onclick=()=>{state.learnedMode='current';state.learnedPage=0;state.learnedKey=null;$('learned-search').value=candidates.find(c=>c.id===currentId)?.email||currentId;renderLearnedAnswers(v);tab('learned');};knowledge.append(browse);
 const add=el('button','Add experience or preference');add.type='button';add.onclick=()=>editLibraryAnswer({identity_id:currentId});knowledge.append(add);
 choice('profile-candidate',candidates.map(c=>[c.id,`${c.email} (${c.id})`]),currentId);
 if(state.profileDirty)return;
 const requestId=state.profileRequest=(state.profileRequest||0)+1;
 try{
  const editor=await api('profile_editor',{identity_id:currentId});
  if(state.profileCandidate!==currentId||state.profileRequest!==requestId||state.profileDirty)return;
  if(state.profileEditor&&JSON.stringify(state.profileEditor)===JSON.stringify(editor))return;
  const cand=editor.candidate;
  if($('profile-id'))$('profile-id').textContent=cand.id;
  if($('profile-person-key'))$('profile-person-key').textContent=cand.person_key;
  if($('profile-hash'))$('profile-hash').textContent=`Hash: ${cand.profile_hash.slice(0,16)}...`;
  const prof=cand.profile||{};
  const idSec=prof.identity||{};
  if(!state.profileDirty){
   state.profileEditor=editor;state.profileHash=cand.profile_hash;state.profilePromotions=new Map();
   $('profile-email').value=cand.email;
   $('profile-full-name').value=idSec.full_name||'';
   const auth=prof.work_authorization??prof.facts?.work_authorization??'';
   $('profile-work-auth').value=typeof auth==='string'?auth:JSON.stringify(auth);
   $('profile-json').value=JSON.stringify(prof,null,2);
   $('profile-json-error').textContent='';renderProfileFields(prof,editor.sections);renderProfileSuggestions(editor);renderProfileFileSync(editor.file_sync);
  }
  const resume=cand.resume_asset?.provenance?.filename||(cand.resume_asset?.storage_ref?cand.resume_asset.storage_ref.split('/').pop():'None registered');
  if($('profile-resume'))$('profile-resume').textContent=resume;
  if($('main-resume-filename'))$('main-resume-filename').textContent=resume;
 }catch(err){
  notice(err.message,true);
 }
}

async function loadAttempt(id){state.attempt=id;try{const report=await api('attempt_report',{attempt_id:id});const a=report.attempt,t=report.timing;const loc=postingLabel(a);$('attempt-summary').textContent=`Attempt ${id}${loc?' · '+loc:''} · ${a.outcome||'active'} · ${duration(t.wall_seconds)} wall time · ${stamp(a.started_at)} → ${stamp(a.completed_at)}`;rememberProgress($('events'));$('events').replaceChildren(postingHeading(a));const projected=renderProgress(report.progress,'attempt:'+id);const debug=projected.querySelector('.debug-details');$('events').append(projected);
 const reasonText=a.failure_reason||report.failure_reason;
 if(reasonText){
  const p=el('p',undefined,'attempt-failure-prominent');
  const strong=el('strong','Reason: ');
  p.append(strong,document.createTextNode(reasonText));
  $('events').append(p);
 }
 debug.append(el('p',`Observed coverage ${duration(t.observed_union_seconds)}; unattributed ${duration(t.unattributed_seconds)}. Tool ${duration(t.category_seconds.tool)}; model ${duration(t.category_seconds.model)}. ${t.uncertainty?'Some timing is uncertain.':''}`),el('p',t.overlap_note));if(a.profile_hash)debug.append(el('p',`Attempt profile hash: ${a.profile_hash}`,'mono'));
 const table=el('table'),body=el('tbody');for(const phase of report.phases){const r=el('tr');r.append(el('td',phase.phase),el('td',duration(phase.duration_seconds)));body.append(r);}table.append(body);debug.append(table);
 if(report.fields&&Object.keys(report.fields).length){
  const fTable=el('table'),fBody=el('tbody');
  fBody.append(el('tr',undefined,undefined,[el('th','Field'),el('th','Elapsed'),el('th','Actions'),el('th','Status')]));
  for(const [k,f] of Object.entries(report.fields)){
   fBody.append(el('tr',undefined,undefined,[el('td',f.field_key),el('td',f.elapsed_seconds!=null?duration(f.elapsed_seconds):'unknown'),el('td',String(f.action_count)),el('td',f.verified?'verified':'unverified')]));
  }
  fTable.append(fBody);debug.append(el('h4','Field Telemetry'),fTable);
 }
 if(report.simplify&&report.simplify.runs_count){
  const s=report.simplify;
  debug.append(el('p',`Simplify runs: ${s.runs_count} · Total duration: ${duration(s.total_duration_seconds)}${s.fallback_reasons.length?' · Fallback reasons: '+s.fallback_reasons.join(', '):''}`));
 }
 if(report.problems&&report.problems.length){
  const pTable=el('table'),pBody=el('tbody');
  pBody.append(el('tr',undefined,undefined,[el('th','Category'),el('th','Field'),el('th','Fallback Reason'),el('th','Source'),el('th','Status'),el('th','Resolution')]));
  for(const p of report.problems){
   pBody.append(el('tr',undefined,undefined,[el('td',p.category||'-'),el('td',p.field_key||'-'),el('td',p.fallback_reason||'-'),el('td',p.source||'native'),el('td',p.status||'-'),el('td',p.resolution||'-')]));
  }
  pTable.append(pBody);debug.append(el('h4','Problems & Recoveries'),pTable);
 }
 for(const e of report.timeline){const row=el('details',undefined,'event');row.append(el('summary',`${stamp(e.observed_at)} · ${e.payload.activity||e.payload.evidence||e.event_type} · ${duration(e.duration_seconds)}${e.stale?' · late metadata':''}`),el('pre',JSON.stringify(e.payload,null,2)));debug.append(row);}if(!report.timeline.length)debug.append(el('p','No events recorded.'));}catch(e){notice(e.message,true);}}

function refresh(){
 if(!state.instance)return Promise.resolve();
 state.refreshRequested=true;
 if(state.refreshPromise)return state.refreshPromise;
 state.busy=true;
 // A save can finish while an older view is rendering. Fetch again before
 // resolving its refresh so callers see their mutation and current revisions.
 state.refreshPromise=(async()=>{try{do{state.refreshRequested=false;try{const v=await api('view',state.run?{run_id:state.run}:{});state.view=v;$('instance').textContent=`Instance ${v.health.instance_id} · DB ${v.health.db_path}`;$('mode').textContent=v.settings.values.mode+' / '+v.settings.values.submission_mode;$('mode').dataset.state=v.settings.values.mode;
 choice('candidate',v.candidates.filter(c=>c.state==='active').map(c=>[c.id,c.email]),$('candidate').value||v.dispatch_queue?.selection?.identity_id);
 if($('browser-profile')&&!$('browser-profile').value.trim()){
  $('browser-profile').value=v.current_run?.browser_profile||v.runs?.[0]?.browser_profile||'operator-chrome';
 }
 renderQueue(v);renderRun(v);renderAccounts(v);renderResources(v);renderSettings(v.settings);await renderProfile(v);$('health').textContent=JSON.stringify(v.health,null,2);if(!$('tab-run').hidden)await loadActivity();if(state.attempt)await loadAttempt(state.attempt);
 }catch(e){notice(e.message,true);}
 }while(state.refreshRequested&&state.instance);}finally{state.busy=false;state.refreshPromise=null;}})();
 return state.refreshPromise;
}
async function tab(name){$('workspace-title').textContent=({queue:'Applications',answers:'Needs your answer',learned:'Learned answers',run:'Activity',profile:'Your profile',settings:'Settings',accounts:'Accounts & history',knowledge:'Lessons & helpers',documents:'Document records'})[name]||'Workspace';document.querySelectorAll('.tab').forEach(n=>n.hidden=n.id!=='tab-'+name);document.querySelectorAll('[data-tab]').forEach(n=>n.classList.toggle('active',n.dataset.tab===name));for(const n of document.querySelectorAll('nav [data-tab]')){if(n.dataset.tab===name)n.setAttribute('aria-current','page');else n.removeAttribute('aria-current');}fitAnswerWorkspace();if(name==='run')await loadActivity();}
$('reconnect').onclick=()=>location.reload();
$('open-intake').onclick=()=>{$('intake-dialog').showModal();$('job-url').focus();};
$('close-intake').onclick=()=>$('intake-dialog').close();
$('job-detail-toggle').onclick=()=>{const expanded=$('jobs-panel').classList.toggle('expanded-columns');$('job-detail-toggle').setAttribute('aria-pressed',String(expanded));$('job-detail-toggle').textContent=expanded?'Show fewer columns':'Show all columns';};
for(const button of document.querySelectorAll('[data-overview-filter]'))button.onclick=()=>{$('job-filter').value=button.dataset.overviewFilter;filterJobs();};
$('refresh').onclick=refresh;document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>tab(b.dataset.tab));
function filterJobs(){rememberProgress($('queue-rows'));state.queueKey=null;state.selected.clear();if(state.view)renderQueue(state.view);}
$('job-filter').onchange=filterJobs;$('job-search').oninput=filterJobs;
for(const id of ['job-source-filter','job-country-filter','job-assessment-filter','job-added-from','job-added-to'])$(id).onchange=filterJobs;
$('job-reset-filters').onclick=()=>{
 for(const id of ['job-search','job-source-filter','job-country-filter','job-assessment-filter','job-added-from','job-added-to'])$(id).value='';
 $('job-filter').value='all';filterJobs();
};
for(const button of document.querySelectorAll('[data-job-sort]'))button.onclick=()=>{
 const key=button.dataset.jobSort;
 state.jobSort={key,direction:state.jobSort.key===key&&state.jobSort.direction==='asc'?'desc':'asc'};
 state.queueKey=null;if(state.view)renderQueue(state.view);
};
function editJobUrl(job){
 const form=$('job-url-form');form.dataset.jobId=job.id;form.dataset.expectedUrl=job.url||'';
 $('job-edit-url').value=job.url||'';$('job-url-label').textContent=(job.seq_id==null?'':'#'+job.seq_id+' · ')+postingLabel(job);
 $('job-url-error').textContent='';$('job-url-save').disabled=false;$('job-url-dialog').showModal();$('job-edit-url').focus();
}
$('job-url-cancel').onclick=()=>$('job-url-dialog').close();
$('job-url-form').onsubmit=async event=>{
 event.preventDefault();if($('job-url-save').disabled)return;
 const form=$('job-url-form');$('job-url-save').disabled=true;$('job-url-error').textContent='';
 try{
  await api('update_job_url',{job_id:form.dataset.jobId,url:$('job-edit-url').value.trim(),expected_url:form.dataset.expectedUrl});
  $('job-url-dialog').close();notice('Job URL saved. History and source references kept.');state.queueKey=null;await refresh();
 }catch(error){$('job-url-error').textContent=({job_url_changed:'This URL changed since the editor opened. Cancel and reopen it to use the latest value.',job_url_in_use:'That URL belongs to another saved job. Open that job to edit its link.',invalid_job_url:'Enter a valid http or https job URL.',sensitive_url:'Use the job posting URL, without sign-in codes or password-reset links.'})[error.message]||error.message;}
 finally{$('job-url-save').disabled=false;}
};
$('select-unfinished').onclick=()=>{state.selected=new Set(visibleJobs(state.view).filter(unfinished).map(j=>j.id));state.queueKey=null;renderQueue(state.view);};
$('select-visible').onclick=()=>{state.selected=new Set(visibleJobs(state.view).filter(j=>j.disposition==='canceled').map(j=>j.id));state.queueKey=null;renderQueue(state.view);};
$('clear-selection').onclick=()=>{state.selected.clear();state.queueKey=null;renderQueue(state.view);};
$('select-all-jobs').onchange=()=>{
 if(!$('select-all-jobs').checked)$('clear-selection').onclick();
 else $($('job-filter').value==='canceled'?'select-visible':'select-unfinished').onclick();
};
async function changeDisposition(disposition){
 const job_ids=state.view.jobs.filter(j=>state.selected.has(j.id)&&(disposition==='canceled'?unfinished(j):j.disposition==='canceled')).map(j=>j.id);
 if(!job_ids.length)return;
 try{
  const result=await api('set_job_disposition',{job_ids,disposition,reason:disposition==='canceled'?$('cancel-reason').value:''});
  state.selected.clear();state.queueKey=null;
  notice(disposition==='canceled'?`${result.jobs.length} job(s) canceled. History and portal accounts kept.${result.skipped_job_ids?.length?' Submitted or already canceled jobs were left unchanged.':''}${result.stop_requested_run_ids.length?' Stop requested for current work; browser shutdown is pending.':''}`:`${result.jobs.length} job(s) restored. Select and queue them when ready.`);
  await refresh();
 }catch(error){notice(error.message,true);}
}
$('cancel-selected').onclick=()=>changeDisposition('canceled');$('restore-selected').onclick=()=>changeDisposition('active');
if($('candidate'))$('candidate').onchange=()=>{if($('queue-resume'))$('queue-resume').value='';renderDispatcher(state.view);};
if($('queue-answered-batch'))$('queue-answered-batch').onclick=async()=>{
 try{const candidates=new Map();for(const group of state.view?.answer_queue?.groups||[]){if(!canQueueAnswers(group))continue;const jobs=candidates.get(group.identity_id)||[];jobs.push(group.job_id);candidates.set(group.identity_id,jobs);}
  let count=0;for(const [identity_id,job_ids] of candidates){await api('queue_answer_retries',{identity_id,job_ids});count+=job_ids.length;}
  notice(`${count} answered application${count===1?'':'s'} queued for the next batch.`);await refresh();
 }catch(error){notice(answerError(error),true);}
};
$('intake-form').onsubmit=async e=>{e.preventDefault();$('intake-error').textContent='';try{const job=await api('intake',{url:$('job-url').value,company:$('job-company').value,title:$('job-title').value,source_type:'manual',source_id:newRequestId(),producer:'dashboard'});
 for(const id of ['job-search','job-source-filter','job-country-filter','job-assessment-filter','job-added-from','job-added-to'])$(id).value='';state.selected.clear();state.queueKey=null;
 if(job.disposition==='canceled'){$('job-filter').value='canceled';notice('This job is already saved as canceled. Restore it here if you want to pursue it again.');}
 else if(submitted(job)){$('job-filter').value='submitted';notice('This job is already saved as submitted.');}
 else{$('job-filter').value='active';state.selected.add(job.id);notice('Job saved and selected. Choose Queue selected to apply.');}
 $('intake-form').reset();$('intake-dialog').close?.();await refresh();}catch(err){$('intake-error').textContent=err.message;}};
$('mark-ready').onclick=async()=>{try{if(!state.selected.size)throw Error('Select at least one job.');for(const id of state.selected)await api('eligibility',{job_id:id,decision:'ready',reason:'Explicit operator approval'});notice('Selected eligibility recorded.');await refresh();}catch(e){notice(e.message,true);}};
$('request-run').onclick=async()=>{try{if(!state.selected.size||!$('candidate').value||!$('browser-profile').value.trim())throw Error('Select jobs, candidate and exact browser profile.');const r=await api('request_run',{request_id:newRequestId(),job_ids:[...state.selected],identity_id:$('candidate').value,browser_profile:$('browser-profile').value.trim()});state.run=r.id;state.attempt=null;notice('Run requested; waiting for worker acceptance.');await tab('run');await refresh();}catch(e){notice(e.message,true);}};
if($('start-application-btn')){$('start-application-btn').onclick=async()=>{
 if(state.queueSubmitting)return;
 state.queueSubmitting=true;selection();
 const orderedIds=visibleJobs(state.view).filter(job=>state.selected.has(job.id)).map(job=>job.id);
 try{
 if(state.view?.local_runtime?.workspaces?.length){
  if(!state.selected.size)throw Error('Select at least one job.');
  const identity_id=$('candidate').value;
  const asset=(state.view.assets||[]).find(a=>a.id===$('queue-resume').value&&a.identity_id===identity_id&&a.kind==='resume'&&a.status==='available');
  if(!asset)throw Error('Choose a candidate with a registered resume.');
  const submission_mode=$('main-submission-mode').value;
  if(submission_mode!==state.view.settings.values.submission_mode)await api('configure',{changes:{submission_mode,mode:submission_mode==='submit'?'pilot':'development'},expected_version:state.settingsVersion});
  const result=await api('queue_enqueue',{job_ids:orderedIds,identity_id,resume_asset_id:asset.id,request_id:newRequestId(),retry:true,start_now:true,producer:'dashboard',enqueue_origin:'manual_enqueue'});
  state.selected.clear();notice(`${result.items.length} selected job(s) requested in table order. ${result.queue?.automation_paused?'Requests are saved until you choose Resume Jobot.':result.queue?.worker_online===false?'The worker is offline; requests are saved until it returns.':'The worker fills available application slots after earlier manual requests, ahead of automatic pickups.'}`);await refresh();return;
 }
 if(!state.selected.size)throw Error('Please select at least one job from the queue.');
 const candidateId=$('candidate').value;if(!candidateId)throw Error('Please select a candidate.');
 const browserProfile=($('browser-profile').value||'').trim()||'operator-chrome';
 const chosenModel=$('main-model-picker')?.value||'gpt-5.6-luna';
 const chosenEffort=$('main-effort-picker')?.value||'low';
 const chosenSubMode=$('main-submission-mode')?.value||'review';
 const chosenBrowserMode=$('main-browser-mode')?.value||'headed';
 const opMode=chosenSubMode==='submit'?'pilot':'development';
 await api('configure',{changes:{reasoning_provider:'openai-codex',reasoning_model:chosenModel,reasoning_effort:chosenEffort,submission_mode:chosenSubMode,mode:opMode,browser_mode:chosenBrowserMode},expected_version:state.settingsVersion});
 for(const id of state.selected){await api('eligibility',{job_id:id,decision:'ready',reason:'Operator approved start application'});}
 const r=await api('request_run',{request_id:newRequestId(),job_ids:orderedIds,identity_id:candidateId,browser_profile:browserProfile});
 state.run=r.id;state.attempt=null;notice('Application run started; waiting for worker acceptance.');await tab('run');await refresh();
}catch(err){notice(err.message,true);}finally{state.queueSubmitting=false;selection();}};}
$('queue-selected-jobs').onclick=()=>$('start-application-btn').onclick();
if($('queue-run-next'))$('queue-run-next').onclick=async()=>{try{const q=await api('queue_control',{command:'run_next'});notice(runNextMessage(q));await refresh();}catch(e){notice(e.message,true);}};
if($('queue-toggle'))$('queue-toggle').onclick=async()=>{try{await api('queue_control',{command:state.view?.dispatch_queue?.enabled?'pause':'resume'});await refresh();}catch(e){notice(e.message,true);}};
if($('automation-toggle'))$('automation-toggle').onclick=async()=>{
 const button=$('automation-toggle');if(button.disabled)return;button.disabled=true;
 try{const q=await api('queue_control',{command:state.view?.dispatch_queue?.automation_paused?'resume_all':'pause_all'});
  notice(q.automation_paused?'Pause saved. Current work finishes; new applications and discovery wait until you resume.':'Jobot resumed. Saved queue and discovery schedules are active again.');await refresh();
 }catch(e){notice(e.message,true);}finally{button.disabled=false;}
};
$('run-picker').onchange=()=>{state.run=$('run-picker').value;state.attempt=null;refresh();};
for(const b of document.querySelectorAll('[data-control]'))b.onclick=async()=>{try{const r=state.view?.current_run;if(!r)throw Error('No run selected.');await api('control',{run_id:r.run_id,command:b.dataset.control});notice('Control request recorded; observe acknowledgement.');await refresh();}catch(e){notice(e.message,true);}};
$('copy-handoff').onclick=async()=>{const r=state.view?.current_run;if(!r)return;const text=`Use the canonical job-apply skill to accept Jobot run ${r.run_id} in instance ${state.instance}; pull one job at a time and obey app controls.`;try{await navigator.clipboard.writeText(text);notice('Worker handoff copied.');}catch{notice(text);}};
$('settings-time-limit-enabled').onchange=()=>{$('settings-time-limit-minutes').disabled=!$('settings-time-limit-enabled').checked;};
$('settings-form').onsubmit=async e=>{e.preventDefault();try{const changes=modelSettingsChanges();changes.application_time_limit_minutes=$('settings-time-limit-enabled').checked?Number($('settings-time-limit-minutes').value):0;for(const n of document.querySelectorAll('[data-setting]')){const k=n.dataset.setting,kind=n.dataset.kind;changes[k]=kind==='boolean'?n.checked:kind==='number'?Number(n.value):kind==='list'?n.value.split(',').map(x=>x.trim()).filter(Boolean):kind==='nullable'?(n.value.trim()||null):n.value;}await api('configure',{changes,expected_version:state.settingsVersion});notice('Settings saved for new requests.');await refresh();}catch(err){notice(err.message,true);}};
(async()=>{try{const data=await request('/session',undefined,'GET');state.instance=data.instance_id;showConsole();await refresh();}catch{showLogin();}})();
$('helper-form').onsubmit=async e=>{e.preventDefault();try{const scope={};if($('helper-platform').value)scope.platform=$('helper-platform').value;if($('helper-namespace').value)scope.namespace=$('helper-namespace').value;await api('helper_register',{helper_id:$('helper-id').value,version:$('helper-version').value,capability:$('helper-capability').value,path:$('helper-path').value,sha256:$('helper-hash').value,scope,preconditions:[],limitations:[],tests:$('helper-tests').value.split('\n').filter(Boolean)});notice('Candidate helper version registered, not activated.');$('helper-form').reset();await refresh();}catch(err){notice(err.message,true);}};
$('asset-form').onsubmit=async e=>{e.preventDefault();try{await api('register_asset',{identity_id:$('asset-identity').value,kind:$('asset-kind').value,version:$('asset-version').value,storage_ref:$('asset-ref').value,sha256:$('asset-hash').value,provenance:{source:$('asset-source').value}});notice('External document metadata registered; not selected or uploaded.');$('asset-form').reset();await refresh();}catch(err){notice(err.message,true);}};
$('asset-select-form').onsubmit=async e=>{e.preventDefault();try{await api('select_asset',{asset_id:$('select-asset').value,job_id:$('select-asset-job').value});notice('Document selected for job; upload not yet confirmed.');await refresh();}catch(err){notice(err.message,true);}};
$('profile-form').oninput=()=>{state.profileDirty=true;};
$('profile-email').oninput=()=>{try{const profile=profileDraft();setProfileValue(profile,'identity.email',$('profile-email').value.trim());$('profile-json').value=JSON.stringify(profile,null,2);}catch{notice('Correct the Advanced Factual JSON before editing identity fields.',true);}};
$('profile-full-name').oninput=()=>{try{const profile=profileDraft();setProfileValue(profile,'identity.full_name',$('profile-full-name').value);$('profile-json').value=JSON.stringify(profile,null,2);}catch{notice('Correct the Advanced Factual JSON before editing identity fields.',true);}};
$('profile-json').onchange=()=>{try{const profile=profileDraft();$('profile-json-error').textContent='';$('profile-email').value=profile.identity?.email||state.profileEditor?.candidate.email||'';$('profile-full-name').value=profile.identity?.full_name||'';renderProfileFields(profile,state.profileEditor?.sections);}catch{$('profile-json-error').textContent='Correct the JSON to update the structured questions.';}};
$('profile-candidate').onchange=async()=>{state.profileDirty=false;state.profileEditor=null;state.profilePromotions=new Map();state.profileCandidate=$('profile-candidate').value;await renderProfile(state.view);};
$('profile-reload').onclick=async()=>{state.profileDirty=false;state.profileEditor=null;state.profilePromotions=new Map();await renderProfile(state.view);};
$('profile-form').onsubmit=async e=>{e.preventDefault();try{
 const prof=profileDraft();
 const email=$('profile-email').value.trim();
 if(!email||!email.includes('@'))throw Error('Valid email required');
 const idSec=prof.identity||{};idSec.email=email;idSec.full_name=$('profile-full-name').value.trim();prof.identity=idSec;
 if(!state.profileEditor)throw Error('Wait for the profile to load before saving.');
 const promotions=[...(state.profilePromotions?.values()||[])].filter(p=>{const source=state.profileEditor.suggestions.find(s=>s.field===p.field&&s.revision===p.revision&&(p.entry_id?s.entry_id===p.entry_id:s.question_id===p.question_id));return source&&JSON.stringify(source.value)===JSON.stringify(profileValue(prof,p.field));});
 const draft=$('profile-json').value,identity=state.profileCandidate;
 const r=await api('save_profile',{profile:prof,identity_id:identity,expected_profile_hash:state.profileHash,promotions});
 if(state.profileCandidate===identity){state.profileHash=r.candidate.profile_hash;state.profileDirty=$('profile-json').value!==draft;if(!state.profileDirty)state.profilePromotions=new Map();renderProfileFileSync(r.file_sync);}
 notice('Profile saved.'+profileSaveMessage(r.file_sync)+(state.profileDirty?' Your newer draft changes are still unsaved.':''),r.file_sync?.status==='error');
 await refresh();
}catch(err){notice(({profile_revision_conflict:'This profile changed elsewhere. Your draft is still here; reload the profile to review the latest saved answers.',profile_source_changed:'A selected saved answer changed. Your draft is still here; reload the profile to review its latest source.',identity_immutable:'Use Import to create a profile with a different email. The selected candidate’s email stays attached to its history.',invalid_profile_answer:'One profile answer has an invalid value. Check the structured fields and JSON.'})[err.message]||err.message,true);}};
$('profile-import-file').onchange=async e=>{
 const file=e.target.files?.[0];if(!file)return;
 const reader=new FileReader();
 reader.onload=async()=>{
  try{
   const raw=JSON.parse(reader.result);
   const {clean,skipped}=sanitizeLegacyClient(raw);
   $('profile-import-skipped').replaceChildren();
   if(skipped.length){
    $('profile-import-skipped').append(el('p','Skipped non-factual / excluded fields: '+skipped.join(', ')));
   }
   const res=await api('import_profile',{data:clean,identity_id:state.profileCandidate});
   state.profileDirty=false;
   state.profileCandidate=res.candidate.id;
   notice(`Imported profile for ${res.candidate.email}; ${skipped.length} excluded fields skipped.`+profileSaveMessage(res.file_sync),res.file_sync?.status==='error');
   e.target.value='';
   await refresh();
  }catch(err){notice(err.message,true);e.target.value='';}
 };
 reader.readAsText(file);
};
$('profile-resume-form').onsubmit=async e=>{
 e.preventDefault();
 const file=$('profile-resume-file').files?.[0];
 if(!file||!state.profileCandidate){notice('Candidate and resume file required.',true);return;}
 try{
  const buffer=await file.arrayBuffer();
  const url=`/v1/upload_asset?identity_id=${encodeURIComponent(state.profileCandidate)}&filename=${encodeURIComponent(file.name)}&kind=resume`;
  const res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/octet-stream','X-JobBot-Instance':state.instance},credentials:'same-origin',body:buffer});
  const data=await res.json();
  if(!res.ok)throw new Error(data.error||`HTTP ${res.status}`);
  notice(`Registered resume ${data.version} (${file.name}).`);
  $('profile-resume-file').value='';
  await refresh();
 }catch(err){notice(err.message,true);}
};
setInterval(()=>{if(state.instance&&!state.busy&&!document.hidden)refresh();},5000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&state.instance)refresh();});
