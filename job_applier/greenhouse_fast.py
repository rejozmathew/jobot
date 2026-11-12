"""Session-owned Greenhouse residual batches on the existing raw CDP runtime."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

from .application_answers import approved_answer, answer_action, saved_answer, label_has
from .browser_controls import FORM, observe, form_action, required_questions, click_control, remaining_submission_work
from .browser_frames import resolve_control, FramePage, FrameUnavailable
from .managed_questions import question_data, question_key, PRIVATE
from .managed_shared import ProtocolError, uid
from .simplify_boundary import SimplifyBoundary, OBSERVE
from .hermes_gmail import mailbox_handoff
from .email_routing import email_route, routed_profile, routed_email_answer

STATES = dict(part.strip().split(' ', 1) for part in '''AL Alabama; AK Alaska; AZ Arizona; AR Arkansas; CA California; CO Colorado;
CT Connecticut; DE Delaware; DC District of Columbia; FL Florida; GA Georgia; HI Hawaii; ID Idaho; IL Illinois; IN Indiana;
IA Iowa; KS Kansas; KY Kentucky; LA Louisiana; ME Maine; MD Maryland; MA Massachusetts; MI Michigan; MN Minnesota;
MS Mississippi; MO Missouri; MT Montana; NE Nebraska; NV Nevada; NH New Hampshire; NJ New Jersey; NM New Mexico;
NY New York; NC North Carolina; ND North Dakota; OH Ohio; OK Oklahoma; OR Oregon; PA Pennsylvania; RI Rhode Island;
SC South Carolina; SD South Dakota; TN Tennessee; TX Texas; UT Utah; VT Vermont; VA Virginia; WA Washington;
WV West Virginia; WI Wisconsin; WY Wyoming'''.replace('\n', ' ').split(';'))


def email_recovery_handoff():
    return {
        'email_recovery':{'operation':'greenhouse_advance','parameters':{'seconds':60,'recovery':'missing_verification_email'}},
        'instruction':('Read the configured mailbox for the current email request. If no matching code arrives after about 1–2 minutes, '
            'having checked the exact recipient, delayed mail and spam/junk, execute email_recovery in this owned session. '
            'It reloads and immediately resumes filling and submission with fresh controls. Mail polls do not restart that window. '
            'Follow renewed verification if the employer requests it again; refresh does not guarantee it disappears. '
            'A replaced document invalidates the old code screen and screenshot. Continue from the returned current form, '
            'not an earlier blocker. This helper handoff does not finish the application.')}


def greenhouse_answer(question, profile):
    """Exact identity mappings and offered residence aliases, never guessed facts."""
    label=question['question'].strip().rstrip('*').strip()
    identity=profile.get('identity') or {}
    answer=approved_answer(label,profile)
    if answer is None:
        names={'preferred name':'preferred_name','preferred first name':'preferred_name',
            'linkedin profile url':'linkedin','linkedin url':'linkedin','website url':'website',
            'phone number':'phone','current location':'location','location (city)':'city',
            'state of residence':'state','residence state':'state','state/province':'state','zip code':'zip'}
        key=names.get(label.casefold())
        if key:
            answer=identity.get(key)
            if answer is None and isinstance(identity.get('address'),dict):answer=identity['address'].get(key)
    if question['kind']=='select' and answer is not None and label.casefold() in (
            'state','state of residence','residence state','state/province'):
        code=next((code for code,name in STATES.items() if str(answer).casefold() in (code.casefold(),name.casefold())),None)
        if code:
            options=[o for o in question.get('options',[]) if o['label'].casefold() in (code.casefold(),STATES[code].casefold())]
            if len(options)==1:return {k:options[0][k] for k in ('value','label')}
    # A dial code is shared by several countries. Require an approved country
    # identity and an offered country label before touching this widget.
    if label.casefold() in ('phone country','phone country code','country calling code'):
        country=identity.get('phone_country')
        if country:
            choices=[o for o in question.get('options',[]) if re.sub(r'\s*\+\d+[\s)]*$', '',o['label']).strip(' (')==country]
            if len(choices)==1:return {k:choices[0][k] for k in ('value','label')}
        return None
    return answer


def binding(question):
    return question_data(**{k:question[k] for k in ('field','question','kind','context')},required=True,
        options=[{k:o[k] for k in ('value','label')} for o in question.get('options',[])])


class GreenhouseRunner:
    def __init__(self,page,call,package,ownership,config,target_id,owned_observation=None):
        self.page,self.call,self.package,self.owner,self.config,self.target=page,call,package,ownership,config,target_id
        page.application_package=package
        self.profile=package['attempt'].get('profile_json') or {}
        self.settings=package['attempt'].get('settings_json') or {}
        if isinstance(self.profile,str):self.profile=json.loads(self.profile)
        self.email_route=package.get('email_route') or email_route(config,'greenhouse')
        self.profile=routed_profile(self.profile,self.email_route)
        if isinstance(self.settings,str):self.settings=json.loads(self.settings)
        self.document=None;self.document_id=None;self.aid=None;self.deadline=None
        self.started=time.monotonic();self.batch_count=0;self.completed=0;self.field_actions=0
        self.questions=[];self.failures=[];self.question_diagnostics=[];self.verified=[];self.seen_plans=set()
        self.receipt={};self.last={};self.phase='readiness';self.restored=self.read_journal()
        self.parent_autofill_count=0
        self.browser_package=package;self.owned_observation=owned_observation or {}

    def owned(self,operation,**params):return self.call(operation,**self.owner,**params)

    def read_journal(self):
        from .application_answers import reusable_answers
        return reusable_answers(self.config,self.package,self.owner['attempt_id'],source='greenhouse_fast')

    def event(self,kind,payload,**extra):
        self.owned('event',event_id=uid(),event_type=kind,action_id=self.aid,
            observed_at=datetime.now(timezone.utc).isoformat(),payload=dict(payload,handler='greenhouse_fast'),**extra)

    async def control(self):
        pulse=self.owned('heartbeat')
        if pulse.get('control','running')!='running':raise ProtocolError(pulse['control'])
        if self.deadline is not None and time.monotonic()>=self.deadline:raise TimeoutError('call_slice_complete')

    async def checkpoint(self):
        await self.control()
        if self.document_id:
            current=await self.document.evaluate('window.__jobbotGreenhouseDocument?.id')
            if current!=self.document_id:raise FrameUnavailable('application_document_changed')
        # Do not recursively enter Service.browser_observe inside our own batch.
        # That action correctly sees this batch as a writer. Check its DOM instead.
        for document in self.writer_documents:
            current=await document.evaluate(OBSERVE)
            if current.get('status') in ('active','unknown') or current.get('autofill_receipt',{}).get('state') in (
                    'dispatching','dispatched','active','uncertain'):
                raise FrameUnavailable('writer_settlement_required')

    async def discover(self):
        from .managed_identity import public_url
        current=await self.page.evaluate('location.href')
        evidence=self.owned_observation
        if (evidence.get('identity',{}).get('status')=='same_job' and evidence.get('target_id')==self.target and
            public_url(current)==evidence.get('observation',{}).get('url')):
            # The Service accepted this correlated target. Use its current URL
            # for browser/frame/submission scope, retaining the intake job and
            # private answer history in the original authoritative package.
            self.browser_package=dict(self.package,job=dict(self.package['job'],url=current))
            self.page.application_package=self.browser_package
        self.last=await observe(self.page,self.browser_package)
        documents=[self.page]
        from .cdp_client import CDPPage
        if isinstance(self.page,CDPPage):
            from .browser_frames import router_for
            router=await router_for(self.page,self.browser_package)
            documents+=list(router.frames.values())
        self.writer_documents=documents
        candidates=[]
        for document in documents:
            native=await document.evaluate_function(FORM,{'method':'observe'})
            if native.get('greenhouse') and any(f.get('tag') in ('INPUT','SELECT','TEXTAREA') for f in native['inventory']):
                candidates.append((document,native))
        if len(candidates)!=1:return False
        self.document,native=candidates[0]
        self.document_url=await self.document.evaluate('location.href')
        self.boundary=SimplifyBoundary(self.document,budget_seconds=max(.05,min(120,self.deadline-time.monotonic())),
            scope={'attempt_id':self.owner['attempt_id'],'target_id':self.target},checkpoint=self.control)
        extension=await self.boundary.observe();self.document_id=extension['document_id'];self.receipt=extension['autofill_receipt']
        self.last=native
        return True

    def wrap(self,ref):return self.document.wrap(ref) if isinstance(self.document,FramePage) else ref

    async def native(self):
        await self.control()
        value=await self.document.evaluate_function(FORM,{'method':'observe'})
        value['inventory']=[dict(f,ref=self.wrap(f['ref'])) for f in value['inventory']]
        value['native']={k:dict(c,ref=self.wrap(c['ref'])) for k,c in value['native'].items()}
        self.last=value
        return value

    async def verification(self):
        groups=self.last.get('verification',{}).get('groups') or []
        if not groups:return None
        self.phase='verification'
        timestamp=await self.document.evaluate_function('''(now)=>{
            const r=window.__jobbotGreenhouseDocument.current;
            const fresh=!r.first_challenge_seen_at;r.first_challenge_seen_at=r.first_challenge_seen_at||now;
            return {first_seen_at:r.first_challenge_seen_at,fresh};
        }''',datetime.now(timezone.utc).isoformat())
        if timestamp['fresh']:
            self.event('checkpoint',{'operation':'verification_observed','first_seen_at':timestamp['first_seen_at'],
                'request_time_known':any(g.get('requested_at') for g in groups)})
        return self.report('verification_required','use_existing_credentials_mail_flow',
            verification={'first_seen_at':timestamp['first_seen_at'],'groups':[dict(g,refs=[self.wrap(r) for r in g['refs']]) for g in groups]},
            **email_recovery_handoff())

    def report(self,status,reason,**extra):
        work=remaining_submission_work(self.last)
        result=dict(handler='greenhouse_fast',status=status,phase=self.phase,reason=reason,
            document={'id':self.document_id,'target_id':self.target,'url':getattr(self,'document_url',self.package['job']['url'])},
            autofill_dispatch_count=self.receipt.get('dispatch_count',0)+self.parent_autofill_count,
            parent_autofill_dispatch_count=self.parent_autofill_count,batch_count=self.batch_count,
            field_action_count=self.field_actions,completed_count=self.completed,residual_count=len(work['required_fields']),
            elapsed_seconds=round(time.monotonic()-self.started,3),questions=self.questions,control_failures=self.failures,
            question_diagnostics=self.question_diagnostics,
            next_operation={'operation':'greenhouse_advance','parameters':{'seconds':60}},
            instruction='Continue this owned application. Return one answers plan with each current ref, exact question_key, answer and approved basis; recover control failures through the scoped browser and resume greenhouse_advance. Helper handoffs do not finish the application.')
        if self.email_route:
            result.update(email_route=self.email_route,mailbox=mailbox_handoff(self.config,platform='greenhouse'))
        return dict(result,**extra)

    async def ready(self):
        previous=None;stable=0
        while time.monotonic()<self.deadline:
            await self.control()
            native=await self.native()
            fields=[f for f in native['inventory'] if f.get('tag') in ('INPUT','SELECT','TEXTAREA') and not f.get('private')]
            contact=any(re.search(r'first.?name|last.?name|e.?mail|phone',f.get('name','')+' '+f.get('label',''),re.I) for f in fields)
            fingerprint=native.get('structure')
            stable=stable+1 if contact and fingerprint==previous else int(contact)
            if native.get('ready_state') in ('interactive','complete') and stable>=3:return True
            previous=fingerprint
            await asyncio.sleep(.2)
        return False

    async def gate(self):
        await self.control()
        gate=await asyncio.to_thread(self.owned,'browser_observe',target_id=self.target,cdp_url=self.config['cdp_url'])
        # The authoritative gate contains accepted handoff/embed identity. Do not
        # compare the LinkedIn intake URL with an employer URL in a second matcher.
        return bool(gate.get('native_takeover_authorized',gate.get('quiescent')))

    async def autofill(self):
        self.phase='simplify'
        # An embedded native form can be filled by a parent-document panel.
        # Resolve that observed control without moving native field ownership.
        from .simplify_boundary import initial_autofill
        from .browser_controls import simplify_document
        combined=await observe(self.page,self.browser_package)
        first=initial_autofill(combined) if self.settings.get('autofill')!='native' else None
        local=await self.boundary.observe()
        if first and first.get('document_id')!=local.get('writer_document_id'):
            if not await self.gate():return False
            document,_,_=await simplify_document(self.page,ref=first.get('ref'),operation='autofill')
            aid=uid();result={};started=time.monotonic()
            self.owned('action_start',action_id=aid,tool_name='greenhouse_fast.simplify')
            try:
                result=await SimplifyBoundary(document,budget_seconds=max(.05,min(45,self.deadline-time.monotonic())),
                    checkpoint=self.control).perform('autofill',automatic=True)
                self.parent_autofill_count+=int(result.get('execution')=='clicked')
            finally:
                self.owned('action_end',action_id=aid,status='success' if result.get('execution')=='clicked' else 'failed',duration_seconds=time.monotonic()-started)
            self.event('checkpoint',{'phase':'simplify','operation':'parent_autofill_settlement',
                'execution':result.get('execution'),'reason':result.get('reason')})
            if not result.get('native_takeover_authorized'):return False
            await self.native()
        while time.monotonic()<self.deadline:
            extension=await self.boundary.observe();self.receipt=extension['autofill_receipt']
            decision=self.boundary.decide(extension)
            pending=decision['action']=='wait'
            if self.settings.get('autofill')=='native' and not pending:return True
            if decision['action']!='autofill' and not pending:return True
            if not pending and not await self.gate():return False
            aid=None;result={};started=time.monotonic()
            try:
                if not pending:
                    aid=uid();self.owned('action_start',action_id=aid,tool_name='greenhouse_fast.simplify')
                    self.owned('writer_state',state='active')
                self.boundary.budget=max(.05,min(120,self.deadline-time.monotonic()))
                result=await self.boundary.perform('autofill',automatic=True)
                self.receipt=result.get('observation',{}).get('autofill_receipt',self.receipt)
                self.owned('writer_state',state='idle' if result.get('native_takeover_authorized') else 'unknown')
                self.event('checkpoint',{'phase':'simplify','operation':'autofill_settlement',
                    'dispatch_count':self.receipt.get('dispatch_count',0),'execution':result.get('execution'),
                    'reason':result.get('reason')})
            finally:
                if aid:self.owned('action_end',action_id=aid,status='success' if result.get('execution')=='clicked' else 'failed',duration_seconds=time.monotonic()-started)
            if not result.get('native_takeover_authorized'):return False
            if not pending and result.get('execution')!='clicked':return True
            await self.native()
        return False

    async def question(self,field):
        document,target=await resolve_control(self.page,{'ref':field['ref']})
        q=await document.evaluate_function(FORM,dict(target,method='question'))
        if q.get('reason'):return None
        q.update(ref=field['ref'],required=field['required'])
        try:
            if q['kind']=='select' and not q.get('options'):
                captured=await required_questions(self.page,[field['ref']],include_answered=True,include_optional=True,checkpoint=self.checkpoint)
                if captured['questions']:
                    q.update(captured['questions'][0]['data'],required=field['required'])
                else:
                    self.failures.extend(captured['skipped']);return None
            elif q['kind']=='radio':
                q['options']=[dict(o,ref=document.wrap(o['ref']) if isinstance(document,FramePage) else o['ref']) for o in q['options']]
            q['question_key']=question_key(binding(q))
        except ProtocolError as exc:
            if str(exc)!='invalid_question':raise
            # A malformed label/identity is local to this control. Preserve exact
            # bindings elsewhere; never invent a label or truncate a question key.
            diagnostic=next((d for d in self.question_diagnostics if d['ref']==field['ref']),None)
            if diagnostic is None:
                name,text=q.get('field'),q.get('question')
                diagnostic=dict(ref=field['ref'],reason='invalid_question',kind=q.get('kind'),
                    needs_recovery=False,
                    metadata={'field_missing':not isinstance(name,str) or not name,
                        'field_length':len(name) if isinstance(name,str) else None,
                        'question_missing':not isinstance(text,str) or not text.strip(),
                        'question_length':len(text.strip()) if isinstance(text,str) else None})
                self.question_diagnostics.append(diagnostic)
            diagnostic.update(required=bool(field.get('required')),
                invalid=bool(field.get('validation',{}).get('rejected')))
            diagnostic['needs_recovery']=bool(diagnostic.get('explicit_plan') or diagnostic['required'] or diagnostic['invalid'])
            if diagnostic['needs_recovery'] and diagnostic not in self.failures:self.failures.append(diagnostic)
            elif not diagnostic['needs_recovery'] and diagnostic in self.failures:self.failures.remove(diagnostic)
            return None
        return q

    async def recover_resume(self):
        """Only an actual Resume/CV rejection triggers the existing upload path."""
        from .browser_controls import upload_file
        from .managed_documents import local_asset_path
        widget=await self.document.evaluate_function(FORM,{'method':'resume_widget'})
        if not widget.get('required_error'):return None
        assets=[a for a in self.package.get('documents',{}).get('assets',[]) if a['kind']=='resume']
        if len(assets)!=1:return {'reason':'selected_resume_unavailable'}
        if not await self.gate():return {'reason':'writer_settlement_required'}
        self.aid=uid();self.owned('action_start',action_id=self.aid,tool_name='greenhouse_fast.resume')
        success=False;started=time.monotonic()
        try:
            await self.checkpoint()
            if widget.get('remove_ref'):
                result=await click_control(self.page,{'ref':self.wrap(widget['remove_ref'])})
                if not result.get('clicked'):return {'reason':result.get('reason','resume_remove_unconfirmed')}
            end=min(self.deadline,time.monotonic()+3)
            while time.monotonic()<end:
                await self.checkpoint()
                widget=await self.document.evaluate_function(FORM,{'method':'resume_widget'})
                if widget.get('input_ref'):break
                await asyncio.sleep(.1)
            if not widget.get('input_ref'):return {'reason':'resume_upload_control_unresolved'}
            asset=assets[0];path=local_asset_path(asset)
            self.owned('report_upload',asset_id=asset['id'],status='upload_attempted',evidence='Selected approved resume through its observed Resume/CV widget')
            await upload_file(self.page,{'ref':self.wrap(widget['input_ref'])},path)
            while time.monotonic()<end:
                await self.checkpoint()
                fresh=await self.document.evaluate_function(FORM,{'method':'resume_widget'})
                if not fresh.get('required_error') and not fresh.get('reason'):
                    success=True
                    if any(f['name']==path.name and f['size']==path.stat().st_size for f in fresh.get('files',[])):
                        self.owned('report_upload',asset_id=asset['id'],status='upload_confirmed',evidence='Scoped Resume/CV input matches selected asset and native error cleared')
                    return None
                await asyncio.sleep(.1)
            return {'reason':'resume_required_error_persists'}
        finally:
            self.owned('action_end',action_id=self.aid,status='success' if success else 'failed',duration_seconds=time.monotonic()-started)
            self.aid=None

    async def batch(self,plans):
        from .application_answers import apply_policy,save_answer_history
        from .managed_events import field_task_context
        if not await self.gate():return False
        self.aid=uid();self.owned('action_start',action_id=self.aid,tool_name='greenhouse_fast.batch')
        self.batch_count+=1;started=time.monotonic();success=False
        try:
            native=await self.native()
            # Once corrections begin, a reconnect/rerender cannot schedule a
            # second automatic fill over them. Explicit recovery still can.
            await self.document.evaluate('window.__jobbotGreenhouseDocument.current.repairs_started=true')
            await self.checkpoint()
            policy=await apply_policy(self.page,self.package,native,checkpoint=self.checkpoint,deadline=self.deadline)
            self.completed+=sum(bool(f.get('committed')) for f in policy['fields'])
            self.field_actions+=len(policy['fields'])
            self.failures.extend({'ref':f['ref'],'reason':f.get('reason','policy_control_unconfirmed')} for f in policy['fields'] if not f.get('committed'))
            native=await self.native();pending=list(native['inventory']);processed=set()
            structure=await self.document.evaluate('window.__jobbotFormScope.structureEpoch')
            while pending:
                await self.checkpoint()
                field=pending.pop(0)
                if (not field.get('enabled') or field.get('private') or field.get('type') in ('file','submit','button','password') or
                    not (field.get('tag') in ('INPUT','SELECT','TEXTAREA') or field.get('role') in ('combobox','checkbox','radio'))):continue
                # Untouched optional demographics require explicit direction.
                if not field.get('required') and not any(p.get('ref')==field['ref'] for p in plans):
                    label=field.get('label','').strip().rstrip('*').strip()
                    exact=any(k.strip().casefold()==label.casefold() for k in (self.profile.get('standard_answers') or {}))
                    if not exact and label_has(label,'gender','race','ethnicity','disability','veteran','pronouns'):continue
                q=await self.question(field)
                if q is None:
                    diagnostic=next((d for d in self.question_diagnostics if d['ref']==field['ref']),None)
                    if diagnostic:
                        for plan in (p for p in plans if p.get('ref')==field['ref']):
                            # Account for the supplied plan as a control failure,
                            # without treating its answer as applied or saved.
                            self.seen_plans.add((plan['ref'],plan['question_key']))
                            diagnostic['explicit_plan']=True
                            diagnostic['needs_recovery']=True
                            if diagnostic not in self.failures:self.failures.append(diagnostic)
                if not q or q['question_key'] in processed:continue
                processed.add(q['question_key'])
                if PRIVATE.search(q['field']+' '+q['question']):continue
                plan=next((p for p in plans if p.get('ref')==q['ref'] and p.get('question_key')==q['question_key']),None)
                basis='approved_profile_or_exact_saved_answer'
                routed_answer=routed_email_answer(q,self.email_route)
                if routed_answer is not None:
                    answer=routed_answer;basis='approved_greenhouse_email_route'
                    if plan:self.seen_plans.add((plan['ref'],plan['question_key']))
                elif plan:
                    self.seen_plans.add((plan['ref'],plan['question_key']));answer=plan['answer'];basis=plan['basis']
                    valid=isinstance(answer,str) if q['kind']=='text' else type(answer) is bool if q['kind']=='check' else isinstance(answer,dict)
                    if not valid:
                        self.failures.append({'ref':q['ref'],'reason':'answer_type_mismatch'});continue
                else:
                    answer=saved_answer(q,self.package)
                    if answer is not None:
                        from .application_answers import saved_answer_basis
                        basis=saved_answer_basis(q,self.package) or basis
                    if answer is None:answer=greenhouse_answer(q,self.profile)
                    restored=self.restored.get(q['question_key'])
                    if answer is None and restored:answer=restored['answer_value'];basis=restored['answer_basis']
                if answer is None:
                    if q['required'] and (not q.get('answered') or field.get('validation',{}).get('rejected')):
                        self.questions.append({k:q[k] for k in ('ref','question_key','field','question','kind','options','context','required')})
                    continue
                action=answer_action(q,answer)
                if action is None:
                    self.failures.append({'ref':q['ref'],'question_key':q['question_key'],'reason':'approved_answer_option_unmatched'});continue
                semantic=field_task_context(q['question'],page='form',document=q['context'].get('document',''))
                self.event('field_context',semantic)
                started_field=time.monotonic()
                # Skip an exactly correct value; never skip native rejection.
                document,target=await resolve_control(self.page,{'ref':action['ref']})
                info=await document.evaluate_function(FORM,dict(target,method='inspect'))
                expected=action.get('value')
                correct=not info.get('validation',{}).get('rejected') and (
                    action['method']=='fill' and info.get('value')==expected or
                    action['method']=='check' and info.get('checked') is expected)
                result={'committed':True,'unchanged':True} if correct else await form_action(
                    self.page,action,checkpoint=self.checkpoint,deadline=self.deadline)
                self.field_actions+=int(not result.get('unchanged'))
                self.event('field_verified' if result.get('committed') else 'checkpoint',dict(semantic,
                    task_state='completed' if result.get('committed') else 'recovering',
                    evidence='Exact approved answer verified' if result.get('committed') else 'Control requires recovery'),
                    duration_seconds=time.monotonic()-started_field)
                if result.get('committed'):
                    self.completed+=1
                    self.verified.append({'field':q['field'],'question':q['question'],'question_key':q['question_key'],
                        'answer':str(answer.get('label')) if isinstance(answer,dict) else str(answer),'answer_value':answer,
                        'answer_basis':basis,'verified':True})
                else:self.failures.append({'ref':q['ref'],'question_key':q['question_key'],'reason':result.get('reason','value_unconfirmed')})
                epoch=await self.document.evaluate('window.__jobbotFormScope.structureEpoch')
                if epoch!=structure:
                    structure=epoch;pending=list((await self.native())['inventory'])
            for plan in plans:
                if (plan['ref'],plan['question_key']) not in self.seen_plans:
                    self.failures.append({'ref':plan['ref'],'reason':'stale_answer_binding'})
            success=not self.failures
            return True
        finally:
            save_answer_history(self.config,self.package,self.owner['attempt_id'],self.verified,page='form',
                source='greenhouse_fast',basis='approved_profile_or_exact_saved_answer')
            self.owned('action_end',action_id=self.aid,status='success' if success else 'failed',duration_seconds=time.monotonic()-started)
            self.aid=None

    async def run(self,seconds=60,answers=None):
        self.deadline=time.monotonic()+seconds
        plans=answers or []
        if not isinstance(plans,list) or any(not isinstance(p,dict) or not isinstance(p.get('ref'),str) or
            not isinstance(p.get('question_key'),str) or not isinstance(p.get('basis'),str) or not p['basis'].strip() or
            not isinstance(p.get('answer'),(str,bool,dict)) for p in plans):raise ValueError('approved_grouped_answer_plan_required')
        try:
            if not await self.discover():return self.report('inspection_required','greenhouse_application_document_unresolved')
            challenge=await self.verification()
            if challenge:return challenge
            if self.last.get('auth'):return self.report('authentication_required','use_existing_credentials_flow')
            if not await self.ready():return self.report('continue','native_form_initializing')
            if not await self.autofill():return self.report('continue','writer_settlement_required')
            self.phase='residual_batch'
            if not await self.batch(plans):return self.report('continue','writer_settlement_required')
            native=await self.native()
            if any(re.search(r'resume|\bcv\b',e,re.I) for e in native.get('blocking_errors',[])):
                self.phase='resume_recovery'
                resume=await self.recover_resume()
                if resume:return self.report('inspection_required',resume['reason'])
                native=await self.native()
            challenge=await self.verification()
            if challenge:return challenge
            if self.failures:return self.report('inspection_required','control_recovery')
            if self.questions:return self.report('questions_required','unresolved_required_questions')
            if native.get('blocking_errors'):return self.report('inspection_required','native_validation',errors=native['blocking_errors'])
            self.phase='submission'
            if self.settings.get('submission_mode')!='submit':return self.report('ready_for_review','configured_review_mode')
            control=native['native'].get('submit') or {}
            if not control.get('enabled'):return self.report('inspection_required','submit_control_unavailable')
            from .submission import submit
            async def activate():
                await self.checkpoint()
                return await click_control(self.page,{'ref':control['ref']})
            result=await submit(self.page,self.call,self.browser_package,self.owner,self.config,self.target,activate,
                application_control={'ref':control['ref']},seconds=max(1,min(15,self.deadline-time.monotonic())))
            report=dict(self.report(result.get('status','inspection_required'),result.get('reason','submission_service_result')),**result)
            if result.get('remaining_work',{}).get('verification_groups'):
                report.update(email_recovery_handoff(),phase='verification')
            return report
        except TimeoutError:return self.report('continue','call_slice_complete')
        except (FrameUnavailable,ProtocolError) as exc:return self.report('inspection_required',str(exc))


def advance(config,client,ownership,params):
    """Use the resolved owned target and context; close only our CDP connection."""
    from .cdp_client import CDPBrowser
    if set(params)-{'target_id','seconds','answers','recovery'} or not params.get('target_id'):raise ProtocolError('invalid_greenhouse_parameters')
    seconds=params.get('seconds',60)
    if type(seconds) not in (int,float) or not 0<seconds<=120:raise ValueError('bounded_seconds_required')
    recovery=params.get('recovery')
    if recovery not in (None,'missing_verification_email'):raise ProtocolError('invalid_greenhouse_parameters')
    started=time.monotonic();reloaded=None
    package=client.call('application_context',attempt_id=ownership['attempt_id'],worker_id=ownership['worker_id'])
    observed=client.call('browser_observe',**ownership,target_id=params['target_id'],cdp_url=config['cdp_url'])
    if recovery and observed.get('platform') not in (None,'unknown','greenhouse'):
        return dict(observed,status='continue',reason='missing_email_recovery_is_greenhouse_only')
    async def execute():
        nonlocal observed,reloaded
        browser=await CDPBrowser.connect(config['cdp_url'],target_id=params['target_id'],expected_mode=config.get('browser_mode','headed'))
        runner=None
        try:
            runner=GreenhouseRunner(await browser.get_current_page(),client.call,package,ownership,config,params['target_id'],observed)
            if recovery:
                from .application_runtime import browser_action
                if observed.get('platform')!='greenhouse':
                    # Custom career pages can host the accepted Greenhouse
                    # document. Reuse owned-frame discovery before rejecting
                    # recovery; the parent hostname alone cannot identify it.
                    runner.deadline=started+seconds
                    await runner.control()
                    if not await runner.discover():
                        return dict(observed,status='continue',reason='missing_email_recovery_is_greenhouse_only')
                screen=await asyncio.to_thread(browser_action,config,client,ownership,package,params['target_id'],{'method':'snapshot'})
                # A stale request must not reload an ordinary form again.
                if any(g.get('complete') is False for g in screen.get('verification',{}).get('groups',[])):
                    reloaded=await asyncio.to_thread(browser_action,config,client,ownership,package,params['target_id'],
                        {'method':'reload','recovery_reason':recovery})
                    if not reloaded.get('document_replaced'):
                        return dict(reloaded,handler='greenhouse_fast',status='inspection_required',
                            reason='reload_requires_inspection',next_operation={'operation':'browser','parameters':{'method':'snapshot'}})
                    observed=await asyncio.to_thread(client.call,'browser_observe',**ownership,
                        target_id=params['target_id'],cdp_url=config['cdp_url'])
                    runner=GreenhouseRunner(await browser.get_current_page(),client.call,package,ownership,config,params['target_id'],observed)
            # Reload and refill share the caller's slice. The durable application
            # deadline remains owned by the runtime, including across this call.
            result=await runner.run(max(.05,seconds-(time.monotonic()-started)),None if reloaded else params.get('answers'))
            if reloaded:
                result['email_recovery_result']={'document_replaced':True,
                    'reload_status':reloaded.get('recovery',{}).get('status'),
                    'elapsed_seconds':round(time.monotonic()-started,3)}
            return result
        except TimeoutError:
            if runner is None:raise
            return runner.report('continue','call_slice_complete')
        except (FrameUnavailable,ProtocolError) as exc:
            if runner is None:raise
            return runner.report('inspection_required',str(exc))
        finally:await browser.close()
    return asyncio.run(execute())
