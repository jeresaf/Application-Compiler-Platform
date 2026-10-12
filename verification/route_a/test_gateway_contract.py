"""Executable design oracle, NOT an adapter or security implementation.

All labels and evidence flags are symbolic test inputs. No keys, signatures,
sessions, receipts, databases, journal entries or authority grants are issued.
Future integration must satisfy this contract using independently verified facts.
"""
from dataclasses import dataclass, replace, FrozenInstanceError
import unittest


class Denied(ValueError):
    pass


@dataclass(frozen=True)
class Subject:
    repository: str
    application: str
    configuration: str
    operation: str
    action: str
    proposal_version: str
    plan: bytes
    expected_head: tuple
    author: str
    proof_fingerprint: str
    retry: str
    scopes: tuple


@dataclass(frozen=True)
class Context:
    subject: Subject
    caller: str
    purpose: str


@dataclass(frozen=True)
class HostFacts:
    repository: str
    application: str
    configuration: str
    authenticated_endpoint: bool = True
    active_configuration: bool = True


PURPOSES = frozenset({'bootstrap', 'propose', 'review', 'approve', 'apply',
                      'retry', 'audit', 'export', 'restore'})
STATES = frozenset({'RESERVED', 'JOURNAL_COMMITTED', 'RECEIPT_STORED',
                    'WITNESSED', 'PUBLISHED', 'REJECTED', 'EXPIRED',
                    'RECOVERY_REQUIRED', 'QUARANTINED'})
STABLE = frozenset({'RESERVED', 'JOURNAL_COMMITTED', 'RECEIPT_STORED', 'WITNESSED'})
NORMAL = {'RESERVED': 'JOURNAL_COMMITTED', 'JOURNAL_COMMITTED': 'RECEIPT_STORED',
          'RECEIPT_STORED': 'WITNESSED', 'WITNESSED': 'PUBLISHED'}


def bind(host, subject, caller, purpose):
    # HostFacts model facts resolved OUTSIDE the adapter by trusted registration.
    # This function cannot authenticate a real caller or configuration.
    if not host.authenticated_endpoint or not host.active_configuration:
        raise Denied('host trust')
    if (subject.repository, subject.application, subject.configuration) != (
            host.repository, host.application, host.configuration):
        raise Denied('repository binding')
    if subject.action not in {'GENESIS_ACCEPT', 'SEMANTIC_TRANSITION_ACCEPT'}:
        raise Denied('unknown history action')
    if purpose == 'bootstrap' and subject.action != 'GENESIS_ACCEPT':
        raise Denied('wrong bootstrap action')
    if purpose in {'propose','review','approve','apply'} and subject.action != 'SEMANTIC_TRANSITION_ACCEPT':
        raise Denied('wrong proposal action')
    if purpose not in PURPOSES or not caller:
        raise Denied('operation purpose')
    text_fields = ('repository', 'application', 'configuration', 'operation', 'action',
                   'proposal_version', 'author', 'proof_fingerprint', 'retry')
    if any(not isinstance(getattr(subject, field), str) or not getattr(subject, field)
           for field in text_fields):
        raise Denied('nonimmutable or missing subject identity')
    if not isinstance(subject.plan, bytes) or not isinstance(subject.expected_head, tuple):
        raise Denied('mutable subject')
    if not isinstance(subject.scopes, tuple) or any(not isinstance(x, str) for x in subject.scopes):
        raise Denied('mutable scopes')
    if any(not isinstance(x, (str, int)) for x in subject.expected_head):
        raise Denied('mutable head')
    return Context(subject, caller, purpose)


def check_proposal(context, stored_subject, current_version, proof, reviewer,
                   *, independent_grant, current_authority, live_head, caller_action_grant):
    if not caller_action_grant:
        raise Denied('missing caller action grant')
    if context.purpose not in {'approve', 'apply'}:
        raise Denied('context purpose')
    if context.subject != stored_subject or current_version != stored_subject.proposal_version:
        raise Denied('changed proposal')
    if proof != stored_subject.proof_fingerprint or live_head != stored_subject.expected_head:
        raise Denied('changed proof or stale head')
    if not current_authority or not independent_grant or reviewer == stored_subject.author:
        raise Denied('review authority')
    if context.purpose == 'approve' and context.caller != reviewer:
        raise Denied('wrong reviewer')
    if context.purpose == 'apply' and context.caller != stored_subject.author:
        raise Denied('wrong applying author')
    return stored_subject


@dataclass(frozen=True)
class Ledger:
    subject: Subject
    state: str = 'RESERVED'
    stable: str | None = None


def advance(row, target, *, verified_effect=False, proven_uncommitted=False,
            reconciled=False):
    if row.state not in STATES or target not in STATES or target == row.state:
        raise Denied('unknown or repeated state write')
    if target == 'QUARANTINED' and row.state not in {'REJECTED', 'EXPIRED', 'QUARANTINED'}:
        return replace(row, state=target, stable=row.stable or row.state)
    if target == 'RECOVERY_REQUIRED' and row.state in STABLE:
        return replace(row, state=target, stable=row.state)
    if row.state == 'RECOVERY_REQUIRED':
        if target != row.stable or not reconciled:
            raise Denied('unreconciled recovery')
        return replace(row, state=target, stable=None)
    if row.state == 'RESERVED' and target in {'REJECTED', 'EXPIRED'}:
        if not proven_uncommitted:
            raise Denied('uncertain commit existence')
        return replace(row, state=target)
    if NORMAL.get(row.state) != target or not verified_effect:
        raise Denied('invalid progression or missing independently verified effect')
    return replace(row, state=target)


def retrieve(context, row, requested, *, authenticated, read_grant,
             explicit_delegate=False, commit_and_receipt_verified=False):
    if context.purpose != 'retry' or not authenticated or not read_grant:
        raise Denied('separate read authorization')
    if context.subject != row.subject or requested != row.subject:
        raise Denied('wrong receipt subject')
    if context.caller != row.subject.author and not explicit_delegate:
        raise Denied('wrong receipt principal')
    if row.state != 'PUBLISHED' or not commit_and_receipt_verified:
        raise Denied('receipt not usable')
    return 'AUTHORIZED_READ_ONLY'  # No receipt object or journal acceptance.


@dataclass(frozen=True)
class HistoricalFacts:
    identity: bool = True
    reviewer_grant: bool = True
    signature: bool = True
    key_validity: bool = True
    issue_time: bool = True
    commit_time: bool = True
    revocation_history: bool = True
    revocation_allows: bool = True
    scopes: bool = True
    original_configuration: bool = True


def historical_context(host, chain, index, *, independent_checkpoint_matches,
                       structural_valid, historical_authority_valid, authority_facts=None):
    # chain is symbolic immutable (head, predecessor, Subject) data, not a journal.
    if (not independent_checkpoint_matches or not structural_valid or not historical_authority_valid
            or not isinstance(authority_facts, HistoricalFacts)
            or not all(getattr(authority_facts, f) for f in HistoricalFacts.__dataclass_fields__)):
        raise Denied('incomplete independent audit')
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(chain):
        raise Denied('invalid historical sequence')
    head, previous, subject = chain[index]
    expected = ('EMPTY_UNINITIALIZED',) if index == 0 else chain[index - 1][0]
    if previous != expected or subject.expected_head != expected:
        raise Denied('untrusted predecessor')
    return bind(host, subject, 'TEST-AUDITOR', 'audit')


class GatewayContractTests(unittest.TestCase):
    def setUp(self):
        self.host = HostFacts('TEST-REPOSITORY-A', 'TEST-APPLICATION-A', 'TEST-CONFIG-A')
        self.subject = Subject(self.host.repository, self.host.application,
                               self.host.configuration, 'TEST-OPERATION-A',
                               'SEMANTIC_TRANSITION_ACCEPT', 'TEST-PROPOSAL-V1',
                               b'TEST-PLAN-BYTES', (0, 'TEST-CANONICAL', 'TEST-HEAD'),
                               'TEST-AUTHOR', 'TEST-PROOF-FINGERPRINT-NOT-A-PROOF',
                               'TEST-RETRY-ID', ('MIGRATION', 'SECURITY', 'SEMANTIC'))
        self.row = Ledger(self.subject)

    def context(self, purpose='apply', caller='TEST-AUTHOR', subject=None):
        return bind(self.host, subject or self.subject, caller, purpose)

    def test_all_nine_lifecycle_contexts_are_explicit_and_immutable(self):
        for purpose in PURPOSES:
            subject=replace(self.subject,action='GENESIS_ACCEPT') if purpose=='bootstrap' else self.subject
            c = self.context(purpose,subject=subject)
            self.assertEqual(purpose, c.purpose)
            with self.assertRaises(FrozenInstanceError): c.purpose = 'other'
            with self.assertRaises(FrozenInstanceError): c.subject.plan = b'changed'
        with self.assertRaises(Denied): self.context('default')
        for field, value in [('plan', bytearray(b'mutable')), ('expected_head', [0]),
                             ('scopes', ['SEMANTIC']), ('expected_head', (['nested'],)),
                             ('operation', ['nested'])]:
            with self.subTest(field=field), self.assertRaises(Denied):
                self.context(subject=replace(self.subject, **{field: value}))

    def test_cross_repository_application_configuration_and_endpoint_rejected(self):
        for field in ('repository', 'application', 'configuration'):
            with self.subTest(field=field), self.assertRaises(Denied):
                self.context(subject=replace(self.subject, **{field: 'OTHER'}))
        for field in ('authenticated_endpoint', 'active_configuration'):
            with self.subTest(field=field), self.assertRaises(Denied):
                bind(replace(self.host, **{field: False}), self.subject, 'TEST-AUTHOR', 'apply')

    def check(self, context=None, **changes):
        args=dict(stored_subject=self.subject, current_version=self.subject.proposal_version,
                  proof=self.subject.proof_fingerprint, reviewer='TEST-REVIEWER',
                  independent_grant=True, current_authority=True, caller_action_grant=True,
                  live_head=self.subject.expected_head)
        args.update(changes)
        return check_proposal(context or self.context(), **args)

    def test_approval_and_application_preserve_exact_subject(self):
        self.assertEqual(self.subject, self.check(self.context('approve', 'TEST-REVIEWER')))
        self.assertEqual(self.subject, self.check())
        for field, value in [('operation', 'OTHER'), ('proposal_version', 'V2'),
                             ('plan', b'changed'), ('action', 'GENESIS_ACCEPT'),
                             ('proof_fingerprint', 'OTHER'), ('retry', 'OTHER')]:
            with self.subTest(field=field), self.assertRaises(Denied):
                self.check(self.context(subject=replace(self.subject, **{field: value})))
        for changes in [{'current_version':'V2'}, {'proof':'OTHER'},
                        {'live_head':(1, 'TEST-NEW', 'TEST-NEW-HEAD')},
                        {'reviewer':'TEST-AUTHOR'}, {'independent_grant':False},
                        {'current_authority':False}, {'caller_action_grant':False}]:
            with self.subTest(changes=changes), self.assertRaises(Denied): self.check(**changes)
        with self.assertRaises(Denied): self.check(self.context('apply', 'TEST-OPERATOR'))
        with self.assertRaises(Denied): self.check(self.context('approve', 'TEST-OPERATOR'))
        with self.assertRaises(Denied): self.check(self.context('review'))

    def test_contexts_do_not_leak_between_interleaved_operations(self):
        first=self.context(); other=replace(self.subject, operation='TEST-OPERATION-B', plan=b'B')
        second=self.context(subject=other)
        self.assertEqual(self.subject, first.subject)
        self.assertEqual(other, second.subject)
        with self.assertRaises(Denied): self.check(second)
        self.assertEqual(self.subject, self.check(first))

    def test_closed_normal_sequence_requires_evidence_at_each_stage(self):
        row=self.row
        for target in ('JOURNAL_COMMITTED','RECEIPT_STORED','WITNESSED','PUBLISHED'):
            with self.assertRaises(Denied): advance(row,target)
            row=advance(row,target,verified_effect=True)
            self.assertEqual(self.subject,row.subject)
        self.assertEqual('PUBLISHED',row.state)

    def test_all_state_pairs_reject_undefined_edges(self):
        allowed={('RESERVED','JOURNAL_COMMITTED'),('JOURNAL_COMMITTED','RECEIPT_STORED'),
                 ('RECEIPT_STORED','WITNESSED'),('WITNESSED','PUBLISHED'),
                 ('RESERVED','REJECTED'),('RESERVED','EXPIRED')}
        allowed |= {(s,'RECOVERY_REQUIRED') for s in STABLE}
        allowed |= {(s,'QUARANTINED') for s in STATES-{'QUARANTINED','REJECTED','EXPIRED'}}
        for start in STATES:
            for end in STATES:
                row=Ledger(self.subject,start)
                if (start,end) not in allowed:
                    with self.subTest(start=start,end=end), self.assertRaises(Denied):
                        advance(row,end,verified_effect=True,proven_uncommitted=True)
        with self.assertRaises(Denied): advance(self.row,'UNKNOWN',verified_effect=True)
        with self.assertRaises(Denied): advance(Ledger(self.subject,'UNKNOWN'),'RESERVED')

    def test_every_crash_window_requires_exact_reconciliation(self):
        for stage in STABLE:
            row=Ledger(self.subject,stage)
            recovery=advance(row,'RECOVERY_REQUIRED')
            with self.assertRaises(Denied): advance(recovery,stage)
            for wrong in STABLE-{stage}:
                with self.assertRaises(Denied): advance(recovery,wrong,reconciled=True)
            restored=advance(recovery,stage,reconciled=True)
            self.assertEqual(row,restored)
            self.assertEqual(NORMAL[stage],advance(restored,NORMAL[stage],verified_effect=True).state)

    def test_uncertain_commit_cannot_be_rejected_or_expired(self):
        for target in ('EXPIRED','REJECTED'):
            with self.assertRaises(Denied): advance(self.row,target)
            terminal=advance(self.row,target,proven_uncommitted=True)
            for state in STATES:
                with self.assertRaises(Denied): advance(terminal,state,verified_effect=True)
            committed=Ledger(self.subject,'JOURNAL_COMMITTED')
            with self.assertRaises(Denied): advance(committed,target,proven_uncommitted=True)

    def test_quarantine_cannot_resume_automatically(self):
        for stage in STABLE|{'PUBLISHED','RECOVERY_REQUIRED'}:
            q=advance(Ledger(self.subject,stage),'QUARANTINED')
            for target in STATES:
                with self.assertRaises(Denied): advance(q,target,reconciled=True,verified_effect=True)

    def read(self, context=None, row=None, requested=None, **changes):
        args=dict(authenticated=True,read_grant=True,commit_and_receipt_verified=True)
        args.update(changes)
        return retrieve(context or self.context('retry'), row or Ledger(self.subject,'PUBLISHED'),
                        requested or self.subject, **args)

    def test_retry_requires_independent_read_authorization(self):
        self.assertEqual('AUTHORIZED_READ_ONLY',self.read())
        for changes in [{'authenticated':False},{'read_grant':False},
                        {'commit_and_receipt_verified':False}]:
            with self.assertRaises(Denied): self.read(**changes)
        with self.assertRaises(Denied): self.read(self.context('apply'))
        with self.assertRaises(Denied): self.read(self.context('retry','TEST-OPERATOR'))
        self.assertEqual('AUTHORIZED_READ_ONLY',self.read(
            self.context('retry','TEST-DELEGATE'),explicit_delegate=True))
        for state in STATES-{'PUBLISHED'}:
            with self.assertRaises(Denied): self.read(row=Ledger(self.subject,state))

    def test_retry_rejects_every_changed_subject_field(self):
        for field,value in [('repository','OTHER'),('application','OTHER'),
                            ('configuration','OTHER'),('operation','OTHER'),
                            ('action','GENESIS_ACCEPT'),('proposal_version','V2'),
                            ('plan',b'OTHER'),('expected_head',(1,'OTHER','OTHER')),
                            ('author','OTHER'),('proof_fingerprint','OTHER'),
                            ('retry','OTHER'),('scopes',('SEMANTIC',))]:
            with self.subTest(field=field), self.assertRaises(Denied):
                self.read(requested=replace(self.subject,**{field:value}))

    def test_historical_predecessor_comes_from_chain_not_claim(self):
        empty=('EMPTY_UNINITIALIZED',); head=(0,'TEST-CANONICAL','TEST-HEAD')
        genesis=replace(self.subject,action='GENESIS_ACCEPT',expected_head=empty)
        chain=((head,empty,genesis),((1,'TEST-NEXT','TEST-NEXT-HEAD'),head,self.subject))
        args=dict(independent_checkpoint_matches=True,structural_valid=True,
                  historical_authority_valid=True,authority_facts=HistoricalFacts())
        for invalid in (-1, 2, True):
            with self.assertRaises(Denied): historical_context(self.host,chain,invalid,**args)
        for index in (0,1):
            self.assertEqual(chain[index][2],historical_context(self.host,chain,index,**args).subject)
        # Internally consistent forged proof/entry claim still disagrees with predecessor.
        wrong=(0,'TEST-OTHER','TEST-FORGED')
        altered=(chain[0],(chain[1][0],wrong,replace(self.subject,expected_head=wrong)))
        with self.assertRaises(Denied): historical_context(self.host,altered,1,**args)
        for field in args:
            bad={**args,field:False}
            with self.assertRaises(Denied): historical_context(self.host,chain,1,**bad)
        for field in HistoricalFacts.__dataclass_fields__:
            bad={**args,'authority_facts':replace(HistoricalFacts(),**{field:False})}
            with self.subTest(field=field), self.assertRaises(Denied):
                historical_context(self.host,chain,1,**bad)
        with self.assertRaises(Denied): historical_context(
            replace(self.host,repository='OTHER'),chain,1,**args)

    def test_history_migration_scope_never_grants_execution(self):
        self.assertIn('MIGRATION',self.subject.scopes)
        for purpose in ('data_binding','sql','postgresql_migration','deployment'):
            with self.assertRaises(Denied): self.context(purpose)


if __name__ == '__main__':
    unittest.main()
