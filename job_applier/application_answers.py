"""Shared candidate answer preferences and private application answer history."""
import json
import math
import re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit

POLICY_KEYS={'salary_expectation','routine_privacy_consent','submission_evidence_sources'}


def reusable_answers(config,package,attempt_id,*,source):
    """Exact verified answers from authoritative same-candidate retry lineage."""
    if not config.get('spool_dir'):return {}
    folder=Path(config['spool_dir'])/'answers';result={}
    attempt=package.get('attempt',{});job=package['job']
    profile_hash=package.get('profile_hash') or attempt.get('profile_hash')
    prior=list(reversed(package.get('prior_attempts',{}).get('attempts',[])))
    for item in prior+[{'attempt_id':attempt_id,'job_id':job.get('id')}]:
        try:
            aid=int(item['attempt_id']);history=json.loads((folder/f'attempt-{aid}.json').read_text(encoding='utf-8'))
            if history['attempt_id']!=aid:continue
            if aid!=attempt_id:
                # Legacy journals inherit provenance only from this authoritative
                # candidate/posting attempt list, never from a filesystem scan.
                saved_profile=history.get('profile_hash') or item.get('profile_hash')
                if (not profile_hash or saved_profile!=profile_hash
                    or not attempt.get('identity_id') or history.get('identity_id',attempt['identity_id'])!=attempt['identity_id']
                    or history.get('job_id')!=item.get('job_id')):continue
            elif not (history.get('job_url')==job['url'] or job.get('id') and history.get('job_id')==job['id']
                      and history.get('identity_id')==attempt.get('identity_id')):continue
            for row in history['answers']:
                # Library snapshots are audit evidence; resolve their current entry.
                if str(row.get('answer_basis','')).startswith('answer_library:'):continue
                # Editable knowledge supersedes old form values, including retirement.
                from .managed_answer_library import matches
                if any(matches(e,{'question':row.get('question','')},job) for e in package.get('answer_library',[])):
                    continue
                if (row.get('source')==source and row.get('verified') is True and row.get('question_key')
                    and row.get('answer_basis') not in (None,'','not_recorded') and 'answer_value' in row):
                    from .managed_redaction import reject_secrets
                    reject_secrets(row)
                    result[row['question_key']]=row
        except (OSError,ValueError,KeyError,TypeError):continue
    return result


def save_answer_history(config,package,attempt_id,answers,*,page,source,basis=None):
    """Best-effort private journal; its failure cannot make a form write retryable."""
    try:return _save_answer_history(config,package,attempt_id,answers,page=page,source=source,basis=basis)
    except Exception as exc:return {'answer_history_error':type(exc).__name__}


def _save_answer_history(config,package,attempt_id,answers,*,page,source,basis=None):
    """Private question/answer history, separate from redacted operational telemetry."""
    from .managed_redaction import reject_secrets
    if not config.get('spool_dir'):return {}
    folder=Path(config['spool_dir'])/'answers'
    if not folder.is_absolute():raise ValueError('absolute_spool_required')
    path=folder/('attempt-'+str(int(attempt_id))+'.json')
    job=package['job'];attempt=package.get('attempt',{})
    history=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {
        'attempt_id':attempt_id,'session_id':attempt.get('local_session_id'),
        'identity_id':attempt.get('identity_id'),'profile_hash':package.get('profile_hash') or attempt.get('profile_hash'),
        'company':job.get('company'),'job_title':job.get('title'),'job_id':job.get('id'),
        'job_url':job['url'],'platform':package.get('platform'),
        'portal_namespace':package.get('namespace') or urlsplit(job['url']).hostname,'answers':[]}
    stable_job=job.get('id') and history.get('job_id')==job['id'] and history.get('identity_id')==attempt.get('identity_id')
    if history['attempt_id']!=attempt_id or not (stable_job or history['job_url']==package['job']['url']):
        raise ValueError('answer_history_scope_mismatch')
    metadata_changed=False
    for key,value in {'company':job.get('company'),'job_title':job.get('title'),
                      'company_source':job.get('company_source'),'session_id':attempt.get('local_session_id')}.items():
        if value and not history.get(key):history[key]=value;metadata_changed=True
    added=0
    for answer in answers:
        row={key:answer.get(key,'') for key in ('field','question','answer')}
        if any(not isinstance(v,str) or not v.strip() for v in row.values()):continue
        if re.search(r'password|passwd|\botp\b|(?:security|verification|authentication)[\s_-]*code|one[\s_-]?time|token|secret|social.?security|\bssn\b|tax.?id|bank.?account|routing.?number|credit.?card',row['question']+' '+row['field'],re.I):continue
        row.update(page=answer.get('page') or page,source=source,answer_basis=basis or 'not_recorded')
        if source in ('greenhouse_fast','icims_fast') and answer.get('verified') is True and answer.get('question_key'):
            row.update(verified=True,question_key=answer['question_key'],answer_value=answer.get('answer_value'),
                       answer_basis=answer.get('answer_basis') or basis)
        try:reject_secrets(row)
        except ValueError:continue
        previous=next((r for r in reversed(history['answers']) if r['page']==row['page'] and r['field']==row['field'] and r['question']==row['question']),None)
        if previous and previous['answer']==row['answer'] and previous.get('answer_basis')==row['answer_basis'] and (source not in ('greenhouse_fast','icims_fast') or
            previous.get('verified') and previous.get('question_key')==row.get('question_key')):continue
        row['observed_at']=datetime.now(timezone.utc).isoformat()
        history['answers'].append(row);added+=1
    if added or metadata_changed and path.is_file():
        folder.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps(history,indent=2,ensure_ascii=False),encoding='utf-8');temporary.replace(path)
    return {'answer_history_path':str(path),'answers_added':added} if path.is_file() else {}


async def capture_answers(browser_page,config,package,ownership,*,page='form',source='employer_form',basis=None,call=None):
    # Called during filling/advancement, never as an extra final-review pass.
    if not config.get('spool_dir') and call is None:return {}
    from .browser_controls import FORM
    try:
        captured=await browser_page.evaluate_function(FORM,{'method':'answers','page':page})
        from .cdp_client import CDPPage
        from .managed_context import platform_for_url
        if isinstance(browser_page,CDPPage) and platform_for_url(package['job']['url'])!='workday':
            from .browser_frames import router_for
            router=await router_for(browser_page,package)
            if not router.frames:await router.discover()
            for frame in router.frames.values():
                child=await frame.evaluate_function(FORM,{'method':'answers','page':page})
                captured['answers'].extend(child['answers'])
                if not captured.get('context') and child.get('context'):captured['context']=child['context']
        context=captured.get('context',{});job=dict(package['job'])
        if call:
            try:
                result=call('observe_job_metadata',**ownership,metadata={k:context[k] for k in ('url','company','title','source') if k in context})
                job=dict(result['job'],**{k:job[k] for k in ('url','posting_url') if k in job});package['job']=job
            except Exception:pass  # Audit/metadata errors do not change the form result.
        if not job.get('company') and context.get('company'):
            job.update(company=context['company'],company_source=context.get('source'))
        if not job.get('title') and context.get('job_title'):job['title']=context['job_title']
        return save_answer_history(config,dict(package,job=job),ownership['attempt_id'],captured['answers'],page=page,source=source,basis=basis)
    except Exception as exc:
        # An audit failure must not disguise an executed form write as retryable.
        return {'answer_history_error':type(exc).__name__}


def approved_policy(value):
    """Import the supported preferences without importing legacy execution rules."""
    if not isinstance(value,dict):return {}
    result={}
    salary=value.get('salary_expectation')
    if isinstance(salary,dict):
        amount=salary.get('fallback_amount')
        if type(amount) in (int,float) and math.isfinite(amount) and amount>0:
            result['salary_expectation']={
                'use_posted_range_max':salary.get('use_posted_range_max') is True,
                'fallback_amount':amount,'currency':str(salary.get('currency','USD')).upper(),
                'period':salary.get('period','year')}
    if type(value.get('routine_privacy_consent')) is bool:
        result['routine_privacy_consent']=value['routine_privacy_consent']
    if isinstance(value.get('submission_evidence_sources'),list):
        result['submission_evidence_sources']=[s for s in value['submission_evidence_sources']
            if s in ('employer','simplify','user_reported')]
    return result


def profile_policy(package):
    profile=package['attempt'].get('profile_json') or {}
    if isinstance(profile,str):profile=json.loads(profile)
    return approved_policy(profile.get('application_answer_policy'))


def salary_answer(policy, text='', posted_range=None):
    """Return an approved expectation, never use a candidate's private range as a job range."""
    salary=policy.get('salary_expectation') or {}
    if not salary:return None
    if re.search(r'\b(?:CAD|AUD|EUR|GBP)\b',text or '',re.I) and salary.get('currency')=='USD':return None
    if salary.get('use_posted_range_max'):
        if isinstance(posted_range,dict):
            if str(posted_range.get('currency',salary['currency'])).upper()!=salary['currency']:return None
            if posted_range.get('period',salary.get('period','year'))!=salary.get('period','year'):return None
            high=posted_range.get('max')
            if type(high) in (int,float) and math.isfinite(high) and high>0:return str(int(high))
        # The official Simplify role panel displays the job's advertised range.
        # Multiple different ranges are ambiguous; the executor can supply the
        # applicable location range explicitly to the same operation.
        number=r'(\d[\d,]*(?:\.\d+)?\s*[kK]?)'
        pattern=r'(?:\$|USD\s*)\s*'+number+r'\s*(?:-|–|—|to)\s*(?:\$|USD\s*)?\s*'+number
        ranges=set()
        if salary.get('currency')=='USD':
            for low,high in re.findall(pattern,text or '',re.I):
                def amount(v):
                    v=v.replace(',','').replace(' ','')
                    return float(v[:-1])*1000 if v.lower().endswith('k') else float(v)
                lo,hi=amount(low),amount(high)
                if 0<lo<=hi:ranges.add((lo,hi))
        if ranges and re.search(r'per hour|hourly|per month|monthly',text or '',re.I):return None
        if len(ranges)==1:return str(int(next(iter(ranges))[1]))
        if len(ranges)>1:return None
    return str(int(salary['fallback_amount']))


async def apply_policy(page, package, observed, *, completed=None, posted_range=None, dry_run=False,checkpoint=None,deadline=None):
    """Only salary expectations and routine privacy boxes; Simplify still fills the form."""
    from .browser_controls import form_action
    policy=profile_policy(package);completed=completed if completed is not None else []
    results=[]
    for field in observed.get('inventory',[]):
        if checkpoint:await checkpoint()
        label=field.get('question') or field.get('label') or field.get('text') or ''
        key=(observed.get('page_signature') or observed.get('step',''))+'|'+label
        if key in completed or not field.get('enabled') or not field.get('ref'):continue
        params=None
        if policy.get('routine_privacy_consent') and (field.get('type')=='checkbox' or field.get('role')=='checkbox'):
            if (re.search(r'privacy|personal data|data processing|data protection',label,re.I) and
                not re.search(r'marketing|job alerts|talent community|newsletter',label,re.I)):
                params={'method':'check','ref':field['ref'],'value':True}
        elif policy.get('routine_privacy_consent') and field.get('tag')=='SELECT':
            if (re.search(r'privacy|personal data|data processing|data protection',label,re.I) and
                not re.search(r'marketing|job alerts|talent community|newsletter',label,re.I)):
                choices=[o for o in field.get('options',[]) if not o.get('disabled') and
                         re.fullmatch(r'(?:I (?:acknowledge|agree|consent)|Yes)',o.get('label','').strip(),re.I)]
                if len(choices)==1:params={'method':'select','ref':field['ref'],'value':choices[0]['value']}
        elif (field.get('tag')=='INPUT' and field.get('type') in ('text','number','tel','') and
              re.search(r'salary|compensation|pay expectation',label,re.I) and
              not re.search(r'current|previous|past|history|hourly|per hour|monthly|per month',label,re.I)):
            amount=salary_answer(policy,observed.get('panel_text',''),posted_range)
            if amount is not None:params={'method':'fill','ref':field['ref'],'value':amount}
        if params:
            if dry_run:
                results.append({'field':label,'ref':field['ref'],'pending':True});continue
            result=await form_action(page,params,checkpoint=checkpoint,deadline=deadline) if checkpoint or deadline else await form_action(page,params)
            results.append({'field':label,'ref':field['ref'],'committed':result.get('committed',False),'reason':result.get('reason')})
            if result.get('committed'):completed.append(key)
    return {'changed':any(r.get('committed') for r in results),'fields':results}


# Internal reuse of the LinkedIn answer adaptations. Copyright (c) 2024-2026
# Sai Vignesh Golla; see third_party/godsscion-linkedin for MIT attribution.

def label_has(label, *words):
    """Donor find_bad_word/label_has: boundaries prevent state/States and no/non collisions."""
    for word in words:
        word=str(word).strip()
        if not word:continue
        left=r'(?<!\w)' if word[0].isalnum() or word[0]=='_' else ''
        right=r'(?!\w)' if word[-1].isalnum() or word[-1]=='_' else ''
        if re.search(left+re.escape(word)+right,label,re.I):return True
    return False


def match_answer_to_option(answer, options):
    """Adapted donor mapping: exact first, polarity-aware unique matches only."""
    if answer is None:return None
    answer='Yes' if answer is True else 'No' if answer is False else str(answer).strip()
    if not answer:return None
    exact=[i for i,o in enumerate(options) if o.strip().casefold()==answer.casefold()]
    if exact:return exact[0] if len(exact)==1 else None
    negative=('no','not','never',"don't","doesn't","won't","can't",'cannot','disagree','decline')
    polarity=None
    if label_has(answer,'decline','prefer not','not wish',"don't wish",'not want','rather not'):
        phrases=('Decline','not wish',"don't wish",'Prefer not','not want')
    elif answer.casefold()=='yes':phrases=('Yes','Agree','I do','I have');polarity=False
    elif answer.casefold()=='no':phrases=('No','Disagree',"I don't",'I do not');polarity=True
    else:phrases=(answer,)
    matches=[i for i,option in enumerate(options) if any(label_has(option,p) for p in phrases)
             and (polarity is None or polarity==label_has(option,*negative))]
    return matches[0] if len(matches)==1 else None


def approved_answer(question, profile):
    """Use explicit Jobbot facts; the executor resolves unfamiliar/compound wording."""
    from .profile_questions import structured_answer,field_for_question
    answer=structured_answer(question,profile)
    if answer is not None or field_for_question(question):return answer
    standard=profile.get('standard_answers') or {};identity=profile.get('identity') or {}
    auth=profile.get('work_authorization') or {}
    if not isinstance(auth,dict):auth={}
    exact=[v for k,v in standard.items() if k.strip().casefold()==question.strip().casefold()]
    if exact:return exact[0]
    # Donor precedence: sponsorship, authorization, citizenship, then location.
    # No status-to-eligibility inference and no total tenure for skill experience.
    if label_has(question,'sponsor','sponsors','sponsorship') or (
            label_has(question,'need','require','requires') and label_has(question,'visa','visas','work permit','h-1b','h1b')):
        if re.search(r'\b(?:not|without|no)\b',question,re.I):return None
        current=standard.get('requires_sponsorship',auth.get('needs_sponsorship'))
        future=standard.get('will_require_sponsorship_future')
        if label_has(question,'future'):
            if label_has(question,'now','currently','current'):
                return True if current is True or future is True else False if current is False and future is False else None
            return future
        return current
    if label_has(question,'legally authorized','legally authorised','authorized to work','authorised to work','right to work','work authorization','work authorisation'):
        if label_has(question,'citizen','citizenship') or re.search(r'\b(?:not|without|no)\b',question,re.I):return None
        if label_has(question,'United States','US','U.S.'):
            return standard.get('authorized_to_work_us',standard.get('legally_authorized_to_work',auth.get('legally_authorized_us')))
        return standard.get('legally_authorized_to_work')
    if label_has(question,'citizen','citizenship'):return None
    label=question.strip().rstrip('*').strip().casefold()
    names={'first name':'first_name','last name':'last_name','full name':'full_name','email':'email','email address':'email',
           'phone':'phone','phone number':'phone','mobile phone number':'phone','linkedin profile':'linkedin','website':'website'}
    if label in names:return identity.get(names[label])
    address=identity.get('address') or {}
    if label in ('city','state','country','zip','zip code','postal code','street address','address','address line 1') and isinstance(address,dict):
        return address.get({'postal code':'zip','zip code':'zip','street address':'street','address':'street','address line 1':'street'}.get(label,label))
    if label in ('location','city, state','city, state, country'):return identity.get('location')
    if label in ('total years of experience','years of work experience','total professional experience'):
        return profile.get('years_experience')
    return None


def answer_action(question,answer):
    kind=question['kind'];ref=question['ref']
    if kind in ('radio','select') and question.get('options'):
        options=question['options']
        if isinstance(answer,dict):
            matches=[i for i,o in enumerate(options) if all(o.get(k)==answer.get(k) for k in ('value','label'))]
            index=matches[0] if len(matches)==1 else None
        else:index=match_answer_to_option(answer,[o['label'] for o in options])
        if index is None:return None
        selected=options[index]
        if kind=='radio':return {'method':'check','ref':selected['ref'],'value':True}
        return {'method':'select','ref':ref,'value':selected['value'],'label':selected['label']}
    if kind=='check':return {'method':'check','ref':ref,'value':answer} if type(answer) is bool else None
    if isinstance(answer,(str,int,float,bool)):
        value='Yes' if answer is True else 'No' if answer is False else str(answer)
        return {'method':'select' if kind=='select' else 'fill','ref':ref,**({'label':value} if kind=='select' else {'value':value})}
    return None


def saved_answer(question,package):
    from .managed_questions import question_data,question_key
    try:
        data=question_data(**{k:question[k] for k in ('field','question','kind','required','context')},
            options=[{k:o[k] for k in ('value','label')} for o in question['options']])
    except ValueError:return None
    key=question_key(data)
    exact=next((q for q in package.get('saved_questions',[]) if q.get('question_key')==key
                 and q.get('state')!='superseded' and q.get('answer') is not None),None)
    if exact and exact.get('answer_source') in ('user_dashboard','user_reply'):return exact['answer']
    from .managed_answer_library import resolve_with_profile
    profile=package.get('attempt',{}).get('profile_json') or {}
    if isinstance(profile,str):profile=json.loads(profile)
    library=resolve_with_profile(question,package.get('job',{}),package.get('answer_library',[]),profile)
    if library.get('matched'):return library['answer']
    return exact['answer'] if exact and not exact.get('library_entry_id') else None


def saved_answer_basis(question,package):
    from .managed_answer_library import resolve_with_profile
    from .managed_questions import question_key,question_data
    try:key=question_key(question_data(**{k:question[k] for k in ('field','question','kind','required','context')},
        options=[{k:o[k] for k in ('value','label')} for o in question.get('options',[])]))
    except (KeyError,ValueError):return None
    if any(q.get('question_key')==key and q.get('state')!='superseded' and q.get('answer') is not None
           and q.get('answer_source') in ('user_dashboard','user_reply') for q in package.get('saved_questions',[])):return None
    profile=package.get('attempt',{}).get('profile_json') or {}
    if isinstance(profile,str):profile=json.loads(profile)
    return resolve_with_profile(question,package.get('job',{}),package.get('answer_library',[]),profile).get('basis')
