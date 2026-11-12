"""Current operator-owned answer knowledge; historical responses remain snapshots.

AI extracts general knowledge and equivalent wording in a separate background worker.
Application reuse checks current scope, conditions and actual form options; field IDs,
option values and document URLs never become reusable knowledge.
"""
import hashlib
import json
import re
import unicodedata

from .managed_shared import ProtocolError, dumps, uid
from .managed_redaction import reject_secrets
from .answer_learning import AnswerLearningServices


def normalized(text):
    text = unicodedata.normalize('NFKC', str(text)).casefold()
    return ' '.join(re.findall(r'\w+|[$€£¥%+<>=]', text))


def company_key(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value)).casefold().split())


def country_key(value):
    value = normalized(value)
    return {'united states':'us', 'united states of america':'us', 'u s':'us', 'usa':'us',
            'u s a':'us', 'united kingdom':'uk', 'great britain':'uk'}.get(value, value)


def question_identity(question):
    """Only harmless typography and narrowly recognized wording are generalized."""
    text = normalized(question)
    # Never discard negation, qualifiers or a compound employer question.
    if re.search(r'\b(not|without|never|except|unless)\b', text):return 'exact:' + text
    country = 'us' if re.search(r'\b(united states(?: of america)?|usa|u s(?: a)?)\b', text) else ''
    sponsorship = re.fullmatch(
        r'(?:do you|will you|would you|are you going to) (?:currently |now )?(?:require|need) '
        r'(?:visa |employment |work visa )?sponsorship(?: (?:now|currently|in the future|in future|now or in the future|now or in future))?\??', text)
    if sponsorship:
        when = 'now_or_future' if 'now or' in text else 'future' if 'future' in text else 'current'
        return 'intent:sponsorship:' + when
    if country and re.fullmatch(
        r'are you (?:currently )?(?:legally )?(?:authorized|authorised|eligible) to work in (?:the )?'
        r'(?:united states(?: of america)?|usa|u s(?: a)?)', text):
        return 'intent:authorization:us'
    if text in ('when can you start', 'when could you start', 'when are you available to start',
                'when would you be available to start'):
        return 'intent:start_availability'
    from .profile_questions import field_for_question
    path = field_for_question(question)
    if path:return 'profile:' + path
    return 'exact:' + text


def recommended_scope(question):
    return 'company' if re.search(r'\b(this company|our company|our organization|for us|with us|here)\b', normalized(question)) else 'global'


def applicability(question, job):
    text = question.get('question', '')
    try:metadata = json.loads(job.get('metadata_json') or '{}')
    except (TypeError, ValueError):metadata = {}
    result = {}
    for pattern, value in ((r'\bUnited States\b|\bU\.S\.?\b|\bUSA\b', 'us'),
                           (r'\bUnited Kingdom\b|\bUK\b', 'uk'), (r'\bCanada\b', 'canada')):
        if re.search(pattern, text, re.I):result['country'] = value;break
    if re.search(r'\bUS\b',text):result['country']='us'
    if 'country' not in result and isinstance(metadata.get('country'), str):
        result['country'] = country_key(metadata['country'])
    currencies = re.findall(r'\b(USD|CAD|AUD|EUR|GBP)\b', text.upper())
    if len(set(currencies)) == 1:result['currency'] = currencies[0]
    periods = [('hour', r'\b(hourly|per hour)\b'), ('year', r'\b(annual|annually|yearly|per year)\b'),
               ('month', r'\b(monthly|per month)\b')]
    found = [value for value, pattern in periods if re.search(pattern, text, re.I)]
    if len(found) == 1:result['period'] = found[0]
    return result


def matches(entry, question, job):
    # A literal company slot expresses the operator's cross-company default.
    # Bind it only to the actual posting company, never to an arbitrary substring.
    company = job.get('company') or ''
    wordings = [entry['question'], *entry.get('aliases', [])]
    identities = {question_identity(q.replace('{company}', company)) for q in wordings
                  if '{company}' not in q or company}
    if question_identity(question['question']) not in identities:return False
    if entry['scope'] == 'job' and entry['scope_key'] != job.get('id'):return False
    if entry['scope'] == 'company' and entry['scope_key'] != company_key(job.get('company') or ''):return False
    context = applicability(question, job)
    return all(context.get(key) == value for key, value in entry.get('conditions', {}).items())


def option_answer(question, answer):
    """Map an approved meaning to this form's current option labels and values."""
    from .application_answers import match_answer_to_option
    # Older synthesized answers often retain an explicit Yes/No followed by
    # explanation. Keep that text for text fields and use its stated polarity
    # for Boolean controls after trying the complete label first.
    prefix = re.match(r'^\s*(yes|no)\s*(?:[,.:;!]|$)', answer, re.I) if isinstance(answer,str) else None
    polarity = prefix[1].capitalize() if prefix else answer
    if question['kind'] == 'check':
        if type(answer) is bool:return answer
        return {'yes':True, 'no':False}.get(str(polarity).casefold())
    if question['kind'] in ('select', 'radio'):
        choices = question.get('options', [])
        index = match_answer_to_option(answer, [o['label'] for o in choices])
        if index is None and prefix:index = match_answer_to_option(polarity, [o['label'] for o in choices])
        return {k:choices[index][k] for k in ('value', 'label')} if index is not None else None
    return ('Yes' if answer else 'No') if type(answer) is bool else str(answer)


def resolve_library(question, job, entries):
    applicable = [e for e in entries if matches(e, question, job)]
    active = [e for e in applicable if e['state'] == 'active']
    if not active:return {'matched':bool(applicable), 'retired':bool(applicable), 'answer':None}
    priority = lambda e:({'global':0, 'company':1, 'job':2}[e['scope']], len(e.get('conditions', {})))
    best = max(priority(e) for e in active)
    selected = [e for e in active if priority(e) == best]
    if len({dumps(e['answer']) for e in selected}) != 1:
        return {'matched':True, 'answer':None, 'reason':'conflicting_library_answers'}
    entry = sorted(selected, key=lambda e:e['id'])[0]
    return {'matched':True, 'answer':option_answer(question, entry['answer']),
            'entry_id':entry['id'], 'revision':entry['revision'],
            'basis':'answer_library:' + entry['id'] + ':' + str(entry['revision'])}


def resolve_with_profile(question, job, entries, profile):
    """Scoped exceptions, structured profile facts, then general learned answers.

    Explicit human responses are handled by callers before this function.
    A missing answer still returns to the executor's ordinary recovery path.
    """
    from .profile_questions import field_for_question, structured_answer
    scoped = [e for e in entries if e['scope'] in ('company', 'job') and e['state'] == 'active']
    resolved = resolve_library(question, job, scoped)
    if resolved.get('matched'):return resolved
    path = field_for_question(question['question'])
    value = structured_answer(question['question'], profile)
    if value is not None or path and path in (profile.get('profile_answer_sources') or {}):
        return {'matched':True, 'answer':option_answer(question, value) if value is not None else None,
                'source':'approved_profile', 'basis':'profile:' + (path or 'standard_answers')}
    resolved = resolve_library(question, job, entries)
    if resolved.get('matched') and not resolved.get('retired'):return resolved
    from .application_answers import approved_answer
    value = approved_answer(question['question'], profile)
    if value is not None:
        return {'matched':True, 'answer':option_answer(question, value), 'source':'approved_profile', 'basis':'approved_profile'}
    return resolved


class AnswerLibraryServices(AnswerLearningServices):
    @staticmethod
    def _has_library_schema(db):
        return bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='answer_library_entries'").fetchone())

    @staticmethod
    def _library_entry(row):
        value = dict(row)
        value.setdefault('origin', 'legacy')
        for key in ('answer', 'aliases', 'conditions'):
            value[key] = json.loads(value.pop(key + '_json'))
        return value

    def _library_entries(self, db, identity_id):
        if not self._has_library_schema(db):return []
        return [self._library_entry(r) for r in db.execute(
            'SELECT * FROM answer_library_entries WHERE identity_id=? ORDER BY updated_at DESC,id', (identity_id,))]

    def _record_question_answer(self, db, question, answer, source, *, entry_id=None, library_revision=None, evidence=''):
        """Append a response version, including invalidation, without editing history."""
        if (question['answer'] == answer and question.get('answer_source') == source
                and question.get('library_entry_id') == entry_id and question.get('library_revision') == library_revision):return False
        revision = question['revision'] + 1;now = self.now()
        db.execute('''INSERT INTO application_question_answers
            (question_id,revision,answer_json,source,evidence,created_at,library_entry_id,library_revision)
            VALUES (?,?,?,?,?,?,?,?)''', (question['id'], revision, dumps(answer), source, evidence, now, entry_id, library_revision))
        db.execute('''UPDATE application_questions SET state=?,answer_json=?,answer_source=?,answered_at=?,revision=?,
            library_entry_id=?,library_revision=? WHERE id=?''',
            ('answered' if answer is not None else 'pending', dumps(answer) if answer is not None else None,
             source, now if answer is not None else None, revision, entry_id, library_revision, question['id']))
        return True

    def _reconcile_answers(self, db, identity_id=None):
        if not self._has_library_schema(db):return {'resolved':0, 'updated':0, 'invalidated':0}
        rows = db.execute('''SELECT q.* FROM application_questions q JOIN jobs j ON j.id=q.job_id
            WHERE q.state!='superseded' AND (q.state='pending' OR q.answer_source IN ('answer_library','approved_profile','knowledge_changed'))
            AND j.disposition!='canceled' AND j.status NOT IN ('applied','already_applied')
            AND NOT EXISTS (SELECT 1 FROM job_archives a WHERE a.job_id=j.id)'''
            + (' AND q.identity_id=?' if identity_id else ''), (identity_id,) if identity_id else ()).fetchall()
        entries = {};profiles = {};jobs = {};result = {'resolved':0, 'updated':0, 'invalidated':0}
        for row in rows:
            question = self._question(row);identity = question['identity_id'];job_id = question['job_id']
            if identity not in entries:
                entries[identity] = self._library_entries(db, identity)
                profiles[identity] = json.loads(self._get(db, 'candidates', identity)['profile_json'])
            if job_id not in jobs:jobs[job_id] = dict(self._get(db, 'jobs', job_id))
            resolved = resolve_with_profile(question, jobs[job_id], entries[identity], profiles[identity]);answer = resolved['answer']
            source = resolved.get('source', 'answer_library');entry_id = resolved.get('entry_id');version = resolved.get('revision')
            if answer is None and question['answer'] is None:continue
            changed = self._record_question_answer(db, question, answer,
                source if answer is not None else 'knowledge_changed', entry_id=entry_id, library_revision=version,
                evidence='Current editable answer knowledge')
            if changed:result['invalidated' if answer is None else 'resolved' if question['answer'] is None else 'updated'] += 1
        return result

    def reconcile_answers(self, identity_id=None):
        with self.tx() as db:return self._reconcile_answers(db, identity_id)

    def save_library_answer(self, *, identity_id, question, answer, aliases=None, scope='global', scope_key='',
                            conditions=None, entry_id=None, expected_revision=0):
        return self._save_library_answer(identity_id=identity_id, question=question, answer=answer,
            aliases=aliases, scope=scope, scope_key=scope_key, conditions=conditions,
            entry_id=entry_id, expected_revision=expected_revision)

    def _save_library_answer(self, *, identity_id, question, answer, aliases=None, scope='global', scope_key='',
                            conditions=None, entry_id=None, expected_revision=0, origin=None, learning_source=None):
        from .managed_questions import PRIVATE
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 4000 or PRIVATE.search(question):
            raise ProtocolError('invalid_library_question')
        if not (type(answer) is bool or isinstance(answer, str) and 1 <= len(answer.strip()) <= 4000):
            raise ProtocolError('answer_required')
        aliases = aliases or [];conditions = conditions or {}
        if not isinstance(aliases, list) or len(aliases)>100 or any(
                not isinstance(a, str) or not 1 <= len(a.strip()) <= 4000 or PRIVATE.search(a) for a in aliases):
            raise ProtocolError('invalid_question_aliases')
        if scope not in ('global','company','job') or not isinstance(scope_key, str):raise ProtocolError('invalid_answer_scope')
        if scope == 'global':scope_key = ''
        if scope == 'company':scope_key = company_key(scope_key)
        if scope != 'global' and not scope_key:raise ProtocolError('answer_scope_required')
        if not isinstance(conditions, dict) or set(conditions)-{'country','currency','period'} or any(
                not isinstance(v, str) or not 1 <= len(v.strip()) <= 100 for v in conditions.values()):
            raise ProtocolError('invalid_answer_conditions')
        conditions = {k:country_key(v) if k=='country' else v.upper() if k=='currency' else normalized(v) for k,v in conditions.items()}
        if type(expected_revision) is not int:raise ProtocolError('answer_revision_conflict')
        question = question.strip();answer = answer.strip() if isinstance(answer, str) else answer
        aliases = list(dict.fromkeys(a.strip() for a in aliases))
        reject_secrets(dict(question=question, answer=answer, aliases=aliases, scope_key=scope_key, conditions=conditions))
        with self.tx() as db:
            self._get(db, 'candidates', identity_id)
            if scope == 'job':self._get(db, 'jobs', scope_key)
            old = self._library_entry(self._get(db, 'answer_library_entries', entry_id)) if entry_id else None
            if not old:
                duplicate=next((e for e in self._library_entries(db,identity_id)
                    if e['state']=='active' and e['scope']==scope and e['scope_key']==scope_key and e['conditions']==conditions
                    and question_identity(e['question'])==question_identity(question)),None)
                if duplicate:
                    if duplicate['answer']==answer and duplicate['aliases']==aliases:
                        if learning_source:
                            if not self._learning_source_current(db,learning_source):raise ProtocolError('learning_source_changed')
                            db.execute("UPDATE answer_learning_sources SET state='learned',entry_id=?,updated_at=? WHERE id=?",(duplicate['id'],self.now(),learning_source['id']))
                        return duplicate
                    raise ProtocolError('library_answer_exists')
            if old and old['identity_id'] != identity_id:raise ProtocolError('asset_identity_mismatch')
            if expected_revision != (old['revision'] if old else 0):raise ProtocolError('answer_revision_conflict')
            if learning_source and not self._learning_source_current(db, learning_source):raise ProtocolError('learning_source_changed')
            origin = origin or ('ai_edited' if old and old.get('origin') in ('ai','ai_edited') else 'manual')
            identifier = entry_id or uid();revision = expected_revision + 1;now = self.now()
            entry = dict(id=identifier, identity_id=identity_id, question=question, answer=answer, aliases=aliases,
                         scope=scope, scope_key=scope_key, conditions=conditions, state='active', revision=revision,
                         created_at=old['created_at'] if old else now, updated_at=now, origin=origin)
            db.execute('''INSERT INTO answer_library_entries
                (id,identity_id,question,answer_json,aliases_json,scope,scope_key,conditions_json,state,revision,created_at,updated_at,origin)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET question=excluded.question,answer_json=excluded.answer_json,
                aliases_json=excluded.aliases_json,scope=excluded.scope,scope_key=excluded.scope_key,conditions_json=excluded.conditions_json,
                state=excluded.state,revision=excluded.revision,updated_at=excluded.updated_at,origin=excluded.origin''',
                (identifier, identity_id, question, dumps(answer), dumps(aliases), scope, scope_key, dumps(conditions), 'active', revision, entry['created_at'], now, origin))
            db.execute('INSERT INTO answer_library_versions VALUES (?,?,?,?)', (identifier, revision, dumps(entry), now))
            if learning_source:
                db.execute("UPDATE answer_learning_sources SET state='learned',entry_id=?,updated_at=? WHERE id=?", (identifier,now,learning_source['id']))
                if learning_source['kind']=='legacy':
                    self._preserve_legacy_replies(db,learning_source,entry)
                if learning_source['kind']=='legacy' and learning_source['source_id']!=identifier:
                    earlier=self._library_entry(self._get(db,'answer_library_entries',learning_source['source_id']))
                    earlier.update(state='retired',revision=earlier['revision']+1,updated_at=now)
                    db.execute("UPDATE answer_library_entries SET state='retired',revision=?,updated_at=? WHERE id=?",(earlier['revision'],now,earlier['id']))
                    db.execute('INSERT INTO answer_library_versions VALUES (?,?,?,?)',(earlier['id'],earlier['revision'],dumps(earlier),now))
            self._reconcile_answers(db, identity_id)
            return entry

    def set_library_answer_state(self, *, entry_id, state, expected_revision):
        if state not in ('active','retired'):raise ProtocolError('invalid_answer_state')
        with self.tx() as db:
            entry = self._library_entry(self._get(db, 'answer_library_entries', entry_id))
            if type(expected_revision) is not int or expected_revision != entry['revision']:raise ProtocolError('answer_revision_conflict')
            entry.update(state=state, revision=expected_revision+1, updated_at=self.now())
            if state=='active' and entry.get('origin')=='legacy':entry['origin']='manual'
            db.execute('UPDATE answer_library_entries SET state=?,revision=?,updated_at=?,origin=? WHERE id=?',
                       (state, entry['revision'], entry['updated_at'], entry['origin'], entry_id))
            db.execute('INSERT INTO answer_library_versions VALUES (?,?,?,?)', (entry_id, entry['revision'], dumps(entry), entry['updated_at']))
            self._reconcile_answers(db, entry['identity_id'])
            return entry

    def answer_library(self, identity_id=None, include_history=True):
        with self.read() as db:
            if not self._has_library_schema(db):return {'entries':[], 'suggestions':[]}
            identities = [identity_id] if identity_id else [r[0] for r in db.execute('SELECT id FROM candidates')]
            entries = []
            for identity in identities:entries.extend(self._library_entries(db, identity))
            for entry in entries if include_history else []:
                entry['history'] = [json.loads(r[0]) for r in db.execute(
                    'SELECT snapshot_json FROM answer_library_versions WHERE entry_id=? ORDER BY revision DESC', (entry['id'],))]
            if not include_history:return {'entries':entries, 'suggestions':[]}
            for entry in entries:
                if entry['scope']=='job':
                    application=db.execute('SELECT id,company,title,url FROM jobs WHERE id=?',(entry['scope_key'],)).fetchone()
                    if application:entry['application']=dict(application)
            learning = self._learning_view(db, identity_id)
            for entry in entries if self._has_learning_schema(db) else []:
                entry['sources'] = [json.loads(r[0]) for r in db.execute(
                    "SELECT payload_json FROM answer_learning_sources WHERE entry_id=? AND state IN ('learned','context_only','conflict') ORDER BY updated_at DESC", (entry['id'],))]
            impact = self._answer_usage(db, entries)
            return {'entries':entries, 'suggestions':learning.pop('activity'), 'learning':learning, 'impact':impact}

    def _answer_usage(self, db, entries):
        """Project existing response and private form evidence, never infer submission."""
        from pathlib import Path
        indexed = {e['id']:e for e in entries}
        counts = {e['id']:set() for e in entries}
        applications = {e['id']:set() for e in entries}
        used_applications = {}; matched_questions = set()
        for entry in entries:
            entry['usage'] = dict(resolved_questions=0, recorded_form_uses=0, applications=0, last_used_at=None, recent=[])

        def retain(entry, item):
            usage = entry['usage']; applications[entry['id']].add(item['job_id'])
            previous = used_applications.get(item['job_id'])
            if not previous or (item['at'] or '') > (previous['at'] or ''):
                used_applications[item['job_id']] = {key:item.get(key) for key in ('job_id','company','title','url','at')}
            usage['recent'].append(item)
            usage['recent'].sort(key=lambda r:r['at'] or '', reverse=True)
            del usage['recent'][20:]
            usage['last_used_at'] = max(usage['last_used_at'] or '', item['at'] or '') or None

        for row in db.execute('''SELECT a.library_entry_id,a.library_revision,a.created_at AS at,
                q.id AS question_id,q.question,q.job_id,j.company,j.title,j.url
                FROM application_question_answers a JOIN application_questions q ON q.id=a.question_id
                JOIN jobs j ON j.id=q.job_id WHERE a.source='answer_library'
                AND a.answer_json IS NOT NULL AND a.answer_json!='null' ORDER BY a.created_at DESC'''):
            item = dict(row); entry = indexed.get(item.pop('library_entry_id'))
            if not entry or item['question_id'] in counts[entry['id']]:continue
            counts[entry['id']].add(item['question_id']);matched_questions.add(item['question_id']);retain(entry, dict(item, kind='resolved'))
        spool = (getattr(self, 'executor_config', {}) or {}).get('spool_dir')
        cache = getattr(self, '_answer_usage_cache', {})
        current_cache = {}
        if spool:
            identities = {e['identity_id'] for e in entries}
            for row in db.execute('''SELECT a.id,a.identity_id,a.job_id,j.company,j.title,j.url
                    FROM application_attempts a JOIN jobs j ON j.id=a.job_id'''):
                attempt = dict(row)
                if attempt['identity_id'] not in identities:continue
                path = Path(spool)/'answers'/f"attempt-{attempt['id']}.json"
                try:
                    stat = path.stat();key = (str(path), stat.st_mtime_ns, stat.st_size)
                    history = cache.get(key)
                    if history is None:history = json.loads(path.read_text(encoding='utf-8'))
                    if not isinstance(history,dict):continue
                    current_cache[key] = history
                    if (history.get('attempt_id')!=attempt['id'] or history.get('identity_id')!=attempt['identity_id']
                            or history.get('job_id')!=attempt['job_id']):continue
                    seen = set()
                    for record in reversed(history.get('answers', [])):
                        if not isinstance(record,dict):continue
                        match = re.fullmatch(r'answer_library:([^:]+):(\d+)', str(record.get('answer_basis') or ''))
                        if not match:continue
                        entry = indexed.get(match[1])
                        if not entry or entry['identity_id']!=attempt['identity_id']:continue
                        identity = (match[1], match[2], record.get('page'), record.get('field'), record.get('question'))
                        if identity in seen:continue
                        seen.add(identity);entry['usage']['recorded_form_uses'] += 1
                        retain(entry, dict(kind='form', job_id=attempt['job_id'], company=attempt['company'],
                            title=attempt['title'], url=attempt['url'], attempt_id=attempt['id'],
                            question=record.get('question'), library_revision=int(match[2]),
                            at=record.get('observed_at'), source=record.get('source')))
                except (OSError,ValueError,TypeError):continue
        self._answer_usage_cache = current_cache
        for entry in entries:
            entry['usage']['resolved_questions'] = len(counts[entry['id']])
            entry['usage']['applications'] = len(applications[entry['id']])
        return dict(applications=len(used_applications),resolved_questions=len(matched_questions),
                    recorded_form_uses=sum(e['usage']['recorded_form_uses'] for e in entries),
                    recent_applications=sorted(used_applications.values(),key=lambda item:item['at'] or '',reverse=True)[:20])

    @staticmethod
    def _answer_clusters(groups):
        clusters = {}
        for group in groups:
            for question in group['questions']:
                if question['state'] != 'pending':continue
                scope = recommended_scope(question['question'])
                key = (group['identity_id'],question_identity(question['question']),
                       company_key(group['company'] or '') if scope=='company' else '')
                # Unknown choices retain their meaning; equivalent yes/no values can vary.
                labels = tuple(sorted(normalized(o['label']) for o in question['options']))
                key = (*key, question['kind'], labels)
                identifier = hashlib.sha256(dumps(key).encode()).hexdigest()
                item = clusters.setdefault(key, dict(id=identifier, identity_id=group['identity_id'], email=group['email'],
                    question=question['question'], kind=question['kind'], options=question['options'], aliases=[],
                    scope=scope, scope_key=key[2], requests=[], request_count=0))
                if question['question']!=item['question'] and question['question'] not in item['aliases']:item['aliases'].append(question['question'])
                item['requests'].append(dict(question_id=question['id'], revision=question['revision'], job_id=group['job_id'],
                    company=group['company'], title=group['title'], url=group['url'], question=question['question'], options=question['options']))
                item['request_count'] += 1
        return list(clusters.values())
