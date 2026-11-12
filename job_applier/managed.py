"""Agent-neutral application services over the existing SQLite models.

Every writer uses an independent connection and an IMMEDIATE transaction.
No browser, Hermes object, environment-derived DB or secret is imported here.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import hashlib
import json
import logging
import sys
import time
import uuid

from .managed_migrations import connect, migrate, database_busy


from .managed_shared import ProtocolError, uid, dumps, sanitize_legacy_profile
from .managed_events import EventServices
from .managed_accounts import AccountServices
from .managed_continuity import ContinuityServices
from .managed_settings import SettingsServices
from .managed_views import ViewServices
from .managed_learning import LearningServices
from .managed_documents import DocumentServices
from .managed_reports import ReportServices
from .managed_runtime import RuntimeServices
from .managed_context import ContextServices
from .managed_archive import ArchiveServices
from .managed_sessions import SessionServices, local_session
from .managed_questions import QuestionServices
from .managed_answer_library import AnswerLibraryServices
from .managed_queue import QueueServices
from .managed_discovery import DiscoveryServices
from .job_duplicates import DuplicateServices, matching_suppression, duplicate_error, audit_duplicate_admission
from .managed_versions import code_evidence
from .managed_redaction import safe_text, reject_secrets, provenance_text
from .managed_profiles import ProfileServices


def utc_now():
    return datetime.now(timezone.utc).isoformat()


from .managed_identity import canonical_url, job_key, RELATED, same_job_url, greenhouse_query_identity, workday_identity, linkedin_identity, ats_posting_key, observed_posting_key


class Service(EventServices, AccountServices, ContinuityServices, SettingsServices, ViewServices, LearningServices, DocumentServices, ReportServices, RuntimeServices, ContextServices, ArchiveServices, SessionServices, QuestionServices, AnswerLibraryServices, QueueServices, DiscoveryServices, DuplicateServices, ProfileServices):
    def __init__(self, db_path, *, instance_id=None, now_fn=utc_now):
        p=Path(db_path)
        if not p.is_absolute(): raise ProtocolError('absolute_db_path_required')
        if not p.is_file(): raise ProtocolError('instance_not_initialized')
        self.db_path=p.resolve()
        self.now=now_fn
        with self.read() as db:
            try: row=db.execute('SELECT * FROM instance').fetchone()
            except Exception as exc: raise ProtocolError('instance_not_initialized') from exc
            if row is None or (instance_id and row['id']!=instance_id): raise ProtocolError('instance_mismatch')
            self.instance_id=row['id']
            self.settings=json.loads(row['settings_json'])

    @classmethod
    def create(cls, db_path, *, instance_id, settings=None):
        reject_secrets(settings or {})
        p=Path(db_path)
        if not p.is_absolute(): raise ProtocolError('absolute_db_path_required')
        p.parent.mkdir(parents=True,exist_ok=True)
        # Exclusive creation, never overwrite an old DB or sidecar.
        if any(Path(str(p)+suffix).exists() for suffix in ('-wal','-shm','-journal')): raise FileExistsError(p)
        with p.open('xb'): pass
        from .database import DatabaseManager
        manager=DatabaseManager(str(p)); manager.close()
        migrate(p)
        effective={'mode':'development','submission_mode':'review','worker':'external','autofill':'simplify','screenshots':False,'timezone':'UTC'}
        effective.update(settings or {})
        if effective['mode']=='development' and effective['submission_mode']!='review': raise ProtocolError('development_submission_disabled')
        with connect(p) as db:
            db.execute('INSERT INTO instance VALUES (?,?,?)',(instance_id,dumps(effective),utc_now()))
        return cls(p,instance_id=instance_id)

    @contextmanager
    def tx(self):
        started=time.monotonic();acquired=None
        operation=sys._getframe(2).f_code.co_name  # Caller of contextlib.__enter__.
        db=connect(self.db_path)
        try:
            db.execute('BEGIN IMMEDIATE')
            acquired=time.monotonic()
            yield db
            db.commit()
        except Exception as exc:
            db.rollback()
            if database_busy(exc):
                logging.getLogger(__name__).warning('sqlite_contention operation=%s phase=%s elapsed_seconds=%.3f',
                    operation,'write' if acquired is not None else 'acquire',time.monotonic()-started)
            raise
        finally:
            db.close()
            elapsed=time.monotonic()-started
            if elapsed>=1:
                logging.getLogger(__name__).warning('sqlite_slow_transaction operation=%s elapsed_seconds=%.3f lock_wait_seconds=%.3f',
                    operation,elapsed,(acquired or time.monotonic())-started)

    @contextmanager
    def read(self):
        """A consistent read snapshot without reserving the single SQLite writer."""
        db=connect(self.db_path,readonly=True)
        try:
            db.execute('BEGIN')
            yield db
        finally:
            db.rollback()
            db.close()

    def health(self):
        with self.read() as db:
            settings=json.loads(db.execute('SELECT settings_json FROM instance WHERE id=?',(self.instance_id,)).fetchone()[0])
            schema=db.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0]
        return {'instance_id':self.instance_id,'db_path':str(self.db_path),'submission_mode':settings['submission_mode'],'settings':settings,'schema_version':schema,**code_evidence()}

    def job(self, job_id):
        with self.read() as db:
            r=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if not r: raise ProtocolError('job_not_found')
            return dict(r,assessment=self._assessment(db,job_id))

    def sources(self, job_id):
        with self.read() as db:
            return self._source_rows(db,job_id)

    def _source_rows(self, db, job_id):
        rows=[dict(r) for r in db.execute(
            'SELECT * FROM job_sources WHERE job_id=? ORDER BY julianday(discovered_at),rowid',(job_id,))]
        for row in rows:
            row['observations']=[dict(r) for r in db.execute(
                'SELECT * FROM source_observations WHERE source_record_id=? ORDER BY rowid',(row['id'],))]
        return rows

    def intake(self, *, url, source_type='manual', source_id=None, company=None, title=None, namespace=None, requisition_id=None, identity_evidence=None, producer=None, discovery_run_id=None, discovery_profile=None, **metadata):
        reject_secrets(metadata)
        reject_secrets([company,title,namespace,requisition_id,identity_evidence,source_type])
        canonical=canonical_url(url)
        if isinstance(source_id,str) and source_id.startswith(('https://','http://')):
            # An intake URL can legitimately use 'token' as a requisition identifier.
            canonical_url(source_id)
            reject_secrets(urlsplit(source_id).fragment)
        else:
            reject_secrets(source_id)
        if namespace and requisition_id and not identity_evidence: raise ProtocolError('identity_evidence_required')
        supplied_key=job_key(canonical,namespace,requisition_id)
        posting_key=ats_posting_key(canonical,namespace=namespace if identity_evidence else None,source_id=source_id)
        observed_key=observed_posting_key(canonical)
        key=posting_key or supplied_key
        url_key=job_key(canonical)
        compare_identity=linkedin_identity if linkedin_identity(canonical) else workday_identity if workday_identity(canonical) else greenhouse_query_identity
        query_identity=compare_identity(canonical)
        query_key=hashlib.sha256(dumps(['requisition_query',query_identity]).encode()).hexdigest() if query_identity else None
        now=self.now()
        with self.tx() as db:
            if posting_key:
                # Legacy importers can add URL-only rows after migration. Link
                # every matching posting before choosing a row, so an exact URL
                # match cannot hide another alias's recorded submission.
                for historical in db.execute('SELECT id,url,namespace,requisition_id FROM jobs').fetchall():
                    historical_key=ats_posting_key(historical['url'],namespace=historical['namespace'] if historical['requisition_id'] else None)
                    if historical_key==posting_key:
                        db.execute('INSERT OR IGNORE INTO job_identity_keys VALUES (?,?,?)',
                            (posting_key,historical['id'],'consistent_ats_posting_identity'))
            row=db.execute('SELECT j.* FROM jobs j JOIN job_identity_keys k ON k.job_id=j.id WHERE k.identity_key IN (?,?) ORDER BY (j.url=?) DESC,j.created_at,j.id LIMIT 1',(key,url_key,canonical)).fetchone()
            if not row and observed_key:
                row=db.execute('SELECT j.* FROM jobs j JOIN job_identity_keys k ON k.job_id=j.id WHERE k.identity_key=? ORDER BY j.created_at,j.id LIMIT 1',(observed_key,)).fetchone()
            if not row and posting_key and supplied_key!=key:
                # Keep older verified aliases, but a stale requisition label must
                # not combine two explicitly different ATS postings.
                candidates=db.execute('SELECT j.* FROM jobs j JOIN job_identity_keys k ON k.job_id=j.id WHERE k.identity_key=? ORDER BY j.created_at,j.id',(supplied_key,)).fetchall()
                row=next((r for r in candidates if ats_posting_key(r['url'],namespace=r['namespace']) in (None,posting_key)),None)
            query_matches=[]
            if query_identity and not posting_key:
                query_matches=[r for r in db.execute('SELECT * FROM jobs ORDER BY created_at,id')
                                 if compare_identity(r['url'])==query_identity]
                if not row and query_matches:row=query_matches[0]
            # Preserve old identity hashes; add this spelling as another alias.
            if not row and (urlsplit(canonical).hostname or '').endswith('.myworkdayjobs.com'):
                row=next((r for r in db.execute('SELECT * FROM jobs ORDER BY created_at,id') if same_job_url(r['url'],canonical)),None)
            if not row:
                job_id=uid()
                seq=db.execute('SELECT COALESCE(MAX(seq_id),0)+1 FROM jobs').fetchone()[0]
                db.execute('INSERT INTO jobs(id,seq_id,url,title,company,status,priority,notes,error,created_at,updated_at,identity_key,namespace,requisition_id,eligibility,metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(job_id,seq,canonical,title,company,'queued',0,'','',now,now,key,namespace,requisition_id,'held',dumps(metadata)))
            else:
                job_id=row['id']
                if namespace and requisition_id:
                    old_identity=(row['namespace'],str(row['requisition_id']))
                    new_identity=(namespace,str(requisition_id))
                    if (urlsplit(canonical).hostname or '').endswith('.myworkdayjobs.com'):
                        old_identity=tuple(str(v).casefold() for v in old_identity)
                        new_identity=tuple(str(v).casefold() for v in new_identity)
                    same_posting=posting_key and (ats_posting_key(row['url'],namespace=row['namespace'])==posting_key or
                        db.execute('SELECT 1 FROM job_identity_keys WHERE job_id=? AND identity_key=?',(job_id,posting_key)).fetchone())
                    if row['namespace'] and old_identity!=new_identity and not same_posting:raise ProtocolError('identity_conflict')
                    # The URL's posting identity outranks rediscovered labels.
                    # Preserve retained requisitions, including older numeric IDs.
                    if not row['namespace'] or not same_posting:
                        db.execute('UPDATE jobs SET namespace=?,requisition_id=? WHERE id=?',(namespace,str(requisition_id),job_id))
            for alias_key in {key,url_key}:
                db.execute('INSERT OR IGNORE INTO job_identity_keys VALUES (?,?,?)',(alias_key,job_id,safe_text(identity_evidence or 'normalized_url')))
            if observed_key:
                db.execute('INSERT OR IGNORE INTO job_identity_keys VALUES (?,?,?)',(observed_key,job_id,'observed_posting_identity'))
            if row and (company is not None or title is not None):
                self._enrich_job(db,row,company=company,title=title,source='explicit_intake',url=canonical)
            if row:
                # Rediscovery can supply previously missing posting facts. Preserve
                # all other metadata and never replace known facts with omissions.
                facts={k:metadata[k] for k in ('country','posted_at') if isinstance(metadata.get(k),str) and metadata[k].strip()}
                if facts:
                    saved=json.loads(self._get(db,'jobs',job_id)['metadata_json'] or '{}')
                    saved.update(facts)
                    db.execute('UPDATE jobs SET metadata_json=? WHERE id=?',(dumps(saved),job_id))
            if query_key and not posting_key:
                # Retain every historical job row and link existing duplicates so
                # an older applied/uncertain attempt cannot be bypassed by a form URL.
                for related_id in {job_id}|{r['id'] for r in query_matches}:
                    db.execute('INSERT OR IGNORE INTO job_identity_keys VALUES (?,?,?)',
                                 (query_key,related_id,'consistent_requisition_identity'))
            db.execute('INSERT OR IGNORE INTO job_sources VALUES (?,?,?,?,?,?)',(uid(),job_id,source_type,source_id or canonical,urlunsplit(urlsplit(url.strip())._replace(fragment='')),now))
            # Store each supplying process/run separately from the first source sighting.
            # Missing optional attribution never changes intake or execution eligibility.
            context=tuple(provenance_text(v) for v in (producer,discovery_run_id,discovery_profile))
            if any(context):
                source=db.execute('SELECT id FROM job_sources WHERE job_id=? AND source_type=? AND source_id=? AND original_url=?',
                    (job_id,source_type,source_id or canonical,urlunsplit(urlsplit(url.strip())._replace(fragment='')))).fetchone()
                if source and not db.execute('''SELECT 1 FROM source_observations WHERE source_record_id=?
                        AND producer IS ? AND discovery_run_id IS ? AND discovery_profile IS ?''',(source['id'],*context)).fetchone():
                    db.execute('INSERT INTO source_observations VALUES (?,?,?,?,?,?)',(uid(),source['id'],*context,now))
            result=dict(db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone())
        # Optional local inference is outside the write transaction. If unavailable,
        # exact matching and the existing application flow remain available.
        config=getattr(self,'executor_config',{})
        if config.get('duplicate_matching'):
            from .job_duplicates import DuplicateMatcher
            try:DuplicateMatcher(self,config).refresh(job_id=job_id)
            except Exception:logging.getLogger(__name__).warning('duplicate_intake_refresh_unavailable')
        return result

    def update_job_url(self, *, job_id, url, expected_url):
        """Correct a saved posting link without replacing its identity or history."""
        canonical=canonical_url(url)
        new_key=job_key(canonical)
        identity=linkedin_identity(canonical) or workday_identity(canonical) or greenhouse_query_identity(canonical)
        keys={new_key}
        if identity:keys.add(hashlib.sha256(dumps(['requisition_query',identity]).encode()).hexdigest())
        with self.tx() as db:
            job=self._get(db,'jobs',job_id)
            if job['url']!=expected_url:raise ProtocolError('job_url_changed','This URL changed since you opened the editor. Reopen it to edit the latest URL.')
            if job['url']==canonical:return dict(job)
            posting_key=ats_posting_key(canonical,namespace=job['namespace'])
            if posting_key:keys.add(posting_key)
            # Reuse intake identity rules; never silently combine two saved jobs.
            conflict=any(db.execute('SELECT 1 FROM job_identity_keys WHERE identity_key=? AND job_id<>?',(key,job_id)).fetchone() for key in keys)
            if conflict or any(same_job_url(row['url'],canonical) for row in db.execute('SELECT url FROM jobs WHERE id<>?',(job_id,))):
                raise ProtocolError('job_url_in_use','That URL belongs to another saved job. Open that job to edit its link.')
            try:keys.add(job_key(job['url']))
            except (ValueError,ProtocolError):pass  # A malformed legacy URL can still be corrected.
            for key in keys:
                db.execute('INSERT OR IGNORE INTO job_identity_keys VALUES (?,?,?)',(key,job_id,'operator_url_correction'))
            now=self.now();metadata=json.loads(job['metadata_json'] or '{}')
            history=metadata.get('url_history')
            if not isinstance(history,list):history=[]
            metadata['url_history']=[*history,{'previous_url':job['url'],'url':canonical,'changed_at':now,'source':'operator'}]
            db.execute('UPDATE jobs SET url=?,metadata_json=?,updated_at=? WHERE id=?',(canonical,dumps(metadata),now,job_id))
            return dict(self._get(db,'jobs',job_id))

    def _enrich_job(self,db,job,*,url,company=None,title=None,source,preview=False):
        """Keep identity/outcomes and explicit labels; retain per-label provenance."""
        from .managed_identity import is_same_application_scope
        if not is_same_application_scope(job['url'],url):
            alias=db.execute(RELATED+'SELECT 1 FROM related r JOIN job_identity_keys k ON k.job_id=r.id WHERE k.identity_key=?',
                (job['id'],job_key(canonical_url(url)))).fetchone()
            if not alias:raise ProtocolError('metadata_job_mismatch')
        if source not in ('employer_posting','simplify_job_card','retained_answer_history','explicit_intake'):
            raise ProtocolError('metadata_source_required')
        reject_secrets([company,title])
        proposed={};conflicts=[]
        for field,value in {'company':company,'title':title}.items():
            if value is None:continue
            if not isinstance(value,str) or not value.strip() or len(value)>300:raise ProtocolError('invalid_job_label')
            value=' '.join(value.split())
            if not job[field]:proposed[field]=value
            elif job[field]!=value:conflicts.append(field)
        if proposed and not preview:
            meta=json.loads(job['metadata_json'] or '{}');sources=meta.setdefault('label_sources',{})
            for field in proposed:sources[field]={'source':source,'url':canonical_url(url),'observed_at':self.now()}
            meta['label_discovery']={'status':'identified','observed_at':self.now()}
            db.execute('UPDATE jobs SET company=?,title=?,metadata_json=?,updated_at=? WHERE id=?',
                (proposed.get('company',job['company']),proposed.get('title',job['title']),dumps(meta),self.now(),job['id']))
        return {'changed':bool(proposed) and not preview,'proposed':proposed,'conflicts':conflicts,
                'job':dict(self._get(db,'jobs',job['id']))}

    def enrich_job(self,job_id,*,url,company=None,title=None,source,preview=False):
        with self.tx() as db:
            return self._enrich_job(db,self._get(db,'jobs',job_id),url=url,company=company,title=title,source=source,preview=preview)

    def observe_job_metadata(self,attempt_id,*,worker_id,fence,metadata):
        if not isinstance(metadata,dict):raise ProtocolError('invalid_job_metadata')
        with self.tx() as db:
            a=self._owner(db,attempt_id,worker_id,fence);job=self._get(db,'jobs',a['job_id'])
            if metadata:
                return self._enrich_job(db,job,**{k:metadata.get(k) for k in ('url','company','title','source')})
            meta=json.loads(job['metadata_json'] or '{}')
            if not meta.get('label_discovery'):
                meta['label_discovery']={'status':'unavailable','observed_at':self.now()}
                db.execute('UPDATE jobs SET metadata_json=? WHERE id=?',(dumps(meta),job['id']))
            return {'changed':False,'job':dict(job)}

    def backfill_job_metadata(self,*,records,apply=False):
        """Operator-selected retained evidence; preview is the default, no outcome edits."""
        if type(apply) is not bool or not isinstance(records,list) or len(records)>500:raise ProtocolError('invalid_metadata_backfill')
        rows=[]
        with self.tx() as db:
            for record in records:
                try:
                    job=self._get(db,'jobs',record['job_id'])
                    attempt=self._get(db,'application_attempts',record['attempt_id'])
                    if attempt['job_id']!=job['id']:raise ProtocolError('metadata_attempt_mismatch')
                    result=self._enrich_job(db,job,url=record['job_url'],company=record.get('company'),
                        title=record.get('job_title'),source='retained_answer_history',preview=not apply)
                    rows.append({'job_id':job['id'],**{k:result[k] for k in ('changed','proposed','conflicts')}})
                except (KeyError,TypeError,ProtocolError) as exc:
                    rows.append({'job_id':record.get('job_id') if isinstance(record,dict) else None,
                                 'skipped':getattr(exc,'code','invalid_metadata_record')})
        return {'preview':not apply,'rows':rows}

    @staticmethod
    def _get(db, table, key):
        # table comes only from static method declarations in this module.
        row=db.execute(f'SELECT * FROM {table} WHERE id=?',(key,)).fetchone()
        if row is None: raise ProtocolError('not_found')
        return row

    def identity(self, *, identity_id, person_key, email, profile, state='active'):
        if state not in ('active','legacy','disabled') or not person_key or '@' not in email:
            raise ProtocolError('invalid_identity')
        reject_secrets(profile)
        encoded=dumps(profile)
        with self.tx() as db:
            previous=db.execute('SELECT * FROM candidates WHERE id=?',(identity_id,)).fetchone()
            if previous and (previous['email'].casefold()!=email.casefold() or previous['person_key']!=person_key):
                raise ProtocolError('identity_immutable')
            db.execute('INSERT INTO candidates VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,profile_json=excluded.profile_json,profile_hash=excluded.profile_hash', (identity_id,person_key,email,state,encoded,hashlib.sha256(encoded.encode()).hexdigest()))
            self._reconcile_answers(db, identity_id)
            return dict(self._get(db,'candidates',identity_id))

    def candidate(self, identity_id):
        with self.read() as db:
            cand = dict(self._get(db, 'candidates', identity_id))
            cand['profile'] = json.loads(cand['profile_json'])
            asset = db.execute("SELECT * FROM document_assets WHERE identity_id=? AND kind='resume' ORDER BY created_at DESC LIMIT 1", (identity_id,)).fetchone()
            from .managed_learning import public_record
            cand['resume_asset'] = public_record(asset) if asset else None
            cand['default_resume'] = cand['resume_asset']
            return cand

    def import_profile(self, data, *, identity_id=None, person_key=None):
        sanitized, skipped = sanitize_legacy_profile(data)
        identity_sec = sanitized.get('identity') or {}
        email = identity_sec.get('email') or (data.get('email') if isinstance(data, dict) else None)
        if not email or '@' not in email:
            raise ProtocolError('invalid_identity')
        import re
        pk = person_key or identity_sec.get('full_name') or email.split('@')[0]
        pk = re.sub(r'[^A-Za-z0-9_.-]', '_', str(pk).strip()) or 'candidate'
        target_id = identity_id
        with self.tx() as db:
            if target_id:
                prev = db.execute('SELECT * FROM candidates WHERE id=?', (target_id,)).fetchone()
                if prev:
                    if prev['email'].casefold() != email.casefold():
                        match = db.execute('SELECT * FROM candidates WHERE email=? COLLATE NOCASE', (email,)).fetchone()
                        target_id = match['id'] if match else f"cand-{hashlib.sha256(email.casefold().encode()).hexdigest()[:12]}"
                    elif not person_key:
                        pk = prev['person_key']
            else:
                match = db.execute('SELECT * FROM candidates WHERE email=? COLLATE NOCASE', (email,)).fetchone()
                target_id = match['id'] if match else f"cand-{hashlib.sha256(email.casefold().encode()).hexdigest()[:12]}"
                if match and not person_key:
                    pk = match['person_key']
        cand = self.identity(identity_id=target_id, person_key=pk, email=email, profile=sanitized)
        return {
            'identity_id': cand['id'],
            'email': cand['email'],
            'candidate': cand,
            'skipped': skipped,
            'profile_hash': cand['profile_hash'],
            'file_sync': self.sync_profile_file(identity_id=cand['id'])
        }

    def eligibility(self, job_id, decision, *, reason):
        if decision not in ('ready','held','excluded') or not reason: raise ProtocolError('invalid_eligibility')
        with self.tx() as db:
            job=self._get(db,'jobs',job_id)
            if job['status'] in ('running','applied','already_applied'): raise ProtocolError('protected_job')
            db.execute('UPDATE jobs SET eligibility=?,intervention_reason=? WHERE id=?',(decision,safe_text(reason),job_id))
            return dict(self._get(db,'jobs',job_id))

    def _assert_not_suppressed(self, db, job_id, identity_id=None):
        prior=db.execute(RELATED+"SELECT r.id FROM related r JOIN jobs j ON j.id=r.id LEFT JOIN submission_ledger l ON l.job_id=r.id WHERE l.job_id IS NOT NULL OR j.status IN ('applied','already_applied') LIMIT 1",(job_id,)).fetchone()
        if prior:raise duplicate_error(job_id,prior['id'])
        attempts=db.execute(RELATED+'SELECT a.* FROM related r JOIN application_attempts a ON a.job_id=r.id',
                            (job_id,)).fetchall()
        # Past attempts suppress another request only for recorded success.
        # Uncertainty stays in history; explicit operator cancellation is below.
        accepted=next((attempt for attempt in attempts if self._submission_state(db,attempt)['state']=='accepted'),None)
        if accepted:raise duplicate_error(job_id,accepted['job_id'])
        # Explicit operator cancellation is reversible and survives rediscovery.
        # A failed attempt never sets this disposition automatically.
        if db.execute(RELATED+"SELECT 1 FROM related r JOIN jobs j ON j.id=r.id WHERE j.disposition='canceled' LIMIT 1",(job_id,)).fetchone():
            raise ProtocolError('job_canceled')
        duplicate=matching_suppression(self,db,job_id,identity_id=identity_id)
        if duplicate:raise duplicate_error(job_id,duplicate[1],match=duplicate[0],code=duplicate[2])

    def _eligible(self, db, job_id, settings=None, exclude_session=None, identity_id=None):
        job=self._get(db,'jobs',job_id)
        policy=settings or self.settings
        if (job['company'] or '').casefold().strip() in {x.casefold().strip() for x in policy.get('excluded_companies',[])}:
            raise ProtocolError('company_excluded')
        country=json.loads(job['metadata_json'] or '{}').get('country')
        if country and policy.get('market_countries') and country not in policy['market_countries']:
            raise ProtocolError('market_incompatible')
        self._assert_not_suppressed(db,job_id,identity_id=identity_id)
        if db.execute('SELECT 1 FROM job_archives WHERE job_id=?',(job_id,)).fetchone():raise ProtocolError('job_archived')
        if job['eligibility']!='ready': raise ProtocolError('not_ready')
        return job

    @audit_duplicate_admission
    def request_run(self, *, request_id, job_ids, identity_id, browser_profile):
        if not request_id or not job_ids or len(job_ids)!=len(set(job_ids)) or not browser_profile:
            raise ProtocolError('invalid_run')
        request_key=dumps([job_ids,identity_id,browser_profile])
        now=self.now()
        with self.tx() as db:
            old=db.execute('SELECT * FROM runs WHERE request_id=?',(request_id,)).fetchone()
            if old:
                if old['request_key']!=request_key: raise ProtocolError('idempotency_conflict')
                return dict(old)
            candidate=self._get(db,'candidates',identity_id)
            if candidate['state']!='active': raise ProtocolError('identity_inactive')
            settings=self._settings_record(db)['values']
            for key in job_ids: self._eligible(db,key,settings,identity_id=identity_id)
            run_id=uid()
            db.execute('INSERT INTO runs(id,request_id,request_key,identity_id,browser_profile,state,requested_at,settings_json) VALUES (?,?,?,?,?,?,?,?)',(run_id,request_id,request_key,identity_id,browser_profile,'awaiting_worker',now,dumps(settings)))
            for position,key in enumerate(job_ids):
                db.execute('INSERT INTO run_jobs(run_id,job_id,position) VALUES (?,?,?)',(run_id,key,position))
            return dict(self._get(db,'runs',run_id))

    def next_request(self, browser_profile):
        if not browser_profile or not isinstance(browser_profile, str):
            raise ProtocolError('invalid_browser_profile')
        with self.tx() as db:
            row = db.execute(
                "SELECT * FROM runs WHERE browser_profile=? AND state='awaiting_worker' AND control='running' ORDER BY requested_at ASC LIMIT 1",
                (browser_profile,)
            ).fetchone()
            if not row:
                return None
            snapshot = json.loads(row['settings_json'])
            model = snapshot.get('reasoning_model')
            provider = snapshot.get('reasoning_provider')
            effort = snapshot.get('reasoning_effort', 'low')
            return {
                'run_id': row['id'],
                'model': model,
                'provider': provider,
                'effort': effort,
                'reasoning_effort': effort,
                'requested_model': model,
                'requested_provider': provider,
                'requested_effort': effort,
                'settings': snapshot,
            }

    def accept_run(self, run_id, *, worker_id, session_id, capabilities):
        reject_secrets(capabilities)
        with self.tx() as db:
            run=self._get(db,'runs',run_id)
            self._reasoning_matches(run,capabilities)
            required=('skill_version','provider','model','telemetry')
            if capabilities.get('protocol')!=1 or not all(capabilities.get(k) for k in required) or capabilities.get('browser_profile')!=run['browser_profile']:
                raise ProtocolError('unsupported_capability')
            if run['state']!='awaiting_worker':
                if run['worker_id']==worker_id and run['session_id']==session_id: return dict(run)
                raise ProtocolError('owned_elsewhere')
            if not worker_id or not session_id: raise ProtocolError('worker_identity_required')
            db.execute("UPDATE runs SET state='accepted',accepted_at=?,worker_id=?,session_id=?,capabilities_json=? WHERE id=?",(self.now(),worker_id,session_id,dumps(capabilities),run_id))
            db.execute('INSERT INTO run_sessions(run_id,worker_id,session_id,started_at) VALUES (?,?,?,?)',(run_id,worker_id,session_id,self.now()))
            return dict(self._get(db,'runs',run_id))

    def _expiry(self, settings=None):
        from datetime import timedelta
        return (datetime.fromisoformat(self.now())+timedelta(seconds=(settings if settings is not None else self.settings).get('lease_seconds',60))).isoformat()

    def claim(self, run_id, *, worker_id):
        now=self.now()
        with self.tx() as db:
            run=self._get(db,'runs',run_id)
            if self._has_local_schema(db) and db.execute('SELECT 1 FROM application_sessions WHERE run_id=?',(run_id,)).fetchone():
                raise ProtocolError('local_session_requires_start')
            self._legacy_workspace_guard(db,run['browser_profile'])
            if run['state']=='awaiting_worker': raise ProtocolError('awaiting_worker')
            if run['worker_id']!=worker_id: raise ProtocolError('owned_elsewhere')
            if run['control']!='running': raise ProtocolError(run['control'])
            if run['state']=='completed': return None
            if run['state'] not in ('accepted','active'): raise ProtocolError('run_not_active')
            lease=db.execute('SELECT * FROM browser_leases WHERE profile=?',(run['browser_profile'],)).fetchone()
            if lease and lease['state']!='released':
                if lease['state']=='quarantined' or lease['expires_at']<=now: raise ProtocolError('reconciliation_required')
                raise ProtocolError('owned_elsewhere')
            pending=db.execute("SELECT job_id FROM run_jobs WHERE run_id=? AND state='pending' ORDER BY position LIMIT 1",(run_id,)).fetchone()
            if not pending:
                db.execute("UPDATE runs SET state='completed',ended_at=? WHERE id=?",(now,run_id))
                return None
            snapshot=json.loads(run['settings_json'])
            job=self._eligible(db,pending['job_id'],snapshot,identity_id=run['identity_id'])
            if db.execute('SELECT 1 FROM application_attempts WHERE job_id=? AND completed_at IS NULL',(job['id'],)).fetchone():
                raise ProtocolError('owned_elsewhere')
            candidate=self._get(db,'candidates',run['identity_id'])
            if candidate['state']!='active': raise ProtocolError('identity_inactive')
            fence=(lease['generation'] if lease else 0)+1
            attempt_id=self._create_attempt(db,run,job,candidate,fence,now)
            db.execute("INSERT INTO browser_leases VALUES (?,?,?,?,?,?) ON CONFLICT(profile) DO UPDATE SET attempt_id=excluded.attempt_id,worker_id=excluded.worker_id,generation=excluded.generation,expires_at=excluded.expires_at,state=excluded.state",(run['browser_profile'],attempt_id,worker_id,fence,self._expiry(snapshot),'active'))
            db.execute("UPDATE jobs SET status='running',started_at=?,updated_at=? WHERE id=?",(now,now,job['id']))
            db.execute("UPDATE run_jobs SET state='active' WHERE run_id=? AND job_id=?",(run_id,job['id']))
            db.execute("UPDATE runs SET state='active',started_at=COALESCE(started_at,?) WHERE id=?",(now,run_id))
            result=dict(self._get(db,'application_attempts',attempt_id))
            result['settings_hash']=hashlib.sha256(result['settings_json'].encode()).hexdigest()
            return result

    def _create_attempt(self, db, run, job, candidate, fence, now, workflow='external'):
        """Shared attempt snapshot; caller owns only the short reservation transaction."""
        args=(job['id'],'unknown',workflow,now,run['id'],run['identity_id'],run['worker_id'],run['session_id'],run['browser_profile'],fence,now,now,run['settings_json'],candidate['profile_json'],run['capabilities_json'])
        return db.execute('INSERT INTO application_attempts(job_id,platform,workflow,started_at,run_id,identity_id,worker_id,session_id,browser_profile,fence,heartbeat_at,progress_at,settings_json,profile_json,versions_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',args).lastrowid

    def attempt(self, attempt_id):
        with self.read() as db:
            attempt=dict(self._get(db,'application_attempts',attempt_id))
            return dict(attempt,submission_pending=self._submission_pending(db,attempt))

    def _owner(self, db, attempt_id, worker_id, fence, *, completed=False):
        a=self._get(db,'application_attempts',attempt_id)
        if a['worker_id']!=worker_id or a['fence']!=fence: raise ProtocolError('stale_owner')
        if completed and a['completed_at']: return a
        if a['completed_at']: raise ProtocolError('attempt_completed')
        session=local_session(db,attempt_id)
        if session:
            self._local_owner(db,session)
            return a
        self._legacy_workspace_guard(db,a['browser_profile'])
        lease=db.execute('SELECT * FROM browser_leases WHERE profile=?',(a['browser_profile'],)).fetchone()
        if not lease or lease['generation']!=fence or lease['attempt_id']!=attempt_id: raise ProtocolError('stale_owner')
        if lease['state']!='active' or lease['expires_at']<=self.now(): raise ProtocolError('reconciliation_required')
        return a

    def heartbeat(self, attempt_id, *, worker_id, fence):
        with self.tx() as db:
            a=self._owner(db,attempt_id,worker_id,fence)
            db.execute('UPDATE application_attempts SET heartbeat_at=? WHERE id=?',(self.now(),attempt_id))
            if local_session(db,attempt_id):
                db.execute('UPDATE application_sessions SET driver_seen_at=? WHERE attempt_id=?',(self.now(),attempt_id))
            else:
                db.execute('UPDATE browser_leases SET expires_at=? WHERE profile=?',(self._expiry(json.loads(a['settings_json'])),a['browser_profile']))
            run=self._get(db,'runs',a['run_id'])
            return {'control':run['control'],'heartbeat_at':self.now(),'last_progress_at':a['progress_at']}

    def submission_intent(self, attempt_id, *, worker_id, fence, evidence, fixture=False):
        with self.tx() as db:
            a=self._owner(db,attempt_id,worker_id,fence)
            if not self._documents_status(db,a['job_id'],a['identity_id'],attempt_id)['ready']:raise ProtocolError('required_document_missing')
            if self._get(db,'runs',a['run_id'])['control']!='running':raise ProtocolError('control_pending')
            settings=json.loads(a['settings_json'])
            # fixture is allowed only in an explicitly synthetic development instance.
            if not (fixture and settings['mode']=='development') and settings['submission_mode']!='submit':
                raise ProtocolError('submission_not_authorized')
            if not evidence: raise ProtocolError('evidence_required')
            db.execute('UPDATE application_attempts SET submit_intent_at=? WHERE id=?',(self.now(),attempt_id))
            self._append_event(db,a,worker_id=worker_id,fence=fence,event_id=uid(),action_id=None,event_type='checkpoint',
                observed_at=self.now(),duration_seconds=None,payload={'operation':'submission_intent','status':'pending','phase':'submission'})
            return dict(self._get(db,'application_attempts',attempt_id))

    def _complete(self, db, a, outcome, evidence, *, quiescent, finish_key, reconciled=False):
        now=self.now()
        completed=a['completed_at'] if reconciled and a['completed_at'] else now
        duration=max(0,(datetime.fromisoformat(completed)-datetime.fromisoformat(a['started_at']).replace(tzinfo=timezone.utc)).total_seconds())
        uncertain=a['uncertain_duration'] if reconciled and a['completed_at'] else int(reconciled)
        db.execute('UPDATE application_attempts SET outcome=?,evidence=?,completed_at=?,duration_seconds=?,finish_key=?,uncertain_duration=? WHERE id=?',(outcome,evidence,completed,duration,finish_key,uncertain,a['id']))
        if outcome in ('applied','already_applied'):
            person=self._get(db,'candidates',a['identity_id'])['person_key']
            db.execute('INSERT OR IGNORE INTO submission_ledger VALUES (?,?,?,?)',(a['job_id'],person,evidence,now))
        # The posting summarizes all attempts. A later failure cannot erase a
        # successful submission, and one ended attempt cannot hide another run.
        success=db.execute(RELATED+'SELECT l.recorded_at FROM related r JOIN submission_ledger l ON l.job_id=r.id LIMIT 1',(a['job_id'],)).fetchone()
        active=db.execute('SELECT 1 FROM application_attempts WHERE job_id=? AND completed_at IS NULL',(a['job_id'],)).fetchone()
        latest=db.execute('SELECT outcome,completed_at FROM application_attempts WHERE job_id=? ORDER BY id DESC LIMIT 1',(a['job_id'],)).fetchone()
        status=('already_applied' if outcome=='already_applied' else 'applied') if success else 'running' if active else latest['outcome']
        job_completed=success[0] if success else None if active else latest['completed_at']
        db.execute('UPDATE jobs SET status=?,completed_at=?,updated_at=? WHERE id=?',(status,job_completed,now,a['job_id']))
        db.execute('UPDATE run_jobs SET state=? WHERE run_id=? AND job_id=?',(outcome,a['run_id'],a['job_id']))
        # A late reconciliation may NEVER release a newer owner's browser.
        # Browser ownership and employer submission evidence are independent.
        state='released' if quiescent else 'quarantined'
        db.execute('UPDATE browser_leases SET state=? WHERE profile=? AND generation=? AND attempt_id=?',(state,a['browser_profile'],a['fence'],a['id']))
        if local_session(db,a['id']):
            # The host must stop the owned browser before freeing this workspace.
            db.execute("UPDATE application_sessions SET state='finishing',reason=? WHERE attempt_id=? AND ended_at IS NULL",(outcome,a['id']))
        return dict(self._get(db,'application_attempts',a['id']))

    def finish(self, attempt_id, *, worker_id, fence, outcome, evidence='', quiescent=False):
        if outcome not in ('applied','already_applied','ready_for_review','blocked','skipped','failed','interrupted','submission_unknown'):
            raise ProtocolError('invalid_outcome')
        evidence=safe_text(evidence)
        key=hashlib.sha256(dumps([outcome,evidence,quiescent]).encode()).hexdigest()
        with self.tx() as db:
            a=self._owner(db,attempt_id,worker_id,fence,completed=True)
            if a['completed_at']:
                if a['finish_key']==key: return dict(a)
                raise ProtocolError('conflicting_finish')
            if quiescent and not self._is_quiescent(db,a): raise ProtocolError('writers_not_quiescent')
            if outcome in ('applied','already_applied') and not evidence: raise ProtocolError('evidence_required')
            if outcome=='applied' and not a['submit_intent_at']: raise ProtocolError('submission_intent_required')
            if self._submission_pending(db,a) and outcome not in ('applied','already_applied'): outcome='submission_unknown'
            return self._complete(db,a,outcome,evidence,quiescent=quiescent,finish_key=key)

    def reconcile(self, attempt_id, *, outcome, evidence, browser_quiescent, source='user_reported'):
        if source not in ('employer','simplify','user_reported'):raise ProtocolError('invalid_evidence_source')
        evidence=safe_text(evidence)
        if outcome not in ('applied','already_applied','interrupted','failed','blocked') or not evidence or not browser_quiescent:
            raise ProtocolError('reconciliation_evidence_required')
        with self.tx() as db:
            a=self._get(db,'application_attempts',attempt_id)
            session=local_session(db,attempt_id)
            if session and not session['ended_at']:raise ProtocolError('local_session_stop_required')
            if db.execute('SELECT 1 FROM application_attempts WHERE job_id=? AND id>?',(a['job_id'],a['id'])).fetchone():
                raise ProtocolError('newer_attempt_exists')
            if a['outcome'] in ('applied','already_applied'):
                if outcome!=a['outcome']:raise ProtocolError('already_applied')
                self._settle_reconciled_queue(db,a)
                # Browser acknowledgement is distinct from immutable success/history.
                changed=db.execute("UPDATE browser_leases SET state='released' WHERE profile=? AND generation=? AND attempt_id=? AND state='quarantined'",(a['browser_profile'],a['fence'],a['id'])).rowcount
                if changed:
                    now=self.now()
                    payload=dumps({'operation':'browser_reconciled','status':'quiescent','evidence':evidence})
                    audit_key=hashlib.sha256(dumps([a['id'],'operator',now,payload]).encode()).hexdigest()
                    db.execute('INSERT INTO managed_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(uid(),a['id'],a['run_id'],None,'operator','control',now,now,None,1,payload,audit_key))
                return dict(a)
            key=hashlib.sha256(dumps(['reconciled',outcome,evidence,source]).encode()).hexdigest()
            if a['completed_at'] and a['finish_key']==key:return dict(a)
            result=self._complete(db,a,outcome,evidence,quiescent=True,finish_key=key,reconciled=True)
            if outcome in ('applied','already_applied'):self._settle_reconciled_queue(db,a)
            now=self.now()
            payload=dumps({'operation':'submission_reconciled','status':outcome,'evidence':evidence,'source':source})
            audit_key=hashlib.sha256(dumps([a['id'],'operator',now,payload]).encode()).hexdigest()
            db.execute('INSERT INTO managed_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                       (uid(),a['id'],a['run_id'],None,'operator','outcome',now,now,None,0,payload,audit_key))
            return result

    @audit_duplicate_admission
    def retry(self, job_id):
        with self.tx() as db:
            job=self._get(db,'jobs',job_id)
            self._assert_not_suppressed(db,job_id)
            db.execute("UPDATE jobs SET status=CASE WHEN EXISTS(SELECT 1 FROM application_attempts WHERE job_id=? AND completed_at IS NULL) THEN 'running' ELSE 'queued' END,updated_at=? WHERE id=?",(job_id,self.now(),job_id))
            return dict(self._get(db,'jobs',job_id))
