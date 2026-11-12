"""Shared profile form catalogue and explicit question meanings.

No inferred candidate facts, model calls, or application lifecycle decisions live
here. An unfamiliar/qualified question returns to the normal executor path.
"""
import copy
import math
import re
import unicodedata


def field(path, label, *, kind='boolean', aliases=(), help='', country=None, mirrors=(), **limits):
    return dict(path=path, label=label, kind=kind, aliases=list(aliases), help=help,
                country=country, mirrors=list(mirrors), **limits)


SECTIONS = [
    dict(id='screening', title='Screening & background', fields=[
        field('standard_answers.background_check_consent', 'Are you willing to undergo a background check?', aliases=[
            'Are you willing to submit to a background check?', 'Do you agree to a background check if hired?',
            'If you receive a job offer, are you willing to submit to a background check?',
            'Are you willing to undergo a background check as a condition of employment?',
            'Do you consent to a background check?']),
        field('standard_answers.drug_test_consent', 'Are you willing to undergo a drug test?', aliases=[
            'Are you willing to submit to a drug test?', 'Do you consent to a drug test?',
            'Are you willing to submit to substance abuse screening as a condition of employment?']),
        field('standard_answers.felony_conviction', 'Have you ever been convicted of a felony?',
              help='General history only. Employer questions can specify offenses, dates, and exclusions.'),
        field('standard_answers.criminal_conviction_history', 'Have you ever been convicted of a criminal offense?', aliases=[
            'Do you have any criminal convictions?', 'Do you have any criminal conviction history?']),
        field('standard_answers.arrest_history', 'Have you ever been arrested?', aliases=['Do you have any arrest history?']),
        field('standard_answers.felony_explanation', 'Felony history explanation', kind='text'),
        field('standard_answers.age_18_or_older', 'Are you at least 18 years old?', aliases=[
            'Are you 18 years old or over?', 'Are you 18 years of age or older?']),
        field('standard_answers.security_clearance', 'Current security clearance', kind='text', aliases=[
            'Current level of U.S. government security clearance', 'What is your current security clearance?']),
    ]),
    dict(id='employment', title='Employment & outside activities', fields=[
        field('standard_answers.currently_employed', 'Are you currently employed?', help='Update when your employment status changes.'),
        field('standard_answers.involuntarily_discharged', 'Have you ever been involuntarily discharged or asked to resign from a position?'),
        field('standard_answers.outside_employment', 'Do you have your own business or any outside employment, including seasonal employment?', aliases=[
            'Do you have your own business, or do you have outside employment, even if seasonal in nature?']),
        field('standard_answers.continue_outside_activities', 'Do you plan to continue outside work or board/advisory activities after joining?', aliases=[
            'Do you currently perform any additional paid or unpaid work, including running a small business, having a second job, or serving as a company director, that you would like to continue if hired?']),
        field('standard_answers.has_non_compete', 'Do you have a non-compete agreement?',
              mirrors=['standard_answers.non_compete_agreement'], aliases=['Are you subject to a non-compete agreement?']),
        field('standard_answers.has_employment_restrictions', 'Do you have any continuing confidentiality, patent, non-compete, non-solicitation, or non-disclosure agreements?', aliases=[
            'Are you bound by continuing confidentiality or patent agreements, or by restrictive covenants such as non-compete, non-solicitation, or non-disclosure?',
            'Are you bound by a continuing confidentiality or patent agreement or any agreements that contain a restrictive covenant including a non-compete, non-solicitation or non-disclosure?'],
              help='Separate from willingness to sign an agreement for a new employer.'),
        field('standard_answers.reason_for_leaving', 'Reason for leaving your most recent role', kind='text'),
        field('standard_answers.may_contact_current_employer', 'May we contact your current employer?', aliases=['May we contact your present employer?']),
        field('standard_answers.professional_references', 'Professional references', kind='text',
              help='Names, roles, relationship, and contact details you want to provide when references are requested.'),
    ]),
    dict(id='authorization', title='Work authorization', fields=[
        field('work_authorization.country', 'Work authorization country', kind='text'),
        field('work_authorization.status', 'Current visa or work authorization status', kind='text', aliases=[
            'What is your current visa or work authorization status?', 'What is your current immigration status in the United States?']),
        field('standard_answers.authorized_to_work_us', 'Are you legally authorized to work in the United States?',
              mirrors=['work_authorization.legally_authorized_us'], country='us'),
        field('standard_answers.requires_sponsorship', 'Do you currently require sponsorship?', mirrors=['work_authorization.needs_sponsorship']),
        field('standard_answers.will_require_sponsorship_future', 'Will you require sponsorship in the future?'),
        field('work_authorization.sponsorship_type_needed', 'Type of immigration support needed', kind='text'),
        field('work_authorization.visa_expiration', 'Visa expiration date', kind='text'),
    ]),
    dict(id='preferences', title='Work preferences & availability', fields=[
        field('work_preferences.remote_only', 'Are you looking exclusively for remote work?'),
        field('work_preferences.hybrid_ok', 'Are you willing to work in a hybrid arrangement?'),
        field('work_preferences.onsite_ok', 'Are you willing to work onsite?'),
        field('standard_answers.willing_to_relocate', 'Are you willing to relocate?', mirrors=['work_preferences.willing_to_relocate']),
        field('work_preferences.relocation_assistance_required', 'Do you require relocation assistance?'),
        field('work_preferences.relocation_timing', 'When would you be willing to relocate?', kind='text'),
        field('standard_answers.willing_to_travel', 'Are you willing to travel?'),
        field('standard_answers.travel_percentage_ok', 'Maximum travel percentage', kind='number', min=0, max=100,
              help='General preference. Individual jobs can have their own saved answer.'),
        field('work_preferences.notice_period_days', 'Notice period (days)', kind='number', min=0),
        field('work_preferences.earliest_start_date', 'Earliest start date or availability', kind='text'),
        field('work_preferences.preferred_work_hours', 'What are your preferred work hours?', kind='text'),
        field('work_preferences.open_to_individual_contributor', 'Are you open to an individual contributor role?', aliases=[
            'Are you looking for or open to an individual contributor role?']),
        field('standard_answers.can_work_overtime', 'Are you willing to work overtime?'),
        field('standard_answers.can_work_weekends', 'Are you willing to work weekends?'),
        field('standard_answers.remote_workspace_ready', 'Do you have a suitable workspace and connectivity to work from home?'),
        field('standard_answers.has_drivers_license', "Do you have a driver's license?"),
        field('standard_answers.has_reliable_transportation', 'Do you have reliable transportation?'),
    ]),
    dict(id='compensation', title='Compensation preferences', fields=[
        field('work_preferences.min_base_comp', 'Minimum annual base salary', kind='number', min=0),
        field('work_preferences.min_total_comp', 'Minimum annual total compensation', kind='number', min=0),
        field('work_preferences.salary_expectation.min', 'Desired compensation range — minimum', kind='number', min=0),
        field('work_preferences.salary_expectation.max', 'Desired compensation range — maximum', kind='number', min=0),
        field('work_preferences.salary_expectation.currency', 'Compensation currency', kind='text'),
        field('work_preferences.salary_expectation.includes_bonus', 'Does the desired range include bonus?'),
    ]),
    dict(id='communication', title='Communication & verification', fields=[
        field('standard_answers.sms_consent', 'Do you want to receive SMS text messages?', aliases=[
            'Do you consent to receiving recruiting text messages?']),
        field('standard_answers.identity_verification_consent', 'Are you willing to complete third-party identity verification?',
              help='May involve a government-issued ID and a live selfie. Specific employer terms remain separate.'),
        field('standard_answers.interview_recording_consent', 'Do you consent to interview recording?',
              help='A general preference; existing employer-specific recording responses keep their scope.'),
    ]),
    dict(id='immigration_details', title='Additional immigration questions', optional=True, fields=[
        field('work_authorization.i140_approved', 'Has an I-140 petition been approved on your behalf?', country='us', aliases=[
            'Has an I-140 (Immigrant Visa Petition) been filed and approved on your behalf?',
            'Has an employer ever filed an I-140 petition on your behalf that was approved? (An I-140 is typically filed as part of the employment-based green card process. If you have never had an I-140 filed for you, please select “No.”)']),
        field('work_authorization.employment_based_category', 'What employment-based (EB) category was your petition filed under?', kind='text', country='us'),
        field('work_authorization.j1_home_residency_requirement', 'If you ever held J-1 status, are you currently subject to the 2-year home residency requirement?', country='us'),
        field('work_authorization.h1b_time_in_us', 'How many years have you been present in the U.S. in H-1B status?', kind='text', country='us'),
        field('work_authorization.h1b_maxout_date', 'H-1B max-out date, if known', kind='text', country='us'),
    ]),
    dict(id='regulatory', title='Government, licensing & regulatory questions', optional=True, fields=[
        field('standard_answers.government_employment_history', 'Are you currently, planning to be, or have you previously been employed by a government or regulatory entity?', aliases=[
            'Are you presently, planning to, or have you previously been, employed by a government or regulatory entity (federal, state, or local), either as an employee, elected or appointed official, contractor, or consultants?'],
              help='Includes current, past, or planned work as an employee, official, contractor, or consultant.'),
        field('standard_answers.government_official_or_immediate_family', 'Are you or an immediate family member a government official?',
              help='Employer-specific definitions and lookback periods remain in scoped answers.'),
        field('standard_answers.public_official_relationships', 'Do you have a familial relationship or close association with a public official?', aliases=[
            'Do you have any familial relationship (parent, child, sibling, spouse, domestic partner, grandparent, uncle or aunt) or close association (a significant personal or ongoing business relationship) with a public official, including elected or appointed local, state or federal officials and employees, contractors, consultants or advisors of a public entity?']),
        field('standard_answers.government_program_debarment', 'Have you been excluded, debarred, suspended, or proposed for exclusion from government programs?', country='us', aliases=[
            'Are you currently, have you ever been, or has the government ever proposed that you be excluded, debarred, suspended, or otherwise ineligible to participate in any federal or state health care program or other government procurement programs (e.g., Medicare or Medicaid)?'],
              help='Federal or state healthcare and government procurement programs; includes proposed exclusions.'),
        field('standard_answers.professional_license_disciplinary_history', 'Have you had or do you anticipate disciplinary action on a professional license, certification, or credential?', aliases=[
            'Have you ever had, or do you anticipate receiving, any disciplinary action on any professional license, certification, or credential, including fines, citations, penalties, reprimands, reprovals, probation, practice restrictions, revocation, surrender, or suspension?']),
        field('standard_answers.financial_regulatory_sanctions', 'Have you ever been subject to financial regulatory charges or sanctions?', aliases=[
            'Have you ever been subject to administrative or regulatory charges, fines, license revocations, orders, judgments, decrees, or sanctions related to financial regulatory agencies, banking, securities, or investment activities?'],
              help='Includes charges, fines, license revocations, orders, judgments, decrees, and sanctions in banking, securities, or investment activities.'),
        field('standard_answers.finra_registration_history', 'Do you currently hold or have you previously held any FINRA registrations?', country='us', aliases=[
            'Do you currently hold or have you previously held any FINRA registration(s)?']),
    ]),
]
FIELDS = {f['path']: f for section in SECTIONS for f in section['fields']}


def wording(text):
    text = unicodedata.normalize('NFKC', str(text)).casefold()
    text = re.sub(r'\bdo i\b', 'do you', text)
    text = re.sub(r'\bhave i\b', 'have you', text)
    text = re.sub(r'\bam i\b', 'are you', text)
    text = re.sub(r'\bmy\b', 'your', text)
    return ' '.join(re.findall(r'[a-z0-9]+', text))


WORDINGS = {wording(q): f['path'] for f in FIELDS.values() for q in [f['label'], *f['aliases']]}
COMBINED_SCREENING = {wording(q) for q in [
    'Are you willing to submit to a background check and drug test?',
    'Are you willing to submit to a background check and substance abuse screening as a condition of employment?',
]}


def field_for_question(question):
    return WORDINGS.get(wording(question))


def get_value(profile, path):
    value = profile
    for key in path.split('.'):
        if not isinstance(value, dict):return None
        value = value.get(key)
    return value


def set_value(profile, path, value):
    parts = path.split('.')
    for key in parts[:-1]:
        if not isinstance(profile.get(key), dict):
            profile[key] = {'status':profile[key]} if key == 'work_authorization' and isinstance(profile.get(key), str) else {}
        profile = profile[key]
    profile[parts[-1]] = value


def valid_value(spec, value):
    if value is None:return True
    if spec['kind'] == 'boolean':return type(value) is bool
    if spec['kind'] == 'text':return isinstance(value, str) and len(value) <= 10000
    return (type(value) in (int, float) and math.isfinite(value)
            and value >= spec.get('min', float('-inf')) and value <= spec.get('max', float('inf')))


def value_for_field(profile, path):
    value = get_value(profile, path)
    if path == 'work_authorization.status' and isinstance(profile.get('work_authorization'), str):
        value = profile['work_authorization']
    spec = FIELDS[path]
    if value is None:
        values = [get_value(profile, alias) for alias in spec['mirrors']]
        values = [v for v in values if v is not None]
        if values and all(v == values[0] for v in values):value = values[0]
    if path == 'standard_answers.authorized_to_work_us':
        standard = profile.get('standard_answers') or {}
        auth = profile.get('work_authorization') or {}
        # Older profiles used this general key for US eligibility. Preserve the
        # read fallback until an explicit US field is saved, including unset.
        if ('authorized_to_work_us' not in standard
                and (not isinstance(auth, dict) or 'legally_authorized_us' not in auth)):
            value = standard.get('legally_authorized_to_work', value)
    return value if valid_value(spec, value) else None


def structured_answer(question, profile):
    path = field_for_question(question)
    if path:
        value = value_for_field(profile, path)
        return value if value != '' else None
    if wording(question) in COMBINED_SCREENING:
        values = [value_for_field(profile, 'standard_answers.' + key)
                  for key in ('background_check_consent', 'drug_test_consent')]
        if any(v is False for v in values):return False
        if all(v is True for v in values):return True
    return None


def source_value(path, answer):
    """Only an explicit value can become a suggested field value."""
    spec = FIELDS[path]
    if isinstance(answer, dict):answer = answer.get('label', answer.get('value'))
    if spec['kind'] == 'boolean':
        if type(answer) is bool:return answer
        if not isinstance(answer, str):return None
        if re.search(r'\b(but|except|unless|depending|depends|unsure|uncertain)\b', answer, re.I):return None
        match = re.match(r'^\s*(yes|no)\s*(?:[,.;!]|$)', answer, re.I)
        return match[1].casefold() == 'yes' if match else None
    if path == 'work_authorization.employment_based_category' and isinstance(answer, str):
        matches = set(re.findall(r'\bEB[- ]?([1-5])\b', answer, re.I))
        return 'EB-' + next(iter(matches)) if len(matches) == 1 else None
    if path == 'work_authorization.h1b_time_in_us' and isinstance(answer, str):
        match = re.fullmatch(r'(?:I have been present in the U\.S\. in H-1B status for )?(\d+(?:\.\d+)?\+?)(?: years\.?)?', answer.strip(), re.I)
        if match:return match[1]
    # Numeric ranges, rounded durations, and contextual salary amounts are never
    # converted to a different numeric fact during suggestion generation.
    return answer if valid_value(spec, answer) and answer not in ('', None) else None


def schema():
    return copy.deepcopy(SECTIONS)
