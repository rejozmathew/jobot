"""Small shared protocol primitives; no runtime initialization."""
import json
import uuid
from functools import wraps


def submission_pending(attempt, events=()):
    """Unconfirmed dispatch state for observation and reporting, never a write lock."""
    return submission_state(attempt,events)['state'] in ('pending','accepted')


def submission_state(attempt,events=()):
    """Project dispatch and observation history for reporting, never permission.

    Uncertainty remains in history. A fresh view of unfinished work may describe
    progress without erasing a click or requiring a special rejection operation.
    """
    attempt=dict(attempt);state='pending' if attempt.get('submit_intent_at') else 'none'
    dispatch=None;resolved=None;accepted=attempt.get('outcome') in ('applied','already_applied')
    for raw in events:
        row=dict(raw)
        if row.get('stale'):continue
        payload=json.loads(row.get('payload_json','{}'));operation=payload.get('operation')
        if operation=='submission_confirmed' and payload.get('status') in ('applied','already_applied'):accepted=True
        if operation=='submission_reconciled' and payload.get('status') in ('applied','already_applied'):accepted=True
        if operation=='submission_intent':state='pending';dispatch=None;resolved=None
        elif operation=='submission_observation' and payload.get('status')=='incomplete':
            state='incomplete';resolved=payload
        elif operation=='submission_observation' and payload.get('status')=='pending' and attempt.get('submit_intent_at'):
            state='pending';resolved=None
        elif operation=='submission_click':
            dispatch=dict(payload,observed_at=row.get('observed_at'));resolved=None
            state='not_executed' if payload.get('status')=='not_executed' else 'pending'
        elif operation=='submission_resolution' and payload.get('status')=='rejected' and dispatch:
            if (payload.get('source')=='employer' and payload.get('resolution')=='fresh_employer_rejection' and
                payload.get('reason_code') in ('invalid_security_code','expired_security_code','required_fields') and
                all(dispatch.get(k) and payload.get(k)==dispatch[k] for k in ('dispatch_id','document_id','frame_id'))):
                from datetime import datetime
                try:
                    if datetime.fromisoformat(row['observed_at'].replace('Z','+00:00'))<datetime.fromisoformat(dispatch['observed_at'].replace('Z','+00:00')):continue
                except (KeyError,TypeError,ValueError):continue
                state='rejected';resolved=payload
    return {'state':'accepted' if accepted else state,'dispatch':dispatch,'resolution':resolved}


class ProtocolError(ValueError):
    def __init__(self, code, detail=''):
        self.code = code
        super().__init__(code + (': ' + detail if detail else ''))


def legacy_writer(method):
    """Legacy entrypoints cannot bypass managed ownership or overwrite its history."""
    @wraps(method)
    def guarded(self, *args, **kwargs):
        manager = getattr(self, 'db_manager', None) or getattr(self, 'db', None)
        manager.require_legacy()
        return method(self, *args, **kwargs)
    return guarded


def uid():
    return str(uuid.uuid4())


def dumps(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


LEGACY_IDENTITY_FIELDS = frozenset({
    'full_name', 'first_name', 'middle_name', 'last_name', 'preferred_name',
    'email', 'phone', 'country code', 'address', 'location', 'linkedin', 'website', 'github'
})
LEGACY_ALLOWED_SECTIONS = frozenset({
    'identity', 'summary', 'years_experience', 'target_roles', 'industries',
    'skills', 'leadership_scope', 'work_authorization', 'work_preferences',
    'dealbreakers', 'eeo_information', 'standard_answers', 'experience',
    'education', 'certifications', 'projects', 'languages', 'links', 'resume', 'profile_answer_sources'
})
LEGACY_EXCLUDED_SECTIONS = frozenset({
    'accounts', 'cover_letter', 'login', 'greenhouse',
    'automation_preferences', 'application_answer_policy'
})


def sanitize_legacy_profile(data):
    from .managed_redaction import reject_secrets
    if not isinstance(data, dict):
        raise ProtocolError('invalid_profile_data')
    sanitized = {}
    skipped = []

    for key, value in data.items():
        if key=='application_answer_policy':
            from .application_answers import approved_policy
            policy=approved_policy(value)
            if policy:sanitized[key]=policy
            else:skipped.append(key)
            continue
        if key in LEGACY_EXCLUDED_SECTIONS:
            skipped.append(key)
            continue
        if key not in LEGACY_ALLOWED_SECTIONS:
            skipped.append(key)
            continue

        if key == 'identity':
            if isinstance(value, dict):
                clean_identity = {}
                for ik, iv in value.items():
                    if ik in LEGACY_IDENTITY_FIELDS:
                        clean_identity[ik] = iv
                    else:
                        skipped.append(f"identity.{ik}")
                sanitized['identity'] = clean_identity
            else:
                skipped.append('identity')
        elif key == 'resume':
            if isinstance(value, dict):
                clean_resume = {}
                if 'path' in value:
                    clean_resume['path'] = value['path']
                if 'text' in value:
                    skipped.append('resume.text')
                for rk in value:
                    if rk not in ('path', 'text'):
                        skipped.append(f"resume.{rk}")
                sanitized['resume'] = clean_resume
            else:
                skipped.append('resume')
        else:
            sanitized[key] = value

    reject_secrets(sanitized)
    return sanitized, sorted(skipped)
