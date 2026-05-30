"""Tests for the four stage-decision modes.

Mode behavior covered:
- any_member       first vote closes the stage
- unanimous_team   any reject closes as REJECTED; every required voter
                   must approve to close as APPROVED
- majority         strict majority (>50%) of either side closes the stage
- specific_user    that one user's vote decides

Plus: duplicate-vote rejection, non-authorized-user rejection, vote tally
exposed via the stages API.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.tenants.models import OrgMembership, Team, TeamMembership

from .approval import _evaluate_stage_outcome, _required_voter_count, decide_stage, materialize_stages
from .models import ApprovalStage, StageVote, Ticket, TicketType, WorkflowStage

User = get_user_model()
pytestmark = pytest.mark.django_db

HDRS = {"HTTP_X_ORG_SLUG": "acme"}


# ---------------------------------------------------------------------------
# Fixtures — one TT per mode, ticket already escalated
# ---------------------------------------------------------------------------
def _make_tt(org, *, mode: str, approvers: list[str], sequential=True) -> TicketType:
    tt = TicketType.objects.create(
        org=org, identifier=f"acme.{mode}", display_name=f"TT for {mode}", sequential=sequential,
    )
    WorkflowStage.objects.create(
        ticket_type=tt, order=1, name=f"{mode} stage",
        approvers=approvers, mode=mode,
    )
    return tt


def _escalated_ticket(org, requester, tt) -> Ticket:
    t = Ticket.objects.create(
        org=org, requester=requester, ticket_type=tt.identifier,
        title="t", payload={}, status=Ticket.Status.ESCALATED,
    )
    materialize_stages(t)
    return t


@pytest.fixture
def security_team(acme_org):
    return Team.objects.create(org=acme_org, slug="security", name="Security")


@pytest.fixture
def voters(acme_org, security_team):
    """Three approver-role users, all members of the security team."""
    out = []
    for email in ("a@acme.test", "b@acme.test", "c@acme.test"):
        u = User.objects.create_user(email=email, password="pw12345!")
        OrgMembership.objects.create(org=acme_org, user=u, role=OrgMembership.Role.APPROVER)
        TeamMembership.objects.create(team=security_team, user=u)
        out.append(u)
    return out


# ---------------------------------------------------------------------------
# _required_voter_count + _evaluate_stage_outcome — unit-level
# ---------------------------------------------------------------------------
def test_required_voter_count_team_mode(acme_org, security_team, voters) -> None:
    tt = _make_tt(acme_org, mode="unanimous_team", approvers=["security"])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    assert _required_voter_count(stage, acme_org) == 3


def test_required_voter_count_specific_user(acme_org, voters) -> None:
    tt = _make_tt(acme_org, mode="specific_user", approvers=["a@acme.test"])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    assert _required_voter_count(stage, acme_org) == 1


def test_evaluate_outcome_any_member_first_vote_wins(acme_org, voters, security_team) -> None:
    tt = _make_tt(acme_org, mode="any_member", approvers=["security"])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    StageVote.objects.create(stage=stage, user=voters[0], decision=StageVote.Decision.APPROVED)
    assert _evaluate_stage_outcome(stage, acme_org) == ApprovalStage.Status.APPROVED


# ---------------------------------------------------------------------------
# any_member — single vote closes
# ---------------------------------------------------------------------------
def test_any_member_first_approve_closes_approved(acme_org, voters, security_team) -> None:
    tt = _make_tt(acme_org, mode="any_member", approvers=["security"])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    decide_stage(stage=stage, user=voters[0], decision="approved")
    stage.refresh_from_db()
    t.refresh_from_db()
    assert stage.status == "approved"
    assert t.status == "approved"  # only stage, so ticket closes


def test_any_member_first_reject_closes_rejected(acme_org, voters, security_team) -> None:
    tt = _make_tt(acme_org, mode="any_member", approvers=["security"])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    decide_stage(stage=stage, user=voters[0], decision="rejected")
    stage.refresh_from_db()
    t.refresh_from_db()
    assert stage.status == "rejected"
    assert t.status == "rejected"


# ---------------------------------------------------------------------------
# unanimous_team — every voter must approve
# ---------------------------------------------------------------------------
def test_unanimous_first_approve_keeps_pending(acme_org, voters, security_team) -> None:
    tt = _make_tt(acme_org, mode="unanimous_team", approvers=["security"])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    decide_stage(stage=stage, user=voters[0], decision="approved")
    stage.refresh_from_db()
    assert stage.status == "pending"  # need 2 more approves


def test_unanimous_all_approve_closes_approved(acme_org, voters, security_team) -> None:
    tt = _make_tt(acme_org, mode="unanimous_team", approvers=["security"])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    for v in voters:
        decide_stage(stage=stage, user=v, decision="approved")
    stage.refresh_from_db()
    t.refresh_from_db()
    assert stage.status == "approved"
    assert t.status == "approved"


def test_unanimous_any_reject_short_circuits(acme_org, voters, security_team) -> None:
    tt = _make_tt(acme_org, mode="unanimous_team", approvers=["security"])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    decide_stage(stage=stage, user=voters[0], decision="approved")
    decide_stage(stage=stage, user=voters[1], decision="rejected")
    stage.refresh_from_db()
    t.refresh_from_db()
    assert stage.status == "rejected"
    assert t.status == "rejected"
    # voters[2] never voted; that's fine — the reject decided it.


# ---------------------------------------------------------------------------
# majority — >50% of voter universe
# ---------------------------------------------------------------------------
def test_majority_one_of_three_approves_keeps_pending(acme_org, voters, security_team) -> None:
    tt = _make_tt(acme_org, mode="majority", approvers=["security"])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    decide_stage(stage=stage, user=voters[0], decision="approved")
    stage.refresh_from_db()
    assert stage.status == "pending"  # need 2 of 3


def test_majority_two_of_three_approves_closes(acme_org, voters, security_team) -> None:
    tt = _make_tt(acme_org, mode="majority", approvers=["security"])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    decide_stage(stage=stage, user=voters[0], decision="approved")
    decide_stage(stage=stage, user=voters[1], decision="approved")
    stage.refresh_from_db()
    assert stage.status == "approved"


def test_majority_two_of_three_rejects_closes(acme_org, voters, security_team) -> None:
    tt = _make_tt(acme_org, mode="majority", approvers=["security"])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    decide_stage(stage=stage, user=voters[0], decision="rejected")
    decide_stage(stage=stage, user=voters[1], decision="rejected")
    stage.refresh_from_db()
    assert stage.status == "rejected"


def test_majority_one_one_split_stays_pending(acme_org, voters, security_team) -> None:
    """1 approve + 1 reject + 1 still pending → no majority yet, stage stays open."""
    tt = _make_tt(acme_org, mode="majority", approvers=["security"])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    decide_stage(stage=stage, user=voters[0], decision="approved")
    decide_stage(stage=stage, user=voters[1], decision="rejected")
    stage.refresh_from_db()
    assert stage.status == "pending"


# ---------------------------------------------------------------------------
# specific_user
# ---------------------------------------------------------------------------
def test_specific_user_named_user_can_decide(acme_org, voters) -> None:
    tt = _make_tt(acme_org, mode="specific_user", approvers=[voters[0].email])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    decide_stage(stage=stage, user=voters[0], decision="approved")
    stage.refresh_from_db()
    t.refresh_from_db()
    assert stage.status == "approved"
    assert t.status == "approved"


def test_specific_user_other_user_denied(acme_org, voters) -> None:
    from .approval import StageAuthError

    tt = _make_tt(acme_org, mode="specific_user", approvers=[voters[0].email])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    with pytest.raises(StageAuthError):
        decide_stage(stage=stage, user=voters[1], decision="approved")


# ---------------------------------------------------------------------------
# Duplicate vote rejection
# ---------------------------------------------------------------------------
def test_duplicate_vote_rejected(acme_org, voters, security_team) -> None:
    from .approval import ApprovalError

    tt = _make_tt(acme_org, mode="unanimous_team", approvers=["security"])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    decide_stage(stage=stage, user=voters[0], decision="approved")
    with pytest.raises(ApprovalError, match="already voted"):
        decide_stage(stage=stage, user=voters[0], decision="approved")


# ---------------------------------------------------------------------------
# Vote tally exposed via the API
# ---------------------------------------------------------------------------
def test_stages_api_includes_vote_tally(
    client_factory, acme_org, voters, security_team, superuser,
) -> None:
    tt = _make_tt(acme_org, mode="majority", approvers=["security"])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    decide_stage(stage=stage, user=voters[0], decision="approved")

    resp = client_factory(superuser).get(f"/api/tickets/{t.id}/stages/", **HDRS)
    assert resp.status_code == 200
    s0 = resp.json()["stages"][0]
    assert s0["vote_tally"]["approves"] == 1
    assert s0["vote_tally"]["rejects"] == 0
    assert s0["vote_tally"]["required"] == 3
    # Superuser is not a voter — my_vote is null
    assert s0["vote_tally"]["my_vote"] is None


def test_stages_api_my_vote_field(client_factory, acme_org, voters, security_team) -> None:
    tt = _make_tt(acme_org, mode="majority", approvers=["security"])
    t = _escalated_ticket(acme_org, voters[0], tt)
    stage = t.stages.first()
    decide_stage(stage=stage, user=voters[0], decision="approved")

    resp = client_factory(voters[0]).get(f"/api/tickets/{t.id}/stages/", **HDRS)
    s0 = resp.json()["stages"][0]
    assert s0["vote_tally"]["my_vote"] == "approved"
