"""Synthetic Dayforce locale comparisons; no live posting or account data."""
import pytest
from job_applier.managed_identity import application_match, is_same_application_scope, job_key

JOB = 'https://jobs.dayforcehcm.com/en-US/synthetic/CANDIDATEPORTAL/jobs/123'
FORM = JOB.replace('/en-US/', '/')

@pytest.mark.parametrize('portal', ['CANDIDATEPORTAL', 'candidateportal', 'CandidatePortal'])
@pytest.mark.parametrize('locale', ['en-US', 'fr-CA', 'de-DE'])
@pytest.mark.parametrize('suffix', ['', '/apply/manualApplication', '/apply/manualApplication?applicationSource=Manual'])
def test_locale_only_dayforce_transition_preserves_live_scope(locale, suffix, portal):
    before = JOB.replace('en-US', locale).replace('CANDIDATEPORTAL', portal) + suffix
    after = FORM.replace('CANDIDATEPORTAL', portal) + suffix
    assert is_same_application_scope(before, after)
    assert is_same_application_scope(after, before)
    assert application_match(before, after) == {'status': 'same_job'}
    assert job_key(before) != job_key(after)

@pytest.mark.parametrize('other', [
    FORM.replace('synthetic', 'another-tenant'),
    FORM.replace('CANDIDATEPORTAL', 'OTHERPORTAL'),
    FORM.replace('/123', '/124'),
    FORM.replace('jobs.dayforcehcm.com', 'other.example.test'),
    FORM.replace('/synthetic/', '/synthetic%2fother/'),
    FORM + '?reset_token=synthetic',
    FORM + '?applicationSource=Other',
])
def test_dayforce_locale_comparison_keeps_tenant_posting_and_query_guards(other):
    assert not is_same_application_scope(JOB, other)

def test_locale_prefix_on_unrecognized_host_remains_significant():
    assert not is_same_application_scope(JOB.replace('jobs.dayforcehcm.com', 'jobs.example.test'),
                                         FORM.replace('jobs.dayforcehcm.com', 'jobs.example.test'))


@pytest.mark.parametrize('source_key', ['src', 'source'])
def test_dayforce_manual_form_keeps_scope_across_simplify_attribution(source_key):
    before = JOB.replace('CANDIDATEPORTAL', 'candidateportal') + '/apply/manualApplication?applicationSource=Manual'
    after = before.replace('/en-US/', '/') + f'&ref=Simplify&{source_key}=Simplify&utm_source=Simplify'
    assert application_match(before, after) == {'status': 'same_job'}
    assert job_key(before) != job_key(after)
    for conflict in (
        after.replace('/123/', '/124/'),
        after.replace('/synthetic/', '/other-tenant/'),
        after.replace('applicationSource=Manual', 'applicationSource=Other'),
        after.replace('ref=Simplify', 'ref=Other'),
        after + '&jobId=124',
        after + '&ref=Simplify',
        after + '&unknown=synthetic',
        after + '&reset_token=synthetic',
    ):
        assert not is_same_application_scope(before, conflict)
