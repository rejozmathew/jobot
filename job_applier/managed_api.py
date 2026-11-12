import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from .managed_shared import ProtocolError
from .managed_ui import OperatorSessions,COOKIE,install_ui

READS=frozenset({'job','attempt_status','events','attempt_report','application_context','account_strategy','lessons_for_context','helpers_for_context','documents_status','candidate','browser_observe','next_request'})
OPERATOR=frozenset({'identity','intake','eligibility','request_run','control','reconcile','retry','account_update','mail_request','match_mail','view','settings_view','configure','candidate','import_profile'})|READS
OPERATOR=OPERATOR|frozenset({'lesson_observe','lesson_set_status','lesson_record_outcome','helper_register','helper_activate','register_asset','select_asset','register_assessment','namespace_alias','preview_archive','archive'})
OPERATOR=OPERATOR|frozenset({'sessions_view','session_status'})
OPERATOR=OPERATOR|frozenset({'answer_queue','answer_questions','queue_answer_retries','answer_retries','questions_for_attempt'})
OPERATOR=OPERATOR|frozenset({'answer_library','save_library_answer','set_library_answer_state','reconcile_answers','answer_queue_history'})
OPERATOR=OPERATOR|frozenset({'retry_answer_learning'})
OPERATOR=OPERATOR|frozenset({'enrich_job','backfill_job_metadata'})
OPERATOR=OPERATOR|frozenset({'queue_enqueue','queue_status','queue_control'})
OPERATOR=OPERATOR|frozenset({'set_job_disposition','update_job_url'})
OPERATOR=OPERATOR|frozenset({'model_catalog'})
OPERATOR=OPERATOR|frozenset({'activity_stats'})
OPERATOR=OPERATOR|frozenset({'set_portal_password','remove_portal_password'})
OPERATOR=OPERATOR|frozenset({'duplicate_matches','set_duplicate_match_state'})
OPERATOR=OPERATOR|frozenset({'profile_editor','save_profile','sync_profile_file'})
WORKER=frozenset({'accept_run','claim','heartbeat','event','action_start','action_end','writer_state','submission_intent','finish','ack_control','ack_run_control','checkpoint','resume_run'})|READS
WORKER=WORKER|frozenset({'observe_owned_lesson','report_upload','record_account_event','extend_budget','bind_target','target_state','request_mail_for_attempt','match_mail_for_attempt','browser_observe'})
WORKER=WORKER|frozenset({'request_question','park_questions','answer_from_user','questions_for_attempt'})
WORKER=WORKER|frozenset({'observe_job_metadata'})
WORKER=WORKER|frozenset({'record_submission_rejection'})
WORKER=WORKER|frozenset({'progress'})
WORKER=WORKER|frozenset({'handoff_target'})
READS=READS|frozenset({'questions_for_attempt'})


def create_app(service, *, operator_token, worker_tokens):
    if not isinstance(operator_token,str) or len(operator_token)<24 or not worker_tokens:
        raise ProtocolError('strong_local_credentials_required')
    if operator_token in worker_tokens or any(not isinstance(k,str) or len(k)<24 or not v for k,v in worker_tokens.items()):
        raise ProtocolError('distinct_worker_credentials_required')
    app=FastAPI(title='JobBot v1',docs_url=None,redoc_url=None,openapi_url=None)
    operations={name:getattr(service,name) for name in OPERATOR|WORKER}
    app.state.service=service
    sessions=OperatorSessions()
    install_ui(app,service,operator_token,sessions)

    @app.middleware('http')
    async def authorize(request, call_next):
        if request.url.hostname not in ('localhost','127.0.0.1','::1'):
            return JSONResponse({'error':'loopback_host_required'},status_code=403)
        origin=request.headers.get('origin')
        if origin and origin!=str(request.base_url).rstrip('/'):
            return JSONResponse({'error':'untrusted_origin'},status_code=403)
        public=(request.method=='GET' and request.url.path in ('/','/static/jobbot.js','/static/jobbot.css')) or (request.method=='POST' and request.url.path=='/login')
        if public:
            response=await call_next(request)
            response.headers['X-Content-Type-Options']='nosniff'
            response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'self'; base-uri 'none'; form-action 'self'"
            return response
        auth=request.headers.get('authorization','')
        provided=auth[7:] if auth.startswith('Bearer ') else ''
        request.state.role=None;request.state.worker_id=None
        if hmac.compare_digest(provided.encode(),operator_token.encode()):request.state.role='operator'
        for token,worker in worker_tokens.items():
            if hmac.compare_digest(provided.encode(),token.encode()):request.state.role='worker';request.state.worker_id=worker
        if not auth and sessions.valid(request.cookies.get(COOKIE)):request.state.role='operator'
        if request.state.role is None:return JSONResponse({'error':'unauthorized'},status_code=401)
        if request.url.path!='/session' and request.headers.get('x-jobbot-instance')!=service.instance_id:
            return JSONResponse({'error':'instance_mismatch'},status_code=409)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response

    @app.get('/v1/health')
    def health():return service.health()

    @app.post('/v1/upload_asset')
    async def upload_asset(request: Request):
        if request.state.role!='operator':
            return JSONResponse({'error':'role_forbidden'},status_code=403)
        identity_id=request.headers.get('x-identity-id') or request.query_params.get('identity_id')
        if not identity_id:
            return JSONResponse({'error':'identity_id_required'},status_code=422)
        if any(c in identity_id for c in '/\\\x00') or '..' in identity_id:
            return JSONResponse({'error':'invalid_identity_id'},status_code=400)
        kind=request.headers.get('x-asset-kind') or request.query_params.get('kind') or 'resume'
        if kind not in ('resume','cover_letter'):
            return JSONResponse({'error':'invalid_asset_kind'},status_code=422)
        filename=request.headers.get('x-filename') or request.query_params.get('filename') or 'resume.pdf'
        if '..' in filename or any(c in filename for c in '/\\\x00'):
            return JSONResponse({'error':'path_traversal_prohibited'},status_code=400)
        safe_filename=Path(filename).name
        ext=Path(safe_filename).suffix.lower()
        if ext not in ('.pdf','.docx','.doc','.txt','.rtf'):
            return JSONResponse({'error':'unsupported_file_type'},status_code=422)
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>10*1024*1024:
                return JSONResponse({'error':'payload_too_large'},status_code=413)
        if len(body)==0:
            return JSONResponse({'error':'empty_file'},status_code=422)
        content_bytes=bytes(body)
        sha256=hashlib.sha256(content_bytes).hexdigest()
        assets_dir=(service.db_path.parent/'managed-assets').resolve()
        assets_dir.mkdir(parents=True,exist_ok=True)
        target_path=(assets_dir/f"{sha256[:16]}_{safe_filename}").resolve()
        if not str(target_path).startswith(str(assets_dir)):
            return JSONResponse({'error':'invalid_storage_path'},status_code=422)
        if not target_path.exists():
            target_path.write_bytes(content_bytes)
        version=request.headers.get('x-asset-version') or request.query_params.get('version') or f"v-{sha256[:8]}"
        storage_ref=target_path.as_uri()
        provenance={'filename':safe_filename,'source':'operator_upload','size':len(content_bytes)}
        try:
            asset=service.register_asset(
                identity_id=identity_id,kind=kind,version=version,
                storage_ref=storage_ref,sha256=sha256,provenance=provenance
            )
            return JSONResponse(asset)
        except ProtocolError as exc:
            return JSONResponse({'error':exc.code},status_code=422)

    @app.post('/v1/{operation}')
    async def operate(operation: str,request: Request):
        if operation not in operations:return JSONResponse({'error':'unknown_operation'},status_code=404)
        permitted=OPERATOR if request.state.role=='operator' else WORKER
        if operation not in permitted:return JSONResponse({'error':'role_forbidden'},status_code=403)
        try:
            body=bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body)>65536:return JSONResponse({'error':'payload_too_large'},status_code=413)
            payload=json.loads(body)
            if not isinstance(payload,dict):raise ValueError()
            # JSON booleans/IDs are strict; string 'false' must never acknowledge a writer.
            bool_fields={'finish':('quiescent',),'ack_control':('quiescent',),
                'ack_run_control':('quiescent',),'reconcile':('browser_quiescent',),
                'submission_intent':('fixture',)}.get(operation,())
            for key in bool_fields:
                if key in payload and type(payload[key]) is not bool:raise ValueError()
            for key in ('attempt_id','fence'):
                if key in payload and (type(payload[key]) is not int or payload[key]<1):raise ValueError()
            if request.state.role=='worker':
                worker_id=request.state.worker_id
                if 'worker_id' in payload and payload['worker_id']!=worker_id:
                    return JSONResponse({'error':'worker_identity_mismatch'},status_code=403)
                if operation not in READS and payload.get('worker_id')!=worker_id:
                    return JSONResponse({'error':'worker_identity_required'},status_code=403)
                if 'attempt_id' in payload and service.attempt(payload['attempt_id'])['worker_id']!=worker_id:
                    return JSONResponse({'error':'attempt_forbidden'},status_code=403)
                if operation in ('job','account_strategy','documents_status','candidate'):
                    with service.tx() as db:
                        if operation=='job':
                            allowed=db.execute('SELECT 1 FROM runs r JOIN run_jobs j ON r.id=j.run_id WHERE r.worker_id=? AND j.job_id=?',(worker_id,payload.get('job_id'))).fetchone()
                        elif operation=='documents_status':
                            allowed=db.execute('SELECT 1 FROM runs r JOIN run_jobs j ON r.id=j.run_id WHERE r.worker_id=? AND j.job_id=? AND r.identity_id=?',(worker_id,payload.get('job_id'),payload.get('identity_id'))).fetchone()
                        else:
                            allowed=db.execute('SELECT 1 FROM runs WHERE worker_id=? AND identity_id=?',(worker_id,payload.get('identity_id'))).fetchone()
                        if not allowed:return JSONResponse({'error':'context_forbidden'},status_code=403)
            # Only static bound methods above are reachable; no reflection on user strings.
            if operation == 'browser_observe':
                return JSONResponse(await run_in_threadpool(operations[operation], **payload))
            return JSONResponse(operations[operation](**payload))
        except ProtocolError as exc:
            code=409 if exc.code in ('owned_elsewhere','already_applied','stale_owner','reconciliation_required','idempotency_conflict','conflicting_finish','awaiting_worker') else 422
            return JSONResponse({'error':exc.code},status_code=code)
        except (TypeError,ValueError,KeyError):return JSONResponse({'error':'invalid_payload'},status_code=422)
        except sqlite3.Error as exc:
            return JSONResponse({'error':'local_runtime_upgrade_required' if 'local_runtime_upgrade_required' in str(exc) else 'database_operation_failed'},status_code=409)
    return app
