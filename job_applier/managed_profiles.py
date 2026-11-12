"""Operator profile editing, sourced suggestions, and an optional private export.

The managed database remains authoritative. Export errors do not undo a saved
profile or affect application execution. Historical attempts and scoped library
entries are never rewritten by this module.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .managed_shared import LEGACY_ALLOWED_SECTIONS, ProtocolError, dumps
from .managed_redaction import reject_secrets
from .profile_questions import FIELDS, field_for_question, get_value, schema, set_value, source_value, valid_value, value_for_field
from .workspace_process import FileLock


def applicable_conditions(profile, conditions, spec):
    from .managed_answer_library import country_key
    country = get_value(profile, 'work_authorization.country') or get_value(profile, 'identity.address.country')
    country = country_key(country or '')
    if spec.get('country') and country != spec['country']:return False
    return all(key == 'country' and country_key(value) == country for key, value in conditions.items())


def export_content(raw, profile):
    """Replace supported factual sections, preserving private non-factual data."""
    result = copy.deepcopy(raw)
    for key in LEGACY_ALLOWED_SECTIONS:
        if key == 'resume':
            legacy_text = (raw.get('resume') or {}).get('text')
            resume = copy.deepcopy(profile.get('resume') or {})
            if legacy_text is not None:resume['text'] = legacy_text
            if resume:result[key] = resume
            else:result.pop(key, None)
        elif key in profile:result[key] = copy.deepcopy(profile[key])
        else:result.pop(key, None)
    return result


class ProfileServices:
    def _profile_suggestions(self, db, candidate):
        profile = json.loads(candidate['profile_json'])
        suggestions = []

        def offer(question, answer, conditions, **source):
            path = field_for_question(question)
            if not path or not applicable_conditions(profile, conditions, FIELDS[path]):return
            value = source_value(path, answer)
            if value is None:return
            current = value_for_field(profile, path)
            suggestions.append(dict(field=path, label=FIELDS[path]['label'], value=value, current=current,
                                    question=question, conditions=conditions, scope='global', **source))

        entries = self._library_entries(db, candidate['id'])
        for entry in entries:
            if entry['state'] != 'active' or entry['scope'] != 'global':continue
            # Only the primary question defines the source fact. An overbroad
            # alternate wording must not widen an employer-specific answer.
            offer(entry['question'], entry['answer'], entry['conditions'], entry_id=entry['id'],
                  revision=entry['revision'], source_type='answer_library', saved_at=entry['updated_at'])
        rows = db.execute('''SELECT a.*,q.question,q.identity_id FROM application_question_answers a
            JOIN application_questions q ON q.id=a.question_id WHERE q.identity_id=? AND q.state!='superseded'
            AND a.source IN ('user_dashboard','user_reply') AND a.revision=(SELECT MAX(a2.revision)
            FROM application_question_answers a2 WHERE a2.question_id=a.question_id
            AND a2.source IN ('user_dashboard','user_reply'))''', (candidate['id'],)).fetchall()
        for row in rows:
            source = db.execute('''SELECT payload_json,result_json,entry_id FROM answer_learning_sources
                WHERE kind='response' AND source_id=? AND source_revision=?''', (row['question_id'], row['revision'])).fetchone()
            payload = json.loads(source['payload_json']) if source else {}
            result = json.loads(source['result_json'] or '{}') if source else {}
            if payload.get('scope', 'global') != 'global' or result.get('scope', 'global') != 'global':continue
            parent = next((e for e in entries if source and e['id'] == source['entry_id']), None)
            if parent and (parent['scope'] != 'global' or parent['state'] != 'active'):continue
            offer(row['question'], json.loads(row['answer_json']), payload.get('conditions', {}),
                  question_id=row['question_id'], revision=row['revision'], source_type='application_question_answer',
                  saved_at=row['created_at'])
        for item in suggestions:
            alternatives = {dumps(s['value']) for s in suggestions if s['field'] == item['field']}
            item['status'] = ('conflict' if len(alternatives) > 1 else 'current' if item['value'] == item['current']
                              else 'new' if item['current'] in (None, '') else 'different')
        # Keep the source revisions available; the UI groups equivalent proposals.
        return suggestions

    def profile_editor(self, *, identity_id):
        display = self.candidate(identity_id)
        with self.read() as db:
            candidate = dict(self._get(db, 'candidates', identity_id))
            suggestions = self._profile_suggestions(db, candidate)
            display.update(candidate, profile=json.loads(candidate['profile_json']))
        return dict(candidate=display, sections=schema(), suggestions=suggestions,
                    file_sync=self.profile_file_status(identity_id=identity_id))

    def save_profile(self, *, identity_id, profile, expected_profile_hash, promotions=None):
        if not isinstance(profile, dict):raise ProtocolError('invalid_profile_data')
        reject_secrets(profile)
        incoming = copy.deepcopy(profile)
        promotions = promotions or []
        if not isinstance(promotions, list):raise ProtocolError('invalid_profile_sources')
        with self.tx() as db:
            candidate = dict(self._get(db, 'candidates', identity_id))
            if candidate['profile_hash'] != expected_profile_hash:raise ProtocolError('profile_revision_conflict')
            current = json.loads(candidate['profile_json'])
            email = get_value(incoming, 'identity.email')
            if email and email.casefold() != candidate['email'].casefold():raise ProtocolError('identity_immutable')
            provenance = copy.deepcopy(current.get('profile_answer_sources'))
            if not isinstance(provenance, dict):provenance = {}
            for path, spec in FIELDS.items():
                edits = []
                for name in [path, *spec['mirrors']]:
                    value, previous = get_value(incoming, name), get_value(current, name)
                    if value is None and previous is None or spec['kind'] == 'text' and value in (None, '') and previous in (None, ''):continue
                    if dumps(value) != dumps(previous):edits.append(value)
                if edits:
                    if any(not valid_value(spec, value) for value in edits) or len({dumps(value) for value in edits}) != 1:
                        raise ProtocolError('invalid_profile_answer', path)
                    for name in [path, *spec['mirrors']]:set_value(incoming, name, edits[0])
                    provenance[path] = dict(source_type='profile_edit', saved_at=self.now())
            available = self._profile_suggestions(db, candidate) if promotions else []
            seen = set()
            for selection in promotions:
                if not isinstance(selection, dict):raise ProtocolError('invalid_profile_sources')
                path = selection.get('field')
                if path in seen:raise ProtocolError('invalid_profile_sources')
                seen.add(path)
                matches = [s for s in available if s['field'] == path and s['revision'] == selection.get('revision')
                           and (s.get('entry_id') == selection.get('entry_id') if selection.get('entry_id')
                                else s.get('question_id') == selection.get('question_id') and bool(selection.get('question_id')))]
                if len(matches) != 1 or get_value(incoming, path) != matches[0]['value']:
                    raise ProtocolError('profile_source_changed')
                source = matches[0]
                provenance[path] = {k: source[k] for k in ('source_type', 'entry_id', 'question_id', 'revision', 'scope', 'conditions', 'question') if k in source}
                provenance[path]['saved_at'] = self.now()
            if provenance:incoming['profile_answer_sources'] = provenance
            else:incoming.pop('profile_answer_sources', None)
            encoded = dumps(incoming)
            db.execute('UPDATE candidates SET profile_json=?,profile_hash=? WHERE id=?',
                       (encoded, hashlib.sha256(encoded.encode()).hexdigest(), identity_id))
            self._reconcile_answers(db, identity_id)
        return dict(candidate=self.candidate(identity_id), file_sync=self.sync_profile_file(identity_id=identity_id))

    def _profile_export_path(self, identity_id):
        config = getattr(self, 'executor_config', None) or {}
        if identity_id != config.get('identity_id') or not config.get('profile_export_path'):return None
        path = Path(config['profile_export_path'])
        if not path.is_absolute():raise ProtocolError('profile_export_absolute_path_required')
        return path.resolve()

    @staticmethod
    def _read_export(path, candidate):
        raw = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if not isinstance(raw, dict):raise ProtocolError('profile_export_invalid_json')
        email = (raw.get('identity') or {}).get('email')
        owner = (raw.get('_jobbot_profile_export') or {}).get('identity_id')
        if email and email.casefold() != candidate['email'].casefold() or owner and owner != candidate['id']:
            raise ProtocolError('profile_export_identity_mismatch')
        return raw

    def profile_file_status(self, *, identity_id):
        try:
            path = self._profile_export_path(identity_id)
            if path is None:return {'status': 'not_configured'}
            if not path.parent.is_dir():raise OSError('profile_export_directory_missing')
            candidate = self.candidate(identity_id)
            raw = self._read_export(path, candidate)
            stamp = raw.get('_jobbot_profile_export') or {}
            projected = export_content(raw, candidate['profile'])
            unchanged = all(dumps(raw.get(k)) == dumps(projected.get(k)) for k in LEGACY_ALLOWED_SECTIONS)
            return {'status': 'synced' if unchanged and stamp.get('profile_hash') == candidate['profile_hash'] else 'out_of_date',
                    'saved_at': stamp.get('saved_at')}
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            return {'status': 'error', 'code': exc.code if isinstance(exc, ProtocolError) else 'profile_export_unavailable'}

    def sync_profile_file(self, *, identity_id):
        try:
            path = self._profile_export_path(identity_id)
            if path is None:return {'status': 'not_configured'}
            if not path.parent.is_dir():raise OSError('profile_export_directory_missing')
            # Share the existing lock with password edits when the factual export
            # and credential source point to the same private file.
            with FileLock(str(path) + '.password-overrides.lock'):
                candidate = self.candidate(identity_id)
                raw = self._read_export(path, candidate)
                raw = export_content(raw, candidate['profile'])
                raw['_jobbot_profile_export'] = dict(identity_id=identity_id, profile_hash=candidate['profile_hash'], saved_at=self.now())
                fd, temporary = tempfile.mkstemp(prefix='.jobbot-profile-', dir=path.parent)
                try:
                    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                        json.dump(raw, stream, ensure_ascii=False, indent=2)
                        stream.write('\n');stream.flush();os.fsync(stream.fileno())
                    os.replace(temporary, path)
                finally:
                    if os.path.exists(temporary):os.unlink(temporary)
            return {'status': 'synced', 'saved_at': raw['_jobbot_profile_export']['saved_at']}
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            return {'status': 'error', 'code': exc.code if isinstance(exc, ProtocolError) else 'profile_export_write_failed'}
