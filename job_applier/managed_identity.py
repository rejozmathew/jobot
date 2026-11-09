"""Verified job identity aliases without deleting or rewriting historical jobs."""
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import hashlib
import re
from .managed_shared import ProtocolError, dumps


def canonical_url(url):
    p = urlsplit(str(url).strip())
    if p.scheme not in ('https','http') or not p.hostname or p.username or p.password:
        raise ProtocolError('invalid_job_url')
    # Auth0's reset-request screen contains no reset token. It remains reachable
    # only through the ordinary observed-route proof; signed reset links retain
    # their existing treatment and never become public posting identities.
    # The optional segment is the connection name (including custom database
    # connections), not a password-reset token. Additional path segments and
    # secret-bearing query parameters still use the existing sensitive checks.
    reset_request=bool(re.fullmatch(r'/u/reset-password/request(?:/[A-Za-z0-9_-]+)?/?',p.path))
    if not reset_request and any(s in p.path.lower() for s in ('reset-password','password-reset','verify-email','oauth/','signin/callback')):
        raise ProtocolError('sensitive_url')
    query = parse_qsl(p.query, keep_blank_values=True)
    if any(k.lower() in ('access_token','refresh_token','otp','password','reset_token','authorization_code') for k,v in query):
        raise ProtocolError('sensitive_url')
    tracking={'gh_src','utm_source','utm_medium','utm_campaign','utm_term','utm_content','rx_campaign','rx_source','rx_medium','rx_ts'}
    # token, rx_job, and unknown query keys can identify a requisition.
    query=sorted((k,v) for k,v in query if k.lower() not in tracking)
    host=p.netloc.lower()
    if host=='boards.greenhouse.io': host='job-boards.greenhouse.io'
    return urlunsplit((p.scheme.lower(),host,p.path.rstrip('/'),urlencode(query),''))


def job_key(url, namespace=None, requisition_id=None):
    data=[namespace,str(requisition_id)] if namespace and requisition_id else [canonical_url(url)]
    return hashlib.sha256(dumps(data).encode()).hexdigest()


def ats_posting_identity(url, *, namespace=None, source_id=None):
    """Intake identity, separate from browser scope and employer requisition labels.

    Hosted Greenhouse URLs supply the board. Custom-domain URLs need both an
    explicit gh_jid and a retained/verified namespace or corroborating source
    reference. Company names, titles and bare numbers never identify a board.
    """
    try:
        p=urlsplit(canonical_url(url))
        for identify in (linkedin_identity, workday_identity, icims_identity):
            identity=identify(url)
            if identity:return identity
        board=None;posting=None
        if p.hostname in ('job-boards.greenhouse.io','boards-api.greenhouse.io'):
            prefix=r'/v1/boards' if p.hostname=='boards-api.greenhouse.io' else ''
            match=re.fullmatch(prefix+r'/([A-Za-z0-9_-]+)/jobs/([0-9]{1,20})(?:/(?:apply|confirmation))?',p.path)
            if not match:return None
            board,posting=match.groups()
            if any(k=='gh_jid' for k,v in parse_qsl(p.query,keep_blank_values=True)) and query_requisition(url)!=posting:
                return None
        else:
            posting=query_requisition(url)
            if not posting:return None
            parts=p.path.strip('/').split('/')
            if parts[-1] in ('apply','confirmation') and len(parts)>1 and parts[-2].isdigit() and parts[-2]!=posting:
                return None
            reference=re.fullmatch(r'greenhouse:([A-Za-z0-9_-]+):([0-9]{1,20})',str(source_id or ''))
            supplied=str(namespace or '').removeprefix('greenhouse:')
            if reference:
                if reference[2]!=posting or supplied and supplied.casefold()!=reference[1].casefold():return None
                board=reference[1]
            elif re.fullmatch(r'[A-Za-z0-9_-]+',supplied):board=supplied
            if not board:return None
        opaque=tuple((k,v) for k,v in parse_qsl(p.query,keep_blank_values=True)
                     if k!='gh_jid' and not (p.hostname=='boards-api.greenhouse.io' and k=='content'))
        return ('greenhouse',board.casefold(),posting,opaque)
    except (ValueError,ProtocolError):return None


def ats_posting_key(url, *, namespace=None, source_id=None):
    identity=ats_posting_identity(url,namespace=namespace,source_id=source_id) or workday_identity(url, location_optional=True)
    return hashlib.sha256(dumps(['ats_posting',identity]).encode()).hexdigest() if identity else None


def observed_posting_key(url):
    """Explicit posting IDs only; a login or board URL cannot merge job records."""
    key=ats_posting_key(url)
    if key:return key
    try:
        p=urlsplit(canonical_url(url))
        if (p.hostname or '').endswith('.ultipro.com'):
            values=[v.casefold() for k,v in parse_qsl(p.query) if k.casefold()=='opportunityid']
            tenant=p.path.strip('/').split('/')[0].casefold()
            if tenant and values and len(set(values))==1 and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',values[0]):
                return hashlib.sha256(dumps(['ukg',p.hostname,tenant,values[0]]).encode()).hexdigest()
        identity=form_route_identity(url)
        if identity:return hashlib.sha256(dumps(['observed_posting',identity]).encode()).hexdigest()
    except (ValueError,ProtocolError):pass
    return None


def retain_observed_posting_aliases(db):
    """Backfill only explicit IDs in retained host-verified application routes."""
    import json
    for job in db.execute('SELECT id,url FROM jobs').fetchall():
        urls=[job['url']]
        for row in db.execute('SELECT metadata_json FROM application_sessions WHERE job_id=?',(job['id'],)):
            metadata=json.loads(row[0] or '{}')
            urls.extend(metadata.get(k) for k in ('application_identity_url','application_route_url') if metadata.get(k))
        for url in urls:
            key=observed_posting_key(url)
            if key:db.execute('INSERT OR IGNORE INTO job_identity_keys VALUES (?,?,?)',
                (key,job['id'],'observed_posting_identity'))


def application_start_url(url):
    """Provider-specific data endpoint -> public form; original intake stays intact."""
    p=urlsplit(url)
    identity=ats_posting_identity(url)
    if p.hostname=='boards-api.greenhouse.io' and identity and identity[0]=='greenhouse':
        return urlunsplit(('https','job-boards.greenhouse.io',
            '/'+identity[1]+'/jobs/'+identity[2],urlencode(identity[3]),''))
    return url


def explicit_job_conflict(left, right):
    """A different hostname alone is not contradictory observed redirect evidence."""
    for identify in (linkedin_identity,workday_identity,icims_identity,ats_posting_identity):
        a,b=identify(left),identify(right)
        if a and b and a[0]==b[0] and a!=b:return True
    a,b=form_route_identity(left),form_route_identity(right)
    return bool(a and b and a[:3]==b[:3] and a[3]!=b[3])


def retain_posting_aliases(db):
    """Add identities to old records; never merge/delete jobs or rewrite outcomes."""
    for row in db.execute('SELECT id,url,namespace,requisition_id FROM jobs').fetchall():
        references=[(row['url'],None)]
        references.extend((r['original_url'],r['source_id']) for r in db.execute(
            'SELECT original_url,source_id FROM job_sources WHERE job_id=?',(row['id'],)))
        for url,source_id in references:
            key=ats_posting_key(url,namespace=row['namespace'] if row['requisition_id'] else None,source_id=source_id)
            if key:db.execute('INSERT OR IGNORE INTO job_identity_keys VALUES (?,?,?)',
                (key,row['id'],'retained_ats_posting_identity'))


def query_requisition(url):
    """A consistent explicit Greenhouse query id, not a guessed path number."""
    values=[value for key,value in parse_qsl(urlsplit(url).query,keep_blank_values=True) if key=='gh_jid']
    if not values:return None
    if len(set(values))!=1 or not re.fullmatch(r'[0-9]{1,20}',values[0]):return None
    tail=urlsplit(url).path.rstrip('/').rsplit('/',1)[-1]
    if tail.isdigit() and tail!=values[0]:return None
    return values[0]


def greenhouse_query_identity(url):
    """Narrow employer posting/form aliases; unknown query keys remain meaningful."""
    try:
        p=urlsplit(canonical_url(url));requisition=query_requisition(url)
        if not requisition:return None
        parts=p.path.strip('/').split('/')
        if parts[-1] in ('apply','confirmation'):parts=parts[:-1]
        if not (parts in (['jobs'],['form']) or
                len(parts)>1 and parts[0]=='jobs' and parts[-1]==requisition):return None
        opaque=tuple((k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if k!='gh_jid')
        return p.scheme,p.netloc,requisition,opaque
    except (ValueError,ProtocolError):return None


def icims_identity(url):
    """iCIMS keeps the job id across posting, login and embedded form routes."""
    try:
        p=urlsplit(canonical_url(url));host=p.hostname or ''
        if host!='icims.com' and not host.endswith('.icims.com'):return None
        match=re.match(r'^/jobs/(\d+)(?:/|$)',p.path,re.I)
        if match:return ('icims',p.scheme,p.netloc,match[1])
    except (ValueError,ProtocolError):pass
    return None


def linkedin_identity(url):
    """Only an explicit job ID identifies a LinkedIn posting or selected search result."""
    try:
        p=urlsplit(canonical_url(url));host=p.hostname or ''
        if host!='linkedin.com' and not host.endswith('.linkedin.com'):return None
        match=re.fullmatch(r'/(?:comm/)?jobs/view/(?:[^/]*-)?(\d+)',p.path)
        values=[v for k,v in parse_qsl(p.query) if k=='currentJobId']
        if values and (len(set(values))!=1 or not values[0].isdigit()):return None
        if match:
            if values and values[0]!=match[1]:return None
            return ('linkedin',match[1])
        if values and re.match(r'^/jobs/(?:search|collections)(?:/|$)',p.path):return ('linkedin',values[0])
    except (ValueError,ProtocolError):pass
    return None


def same_job_url(left, right):
    """Compare known ATS identities; preserve other portals' opaque URL queries."""
    try:
        a, b = urlsplit(canonical_url(left)), urlsplit(canonical_url(right))
    except (ValueError, ProtocolError):
        return False
    gh_left,gh_right=ats_posting_identity(left),ats_posting_identity(right)
    if gh_left and gh_right and gh_left[0]==gh_right[0]=='greenhouse':return gh_left==gh_right
    li_left,li_right=linkedin_identity(left),linkedin_identity(right)
    if li_left or li_right:return bool(li_left and li_right and li_left==li_right)
    wd_left,wd_right=workday_identity(left),workday_identity(right)
    if wd_left or wd_right:return bool(wd_left and wd_right and wd_left==wd_right)
    icims_left,icims_right=icims_identity(left),icims_identity(right)
    if icims_left and icims_right:return icims_left==icims_right
    gh_left,gh_right=greenhouse_query_identity(left),greenhouse_query_identity(right)
    if gh_left and gh_right:return gh_left==gh_right
    if any(k=='gh_jid' for p in (a,b) for k,v in parse_qsl(p.query,keep_blank_values=True)):
        if not query_requisition(left) or not query_requisition(right):return False
    if (a.hostname or '').endswith('.myworkdayjobs.com'):
        a = a._replace(path=a.path.casefold())
        b = b._replace(path=b.path.casefold())
    return a == b


RELATED = """WITH RECURSIVE related(id) AS (
    SELECT ? UNION
    SELECT other.job_id FROM related r
    JOIN job_identity_keys own ON own.job_id=r.id
    JOIN job_identity_keys other ON other.identity_key=own.identity_key
) """


def linked_jobs(db, job_id):
    return [r[0] for r in db.execute(RELATED+'SELECT id FROM related',(job_id,))]


_LOCALE_RE = re.compile(r"^[a-zA-Z]{2}(?:-[a-zA-Z0-9]{2,4})?$")


def _workday_url(url):
    """Parse the portal and requisition, never the display title or location."""
    from urllib.parse import unquote
    try:
        p = urlsplit(canonical_url(url))
        if p.scheme != 'https' or not (p.hostname or '').endswith('.myworkdayjobs.com'):
            return None
        if any(x in p.path.lower() for x in ('%2f', '%2e', '%5c')) or '..' in p.path or '/.' in p.path:
            return None
        parts = [unquote(x).casefold() for x in p.path.strip('/').split('/') if x]
        if parts and _LOCALE_RE.fullmatch(parts[0]) and parts[1:2] not in (['job'],['details'],['login']):parts = parts[1:]
        return p, parts
    except (ValueError, ProtocolError):return None


def workday_identity(url, *, location_optional=False):
    parsed = _workday_url(url)
    if not parsed:return None
    p, parts = parsed
    if parts[1:] == ['login']:
        query = parse_qsl(p.query, keep_blank_values=True)
        if len(query) != 1 or query[0][0].casefold() != 'redirect':return None
        redirect = query[0][1]
        if not redirect.startswith('/') or redirect.startswith('//') or '\\' in redirect:return None
        destination = urlsplit(redirect)
        if destination.query or destination.fragment:return None
        route = urlunsplit((p.scheme, p.netloc, destination.path, '', ''))
        parsed_destination = _workday_url(route)
        if not parsed_destination or parsed_destination[1][1:2] not in (['job'], ['details']):return None
        return workday_identity(route)
    # A public posting can omit the location slug. Only intake identity opts
    # into that exact, query-free spelling with an explicit requisition suffix.
    locationless = (location_optional and len(parts) == 3 and parts[1] == 'job'
                    and not p.query and '//' not in p.path)
    index = 2 if locationless or parts[1:2] == ['details'] else 3 if parts[1:2] == ['job'] else None
    if index is None or len(parts) <= index or '_' not in parts[index]:return None
    slug = parts[index]
    # Preserve requisition suffixes such as R100_1; do not mistake its final 1
    # for the entire requisition. Other Workday IDs use the final slug separator.
    markers=list(re.finditer(r'_(?:jr|req|r)[-_]?\d',slug))
    if locationless and not markers:return None
    requisition = slug[markers[-1].start()+1:] if markers else slug.rsplit('_', 1)[-1]
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]*', requisition):return None
    for key, value in parse_qsl(p.query, keep_blank_values=True):
        if key.casefold() in ('jobid', 'requisitionid', 'reqid') and value.casefold() != requisition:
            return None
    return ('workday', p.netloc, parts[0], requisition)


def job_identity(url):
    """One comparison identity; stored URL hashes and historical rows stay intact."""
    identity = linkedin_identity(url)
    if identity:return identity
    identity = workday_identity(url)
    if identity:return identity
    identity = icims_identity(url)
    if identity:return identity
    gh = greenhouse_query_identity(url)
    if gh:return ('requisition_query', gh)
    return (canonical_url(url),)


def job_requisition(job):
    """Confirmation consumes the same complete requisition as job ownership."""
    identity=linkedin_identity(job['url']) or workday_identity(job['url'])
    return identity[-1] if identity else job.get('requisition_id') or ''


def is_workday_application_scope(job_url, candidate_url):
    expected = workday_identity(job_url)
    parsed = _workday_url(candidate_url)
    if not expected or not parsed:return False
    p, parts = parsed
    if not parts or (p.netloc, parts[0]) != expected[1:3]:return False
    actual = workday_identity(candidate_url)
    if actual:
        # Application steps are site presentation, not an independent permission
        # list. The complete job identity remains the same at every child route.
        return actual == expected
    if parts[1:] != ['login']:return False
    query = parse_qsl(p.query, keep_blank_values=True)
    if not query:return True  # The owned flow already binds this portal and job.
    if len(query) != 1 or query[0][0].casefold() != 'redirect':return False
    redirect = query[0][1]
    if not redirect.startswith('/') or redirect.startswith('//') or '\\' in redirect:return False
    destination = urlsplit(redirect)
    if destination.query or destination.fragment:return False
    return workday_identity(urlunsplit((p.scheme, p.netloc, destination.path, '', ''))) == expected


def form_route_identity(url):
    """Explicit requisition evidence on generic posting/registration routes.

    This is a live-flow comparison only: it does not rewrite historical keys.
    Unknown query parameters and employer path prefixes remain significant.
    """
    try:
        p=urlsplit(canonical_url(url))
        keys={'jobid','job_id','reqid','requisitionid','requisition_id'}
        query=parse_qsl(p.query,keep_blank_values=True)
        values=[v for k,v in query if k.casefold() in keys]
        parts=p.path.strip('/').split('/')
        markers={'jobdetail','jobs','job','positions','postings'}
        index=next((i for i,part in enumerate(parts[:-1]) if part.casefold() in markers and
                    re.fullmatch(r'[A-Za-z0-9_.-]*\d[A-Za-z0-9_.-]*',parts[i+1])),None)
        if index is not None:values.append(parts[index+1])
        if not values or len(set(values))!=1 or not re.fullmatch(r'[A-Za-z0-9_.-]{1,150}',values[0]):return None
        prefix='/'.join(parts[:index] if index is not None else parts[:-1]).casefold()
        opaque=tuple((k,v) for k,v in query if k.casefold() not in keys)
        return p.scheme,p.netloc,prefix,values[0],opaque
    except (ValueError,ProtocolError):return None


def application_match(job_url, candidate_url):
    """Separate a conflicting identity from a page the helper cannot recognize."""
    if is_same_application_scope(job_url, candidate_url):return {'status': 'same_job'}
    try:
        expected, actual = urlsplit(job_url), urlsplit(candidate_url)
        different = expected.netloc.casefold() != actual.netloc.casefold()
        li_expected,li_actual=linkedin_identity(job_url),linkedin_identity(candidate_url)
        if li_expected and li_actual:different=li_expected!=li_actual
        wd_expected, wd_actual = workday_identity(job_url), workday_identity(candidate_url)
        if wd_expected and wd_actual:different = wd_expected != wd_actual
        gh_expected, gh_actual = query_requisition(job_url), query_requisition(candidate_url)
        if gh_expected and gh_actual:different = different or gh_expected != gh_actual
        icims_expected,icims_actual=icims_identity(job_url),icims_identity(candidate_url)
        if icims_expected and icims_actual:different=different or icims_expected!=icims_actual
        route_expected,route_actual=form_route_identity(job_url),form_route_identity(candidate_url)
        if route_expected and route_actual:different=different or route_expected[:4]!=route_actual[:4]
        return {'status': 'different_job' if different else 'identity_unresolved'}
    except ValueError:return {'status': 'identity_unresolved'}


def public_url(url):
    """Diagnostics never require authentication query strings or fragments."""
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, '', ''))


def _rippling_scope_url(url):
    """Compare Rippling's locale presentation without changing retained URLs."""
    try:
        p = urlsplit(canonical_url(url))
        if p.hostname != 'ats.rippling.com':return url
        match = re.fullmatch(
            r'/[A-Za-z]{2}-[A-Za-z]{2}(/[^/]+/jobs/'
            r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
            r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?:/.*)?)', p.path)
        if not match:return url
        # Tenant, full UUID, child path and non-tracking query remain subject
        # to the existing comparison. This is not a general locale alias.
        return urlunsplit(p._replace(path=match[1]))
    except (ValueError, ProtocolError):return url


def _dayforce_scope_url(url):
    """Normalize Dayforce locale and known manual application attribution."""
    try:
        p = urlsplit(canonical_url(url))
        if p.hostname != 'jobs.dayforcehcm.com':return url
        match = re.fullmatch(
            r'(?:/[A-Za-z]{2}-[A-Za-z]{2})?(/[^/]+/(?i:CANDIDATEPORTAL)/jobs/[0-9]+)(/.*)?', p.path)
        if not match:return url
        child = match[2] or ''
        query = p.query
        if p.scheme == 'https' and child == '/apply/manualApplication':
            # canonical_url has already sorted the query and removed UTM tags.
            # Match the complete observed bundle and retain any other query.
            pairs = parse_qsl(query, keep_blank_values=True)
            if pairs in (
                [('applicationSource', 'Manual'), ('ref', 'Simplify'), ('source', 'Simplify')],
                [('applicationSource', 'Manual'), ('ref', 'Simplify'), ('src', 'Simplify')],
            ):
                query = 'applicationSource=Manual'
        return urlunsplit(p._replace(path=match[1] + child, query=query))
    except (ValueError, ProtocolError):return url


def is_same_application_scope(job_url: str, candidate_url: str) -> bool:
    try:
        job_url, candidate_url = _rippling_scope_url(job_url), _rippling_scope_url(candidate_url)
        job_url, candidate_url = _dayforce_scope_url(job_url), _dayforce_scope_url(candidate_url)
        gh_expected,gh_actual=ats_posting_identity(job_url),ats_posting_identity(candidate_url)
        if gh_expected and gh_actual and gh_expected[0]==gh_actual[0]=='greenhouse':return gh_expected==gh_actual
        li_expected,li_actual=linkedin_identity(job_url),linkedin_identity(candidate_url)
        if li_expected or li_actual:return bool(li_expected and li_actual and li_expected==li_actual)
        workday_host=urlsplit(str(job_url).strip()).hostname or ''
        if workday_host.casefold().endswith('.myworkdayjobs.com') and workday_identity(job_url):
            return is_workday_application_scope(job_url, candidate_url)
        icims_expected,icims_actual=icims_identity(job_url),icims_identity(candidate_url)
        if icims_expected and icims_actual and icims_expected==icims_actual:return True
        job_p = urlsplit(canonical_url(job_url))
        cand_p = urlsplit(canonical_url(candidate_url))
        if job_p.scheme.lower() != cand_p.scheme.lower() or job_p.scheme.lower() not in ('https', 'http'):
            return False
        job_host = job_p.netloc.lower()
        cand_host = cand_p.netloc.lower()
        if job_host == 'boards.greenhouse.io': job_host = 'job-boards.greenhouse.io'
        if cand_host == 'boards.greenhouse.io': cand_host = 'job-boards.greenhouse.io'
        if job_host != cand_host:
            return False
        if any(seq in str(candidate_url).lower() for seq in ('%2f', '%2e', '%5c', '..')):
            return False
        cand_query = parse_qsl(cand_p.query, keep_blank_values=True)
        if any(k.lower() in ('access_token', 'refresh_token', 'otp', 'password', 'reset_token', 'authorization_code') for k, v in cand_query):
            return False
        if any(k=='gh_jid' for p in (job_p,cand_p) for k,v in parse_qsl(p.query,keep_blank_values=True)):
            if not query_requisition(job_url) or not query_requisition(candidate_url):return False
            expected_gh,actual_gh=greenhouse_query_identity(job_url),greenhouse_query_identity(candidate_url)
            if expected_gh and actual_gh:return expected_gh==actual_gh
        route_expected,route_actual=form_route_identity(job_url),form_route_identity(candidate_url)
        if route_expected and route_actual:return route_expected==route_actual
        if job_p.query!=cand_p.query:return False
        expected_path = job_p.path.rstrip('/')
        actual_path = cand_p.path.rstrip('/')
        return actual_path in (expected_path, expected_path + '/apply', expected_path + '/confirmation')
    except Exception:
        return False


def is_post_submit_scope(job_url: str, candidate_url: str) -> bool:
    """Read-only confirmation scope after intent, never an application-write grant."""
    if is_same_application_scope(job_url,candidate_url) or is_workday_candidate_home(job_url,candidate_url):
        return True
    try:
        job=urlsplit(canonical_url(job_url));current=urlsplit(canonical_url(candidate_url))
        if job.scheme!=current.scheme or job.netloc!=current.netloc:return False
        # Redirects may drop a query but never introduce a conflicting identity.
        expected=parse_qsl(job.query,keep_blank_values=True)
        actual=parse_qsl(current.query,keep_blank_values=True)
        for key in {k for k,v in actual}:
            if [v for k,v in actual if k==key]!=[v for k,v in expected if k==key]:return False
        if any(s in current.path.lower() for s in ('/login','/signin','/reset','/verify','/oauth','..')):return False
        a=job.path.strip('/').split('/');b=current.path.strip('/').split('/')
        if (job.hostname or '').endswith('.myworkdayjobs.com'):
            if a and _LOCALE_RE.fullmatch(a[0]):a=a[1:]
            if b and _LOCALE_RE.fullmatch(b[0]):b=b[1:]
            if not a or not b or a[0].casefold()!=b[0].casefold():return False
            if [part.casefold() for part in b[1:]]==['jobtasks','completed','application']:return not current.query
            # A different requisition on the same career site is never evidence.
            if 'job' in b:
                i=b.index('job');j=a.index('job') if 'job' in a else -1
                return j>=0 and len(a)>j+2 and len(b)>i+2 and b[i+2].casefold()==a[j+2].casefold()
            return len(b)==1 or all(part.casefold() in ('apply','applymanually','confirmation','success','thankyou','thank-you','submitted','userhome','candidatehome') for part in b[1:])
        # Shared company/Greenhouse/Lever thank-you destinations. Keep the
        # employer path prefix and reject another job's id in that prefix.
        end=b[-1].casefold() if b else ''
        if end not in ('confirmation','success','thank-you','thank_you','thankyou','submitted'):return False
        if a and b and a[0].casefold()!=b[0].casefold():return False
        for marker in ('jobs','job','positions','posting','postings'):
            if marker in a and marker in b:
                i=a.index(marker);j=b.index(marker)
                if len(a)>i+1 and len(b)>j+1 and b[j+1]!=a[i+1]:return False
        return True
    except (ValueError,ProtocolError):return False


def is_workday_candidate_home(job_url, candidate_url):
    """Exact tenant career-site confirmation read surface; never authorizes writes."""
    try:
        job=urlsplit(canonical_url(job_url)); candidate=urlsplit(canonical_url(candidate_url))
        if job.scheme!='https' or candidate.scheme!='https' or job.netloc!=candidate.netloc:
            return False
        if not (job.hostname or '').endswith('.myworkdayjobs.com') or candidate.query:
            return False
        parts=job.path.strip('/').split('/')
        other=candidate.path.strip('/').split('/')
        if parts and _LOCALE_RE.fullmatch(parts[0]):parts=parts[1:]
        if other and _LOCALE_RE.fullmatch(other[0]):other=other[1:]
        return bool(parts) and [s.casefold() for s in other]==[parts[0].casefold(),'candidatehome']
    except (ValueError,ProtocolError):
        return False
