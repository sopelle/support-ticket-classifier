"""Generate the synthetic support-ticket corpus (dev + test splits).

Tickets are generated from a Scenario, not from a label: a category/priority/intent
in the prompt would just get paraphrased back, producing a corpus the classifier
could ace without proving anything. Each Scenario is seeded from a `cause` - a
specific root cause, documented in data/knowledge_base/ or invented - plus the
situational variables the priority rubric depends on (audit timing, workaround,
tone, ...). No labels are produced here - labeling is issue #5.

A cause is not the same as its symptom: `cause` is a stable identifier that can
surface as more than one customer-visible symptom, in more than one category (an
expired integration credential shows up both as "integration disconnected" in
integrations and "control keeps failing" in controls). `misleading_symptom`
scenarios deliberately use the symptom whose apparent category differs from the
cause's true category - the tie-break the classifier has to get right.

About a third of scenarios are invented (`documented=False`, no `kb_file`): plausible
compliance problems no article covers. Without them the corpus would just be a
copy of the FAQ, and retrieval/cause-discovery work downstream would never have to
handle "not in the docs."

Scenario selection is deterministic (cause rotation + axis cycling), not random
sampling, so re-running reproduces the same scenario list. Neither a `symptom` nor
a `cause` may appear in both splits - causes are partitioned into dev/test pools
per category before any tickets are generated. Already-generated ids (present in
the split file) are skipped, so a partial or failed run can be resumed without
re-billing completed tickets. generation_log.jsonl records the full Scenario for
every id, which is what makes the corpus auditable and regenerable.
"""

import argparse
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from triage.models import Ticket
from triage.taxonomy import Category, Intent

REPO_ROOT = Path(__file__).resolve().parent.parent
DEV_PATH = REPO_ROOT / "data" / "dev" / "tickets.jsonl"
TEST_PATH = REPO_ROOT / "data" / "test" / "tickets.jsonl"
LOG_PATH = REPO_ROOT / "data" / "generation_log.jsonl"

# The classifier being evaluated must not be the model that wrote the corpus.
MODEL = "claude-sonnet-5"

# 5-8 per category (~60 total) / 15-20 per category (~140 total), per the issue.
DEV_COUNTS: dict[Category, int] = {
    Category.FRAMEWORKS: 7,
    Category.CONTROLS: 7,
    Category.EVIDENCE: 8,
    Category.INTEGRATIONS: 7,
    Category.POLICIES: 8,
    Category.ACCESS_MANAGEMENT: 7,
    Category.AUDITS: 8,
    Category.ACCOUNT_BILLING: 8,
}
TEST_COUNTS: dict[Category, int] = {
    Category.FRAMEWORKS: 17,
    Category.CONTROLS: 17,
    Category.EVIDENCE: 18,
    Category.INTEGRATIONS: 17,
    Category.POLICIES: 18,
    Category.ACCESS_MANAGEMENT: 17,
    Category.AUDITS: 18,
    Category.ACCOUNT_BILLING: 18,
}

CATEGORY_BLURB: dict[Category, str] = {
    Category.FRAMEWORKS: "SOC 2 / ISO 27001 / GDPR scoping and setup",
    Category.CONTROLS: "implementing and tracking compliance controls",
    Category.EVIDENCE: "collecting and uploading evidence",
    Category.INTEGRATIONS: "connecting cloud/SaaS accounts to auto-collect evidence",
    Category.POLICIES: "policy templates, customization, and approvals",
    Category.ACCESS_MANAGEMENT: "users, roles, permissions, and access reviews",
    Category.AUDITS: "audit preparation and auditor access",
    Category.ACCOUNT_BILLING: "account setup, subscription, and billing",
}


class AuditTiming(StrEnum):
    IMMINENT = "imminent"
    SCHEDULED = "scheduled"
    NONE = "none"
    NOT_MENTIONED = "not_mentioned"


class Tone(StrEnum):
    NEUTRAL = "neutral"
    FRUSTRATED = "frustrated"
    URGENT_STATED = "urgent_stated"
    RELATIONSHIP_AT_RISK = "relationship_at_risk"


class Difficulty(StrEnum):
    PLAIN = "plain"
    MULTI_TOPIC = "multi_topic"
    MISLEADING_SYMPTOM = "misleading_symptom"
    WORKING_AS_DESIGNED = "working_as_designed"
    MISSING_DECIDING_FACT = "missing_deciding_fact"


# (symptom text, the category that symptom sounds like it belongs to, source kb file or None)
Symptom = tuple[str, Category, str | None]


@dataclass(frozen=True)
class Cause:
    id: str
    true_category: Category
    description: str  # prompt-grounding text; not part of the logged Scenario
    symptoms: tuple[Symptom, ...]  # symptoms[0] always matches true_category


F, C, E, I, P, AM, AU, B = (
    Category.FRAMEWORKS,
    Category.CONTROLS,
    Category.EVIDENCE,
    Category.INTEGRATIONS,
    Category.POLICIES,
    Category.ACCESS_MANAGEMENT,
    Category.AUDITS,
    Category.ACCOUNT_BILLING,
)

DOCUMENTED_CAUSES: list[Cause] = [
    Cause(
        "controls_not_mapped_to_framework",
        F,
        "A batch of controls were added manually and never linked to the framework, so the "
        "nightly readiness job has nothing to count even though each control shows Complete.",
        (("Readiness score is stuck at 0% even though controls are marked complete", F, "frameworks.md"),),
    ),
    Cause(
        "framework_standard_version_auto_migrated",
        F,
        "The account was automatically migrated to a newer version of the framework standard "
        "at renewal, changing control numbering and requirements with no explicit heads-up.",
        (("The framework switched to a different version of the standard", F, "frameworks.md"),),
    ),
    Cause(
        "framework_control_mapping_mismatch",
        F,
        "Two active frameworks scope different systems for what looks like the same control, "
        "so the platform can't safely merge them - it creates separate controls instead.",
        (
            ("Shared control mapping isn't showing between two active frameworks", F, "frameworks.md"),
            ("Duplicate controls appeared after adding a second framework", C, "controls.md"),
        ),
    ),
    Cause(
        "framework_scope_change_not_regenerated",
        F,
        "Control lists only regenerate when a scope change is saved, and a queued audit lock "
        "is delaying that regeneration.",
        (("Scope changes aren't reflected in the control list", F, "frameworks.md"),),
    ),
    Cause(
        "user_lacks_control_permission",
        C,
        "The person being assigned as control owner doesn't have a role with control-"
        "management permissions, so the assignment silently fails to save.",
        (("Control owner assignment isn't saving", C, "controls.md"),),
    ),
    Cause(
        "evidence_uploaded_wrong_location",
        E,
        "The evidence file was uploaded through the general evidence library instead of from "
        "the specific control's own page, so it never auto-attached to that control.",
        (
            ("Evidence isn't linking to the control after upload", E, "evidence.md"),
            ('A control shows "Not Started" even though evidence is attached', C, "controls.md"),
        ),
    ),
    Cause(
        "evidence_processing_stuck",
        E,
        "The uploaded file failed the post-upload OCR/scan step silently and never finished "
        "processing.",
        (('Upload is stuck on "Processing"', E, "evidence.md"),),
    ),
    Cause(
        "evidence_collection_date_backdated",
        E,
        "The customer entered a collection date in the past when uploading, so the evidence's "
        "expiration - calculated from that date - is earlier than they expect.",
        (("Evidence is marked expired but I just uploaded it", E, "evidence.md"),),
    ),
    Cause(
        "evidence_unsupported_file_format",
        E,
        "The uploaded file is in a format the platform doesn't accept, such as an Excel file "
        "or a HEIC photo, and was rejected outright.",
        (("An uploaded file was rejected as an unsupported format", E, "evidence.md"),),
    ),
    Cause(
        "integration_credentials_expired",
        I,
        "The connected integration's OAuth grant or API key was revoked or expired on the "
        "source system's side, so the integration silently stopped authenticating.",
        (
            ('An integration shows "Error" or disconnected unexpectedly', I, "integrations.md"),
            ("An automated control keeps failing with a stale integration error", C, "controls.md"),
        ),
    ),
    Cause(
        "integration_scope_revoked",
        I,
        "A previously granted scope on the connected account was revoked on the source "
        "system's side, so syncs silently stop running.",
        (("Sync hasn't run in several days", I, "integrations.md"),),
    ),
    Cause(
        "integration_connected_with_non_admin_account",
        I,
        "The integration was authorized using an account without admin-level permissions on "
        "the source system, so the platform can't obtain the scopes it needs.",
        (("I get a permission or scope error when connecting", I, "integrations.md"),),
    ),
    Cause(
        "integration_wrong_account_scoped",
        I,
        "The integration is connected to a different cloud account or project than the one "
        "the resource actually lives in, so nothing is found to collect.",
        (("Evidence isn't appearing after a successful sync", I, "integrations.md"),),
    ),
    Cause(
        "policy_acknowledgment_version_mismatch",
        P,
        "The employee acknowledged an earlier version of the policy; acknowledgments don't "
        "carry over when a new version is published.",
        (("An employee's acknowledgment isn't registering as complete", P, "policies.md"),),
    ),
    Cause(
        "policy_approver_not_configured",
        P,
        "The person configured as the policy's approver was removed from the account, so "
        "nothing can move the policy out of Pending Approval.",
        (('A policy is stuck in "Pending Approval"', P, "policies.md"),),
    ),
    Cause(
        "concurrent_editors_conflict",
        P,
        "Two people edited the same policy at once, and one submitted a draft based on an "
        "outdated version, silently reverting the other's newer changes.",
        (("A policy reverted to an older version unexpectedly", P, "policies.md"),),
    ),
    Cause(
        "invite_link_expired",
        AM,
        "The invite - teammate or auditor - was sent more than 7 days ago and its link has "
        "expired, so it silently stopped working.",
        (
            ("An invited teammate never received the invite email", AM, "access_management.md"),
            ("The auditor invite link expired before they used it", AU, "audits.md"),
        ),
    ),
    Cause(
        "stale_session_after_role_change",
        AM,
        "The user's role was changed but they're still on an active login session from "
        "before the change, so the old permissions apply until they log back in.",
        (("A role change isn't taking effect", AM, "access_management.md"),),
    ),
    Cause(
        "sso_metadata_certificate_mismatch",
        AM,
        "The identity provider rotated its signing certificate and the platform still has "
        "the old SSO metadata configured, so the login handshake fails.",
        (("SSO login is failing or stuck in a redirect loop", AM, "access_management.md"),),
    ),
    Cause(
        "user_not_removed_from_source_system",
        AM,
        "The user was removed from the platform but still has an active account on the "
        "underlying connected system, so a fresh access-review snapshot still shows them.",
        (("A removed user still appears in an access review", AM, "access_management.md"),),
    ),
    Cause(
        "stale_point_in_time_snapshot",
        AU,
        "The document being viewed is a point-in-time snapshot generated earlier and doesn't "
        "reflect changes made since - the underlying data is current, the export just isn't "
        "regenerated automatically.",
        (
            ("The audit readiness report shows outdated data", AU, "audits.md"),
            ("The exported PDF is missing recent edits", P, "policies.md"),
        ),
    ),
    Cause(
        "evidence_out_of_audit_scope",
        AU,
        "The evidence the auditor is asking about is attached to a control that isn't in "
        "scope for the specific audit they were invited to.",
        (
            ("My auditor says they can't access requested evidence", AU, "audits.md"),
            ("Evidence I uploaded isn't showing up for our auditor", E, None),
        ),
    ),
    Cause(
        "report_download_role_restricted",
        AU,
        "Only Admins can download the final audit report by default, and the person asking "
        "isn't one.",
        (
            ("The final report or certificate isn't downloadable", AU, "audits.md"),
            ("I don't have permission to download something I need", AM, None),
        ),
    ),
    Cause(
        "billing_seat_count_snapshot_date",
        B,
        "The seat count on the invoice reflects active users as of the billing date, not "
        "today - a user removed after that date isn't reflected until the next cycle.",
        (
            ("My invoice charged the wrong seat count", B, "account_billing.md"),
            ("A user we removed from the team is still showing up and we're being charged for them", AM, None),
        ),
    ),
    Cause(
        "card_issuer_declining_verification_charge",
        B,
        "The card issuer is blocking the small automated verification charge the platform "
        "makes when a payment method is added - a common corporate-card policy.",
        (("Updating my payment method is failing", B, "account_billing.md"),),
    ),
    Cause(
        "billing_cycle_not_yet_elapsed",
        B,
        "A plan downgrade takes effect at the start of the next billing cycle, not "
        "immediately, so an invoice generated shortly after still reflects the old plan.",
        (("My downgrade isn't reflected on the next invoice", B, "account_billing.md"),),
    ),
    Cause(
        "manual_billing_adjustment_untracked",
        B,
        "The charge in question was a one-time adjustment processed manually rather than "
        "through the normal invoicing flow, so it has no auto-generated receipt.",
        (("I'm missing a receipt or invoice for a past charge", B, "account_billing.md"),),
    ),
]

INVENTED_CAUSES: list[Cause] = [
    Cause(
        "external_prior_compliance_work_not_recognized",
        F,
        "The customer already did equivalent scoping work for a different framework outside "
        "the platform and wants it to count toward a new framework - it doesn't automatically.",
        (("Can we get credit toward SOC 2 for work we already did for ISO 27001 outside your platform?", F, None),),
    ),
    Cause(
        "readiness_score_overstates_actual_coverage",
        F,
        "The readiness score reflects control status, not auditor judgment - the auditor can "
        "still find gaps in controls the platform shows as 100% ready.",
        (("Our framework says we're 100% ready but our auditor found gaps in fieldwork", F, None),),
    ),
    Cause(
        "no_framework_preview_before_commit",
        F,
        "There's no way to preview a framework's control set before formally adding it to the "
        "account.",
        (("Is there a way to preview what our GDPR control set would look like before adding the framework?", F, None),),
    ),
    Cause(
        "framework_removal_leaves_orphaned_evidence",
        F,
        "Removing a framework unlinks its controls but leaves evidence that was only ever "
        "attached to those controls with nowhere to go.",
        (("We removed a framework and now some evidence has no controls to attach to", F, None),),
    ),
    Cause(
        "no_way_to_compare_two_framework_versions",
        F,
        "There's no diff or comparison view between the old and new version of a framework "
        "standard after a migration.",
        (("Is there a way to see exactly what changed between the old and new version of our framework?", F, None),),
    ),
    Cause(
        "scoping_wizard_multi_entity_unsupported",
        F,
        "The framework scoping wizard assumes a single legal entity - it has no concept of "
        "multiple subsidiaries needing separate or combined scoping.",
        (("Our scoping only lets us pick one legal entity, but we have three subsidiaries in this framework", F, None),),
    ),
    Cause(
        "framework_certificate_legal_entity_name_mismatch",
        F,
        "The legal entity name on the account doesn't match what's printed on the issued "
        "framework certificate, and there's no self-serve way to correct it.",
        (
            ("The company name on our framework's certificate doesn't match our legal entity name and I can't find where to fix it", F, None),
            ("Our invoices show the wrong company name and I don't know where to update it", B, None),
        ),
    ),
    Cause(
        "single_owner_per_control_limitation",
        C,
        "A control can only have one assigned owner - there's no way to represent shared "
        "responsibility across two people.",
        (("Can a control have two owners for shared responsibilities?", C, None),),
    ),
    Cause(
        "control_test_result_stale_between_runs",
        C,
        "An automated control's status only updates on its next scheduled test run, so a "
        "process that broke after the last passing run still shows as Passing.",
        (("A control test passed last night but the underlying process actually failed this morning", C, None),),
    ),
    Cause(
        "no_staleness_based_auto_fail_rule",
        C,
        "There's no setting to auto-fail a control whose automated test hasn't run recently, "
        "even if its last recorded result was a pass.",
        (("Can I set a control to auto-fail if its test hasn't run in 30 days, even with a passing last result?", C, None),),
    ),
    Cause(
        "control_bulk_edit_no_audit_trail",
        C,
        "A bulk status change touched dozens of controls at once and there's no per-control "
        "record of who made the change or an easy way to undo it in bulk.",
        (
            ("Someone accidentally marked 20 controls complete and I can't see who did it or undo it in bulk", C, None),
            ("I can't tell who changed a bunch of our controls' status", AM, None),
        ),
    ),
    Cause(
        "control_note_field_has_no_history",
        C,
        "The notes field on a control only stores the current text - earlier versions aren't "
        "kept, so an edit silently overwrites what a teammate wrote.",
        (("The notes field on a control just shows the latest text - I can't see what a teammate wrote before they edited it", C, None),),
    ),
    Cause(
        "no_control_dependency_linking",
        C,
        "Controls are independent records - there's no way to mark one as blocked by or "
        "dependent on another.",
        (("Can I mark one control as blocked by another so they show as related?", C, None),),
    ),
    Cause(
        "control_evidence_requirement_unclear_for_custom_controls",
        C,
        "Custom, self-authored controls have no guidance on what evidence would actually "
        "satisfy them, unlike template controls which specify this.",
        (("For a control we wrote ourselves, there's nothing telling us what kind of evidence would satisfy it", C, None),),
    ),
    Cause(
        "bulk_control_status_change_not_supported",
        C,
        "Control status can only be changed one control at a time - there's no multi-select "
        "bulk action.",
        (("Is there a way to update the status on multiple controls at once instead of one at a time?", C, None),),
    ),
    Cause(
        "control_reassignment_no_notification",
        C,
        "Reassigning a control's owner doesn't trigger any notification to the new owner.",
        (("I reassigned a control to a teammate and they had no idea until I mentioned it - is there a notification for that?", C, None),),
    ),
    Cause(
        "cross_framework_control_edit_scope_limited",
        C,
        "Editing a control that's shared across two frameworks only updates the copy under "
        "the framework you were viewing when you made the edit.",
        (("I edited a shared control's description but it only changed for one of our two frameworks", C, None),),
    ),
    Cause(
        "no_bulk_evidence_upload_capability",
        E,
        "Evidence has to be uploaded one file at a time, per control - there's no bulk upload "
        "path for attaching many files across many controls at once.",
        (("Can I bulk-upload evidence for 50 controls at once?", E, None),),
    ),
    Cause(
        "no_evidence_recovery_after_deletion",
        E,
        "Deleted evidence isn't recoverable - there's no trash or undo for evidence removal.",
        (("Evidence I deleted by mistake seems permanently gone", E, None),),
    ),
    Cause(
        "evidence_reuse_across_annual_cycles_unclear",
        E,
        "Evidence collected in one cycle doesn't automatically roll forward or expire in a "
        "way that's obvious to a customer planning next year's collection.",
        (("Does evidence collected for a control automatically count toward next year's cycle, or do we redo it all?", E, None),),
    ),
    Cause(
        "evidence_preview_fails_for_large_files",
        E,
        "Files above a certain size don't render in the in-browser preview and have to be "
        "downloaded to view.",
        (("Evidence files over a certain size won't preview in the browser, I have to download them every time", E, None),),
    ),
    Cause(
        "evidence_owner_field_not_editable",
        E,
        "The uploader recorded against a piece of evidence is fixed at upload time and can't "
        "be reassigned afterward, even when attribution should change.",
        (
            ("I uploaded evidence under the wrong person's name and can't seem to change who it's attributed to", E, None),
            ("Evidence is attributed to someone who's no longer on our team and I want it re-attributed", AM, None),
        ),
    ),
    Cause(
        "no_pre_auditor_evidence_review_status",
        E,
        "There's no internal-only review status for evidence - it's either uploaded or not, "
        "with no way to mark it as internally vetted before an auditor sees it.",
        (("Is there a status I can set on evidence to show it's been reviewed internally before the auditor sees it?", E, None),),
    ),
    Cause(
        "evidence_search_no_partial_filename_match",
        E,
        "The evidence library's search only matches complete filenames, not substrings.",
        (("Searching the evidence library for part of a filename doesn't find anything unless I type the whole thing", E, None),),
    ),
    Cause(
        "on_prem_identity_provider_unsupported",
        I,
        "The platform's integrations target cloud identity providers - there's no supported "
        "path for connecting an on-premises directory.",
        (("Do you support connecting our on-prem Active Directory, not just cloud identity providers?", I, None),),
    ),
    Cause(
        "duplicate_sync_run_race_condition",
        I,
        "An integration's scheduled sync and a manually triggered sync overlapped, and "
        "evidence from both runs was recorded, doubling the count.",
        (("Our integration sync ran twice in the same hour and doubled our evidence count", I, None),),
    ),
    Cause(
        "no_integration_disconnect_webhook",
        I,
        "There's no outbound notification when an integration disconnects - customers only "
        "find out by checking the dashboard.",
        (("Can we get a webhook that fires whenever an integration disconnects?", I, None),),
    ),
    Cause(
        "integration_sync_history_not_visible",
        I,
        "There's no log of what a specific sync actually pulled in - only the current "
        "resulting evidence, not a history of runs.",
        (("Is there a log anywhere showing what an integration actually pulled in on its last sync?", I, None),),
    ),
    Cause(
        "cant_scope_integration_to_resource_subset",
        I,
        "An integration connects to the whole account or project - there's no way to limit it "
        "to a subset of resources.",
        (("Can we connect only part of our AWS account instead of the whole thing?", I, None),),
    ),
    Cause(
        "integration_reconnect_loses_historical_mapping",
        I,
        "Reconnecting a disconnected integration doesn't restore prior evidence-to-control "
        "mappings - they have to be redone by hand.",
        (("After reconnecting our integration, evidence that used to map automatically now needs to be re-linked by hand", I, None),),
    ),
    Cause(
        "no_sandbox_mode_for_new_integration",
        I,
        "There's no test or preview mode for connecting an integration - authorizing it "
        "starts real evidence collection immediately.",
        (("Is there a way to test-connect an integration without it immediately starting to collect real evidence?", I, None),),
    ),
    Cause(
        "no_multilingual_policy_support",
        P,
        "Policy templates and custom policies are English-only - there's no built-in "
        "translation or localization.",
        (("Can policies be translated into other languages for our EU staff?", P, None),),
    ),
    Cause(
        "acknowledgment_not_visible_to_managers",
        P,
        "Policy acknowledgment status is visible on the policy's own page, but there's no "
        "manager-facing view scoped to their direct reports.",
        (("An employee acknowledged a policy but their manager can't see that confirmation anywhere", P, None),),
    ),
    Cause(
        "no_two_step_policy_acknowledgment_workflow",
        P,
        "Policy acknowledgment is a single step - there's no way to require a manager's "
        "sign-off in addition to the employee's own acknowledgment.",
        (("Can we require a manager's approval in addition to the employee's acknowledgment for high-risk policies?", P, None),),
    ),
    Cause(
        "policy_template_edits_not_retroactive",
        P,
        "Updating a policy template only affects new policies created from it - already-"
        "published policies don't pick up the change.",
        (("We updated a policy template's wording but our already-published policy didn't pick up the change", P, None),),
    ),
    Cause(
        "no_scheduled_future_policy_publish",
        P,
        "Policies publish immediately when approved - there's no way to schedule a publish "
        "date in the future.",
        (("Can I schedule a policy to publish automatically on a specific future date instead of publishing it manually?", P, None),),
    ),
    Cause(
        "policy_attachment_size_limit_too_small",
        P,
        "Supporting documents attached to a policy are capped at a size limit that's too "
        "small for some customers' files.",
        (
            ("I'm trying to attach a large supporting document to a policy and it's being rejected for size", P, None),
            ("A file I'm trying to attach keeps getting rejected for being too large", E, None),
        ),
    ),
    Cause(
        "no_custom_policy_review_reminder",
        P,
        "The only review reminder is the standard annual one - there's no way to set a "
        "custom cadence for a specific policy.",
        (("Is there a way to set a custom review reminder for a policy that isn't the standard annual one?", P, None),),
    ),
    Cause(
        "no_department_scoped_policy_assignment",
        P,
        "Policies apply account-wide - there's no way to assign different sets of policies "
        "to different departments.",
        (("Can we assign different sets of policies to different departments instead of everyone getting everything?", P, None),),
    ),
    Cause(
        "no_custom_role_between_contributor_and_admin",
        AM,
        "Roles are limited to Admin, Contributor, and Viewer - there's no way to create a "
        "narrower custom role, such as one with Contributor access but no billing visibility.",
        (("Can we have a role between Contributor and Admin with narrower billing access?", AM, None),),
    ),
    Cause(
        "shared_login_credentials_no_individual_attribution",
        AM,
        "Two people are using the same login instead of separate accounts, so actions in the "
        "audit log can't be attributed to a specific individual.",
        (("Two people on our team seem to share one login and I can't tell who did what", AM, None),),
    ),
    Cause(
        "access_review_not_scoped_per_framework",
        AM,
        "Access reviews cover the whole account at once - there's no way to scope one to just "
        "the users and systems relevant to a single framework.",
        (("Can access reviews be scoped to just one framework instead of the whole account?", AM, None),),
    ),
    Cause(
        "no_time_bound_access_grants",
        AM,
        "Role assignments are permanent until manually changed - there's no way to grant "
        "access that automatically expires after a set period.",
        (("Can I grant someone Contributor access that automatically expires after 30 days?", AM, None),),
    ),
    Cause(
        "audit_log_lacks_login_ip_address",
        AM,
        "The audit log records login events but not the originating IP address.",
        (("Does the audit log record where a login came from, like an IP address?", AM, None),),
    ),
    Cause(
        "no_bulk_user_invite",
        AM,
        "Users are invited one at a time - there's no bulk or CSV-based invite flow.",
        (("Can I invite 15 people at once instead of one at a time?", AM, None),),
    ),
    Cause(
        "viewer_role_not_scoped_to_single_framework",
        AM,
        "The Viewer role grants read access to the whole account - there's no way to scope "
        "it to just one framework, which matters for external viewers like auditors.",
        (
            ("Can we give our auditor Viewer access to just one framework instead of the whole account?", AM, None),
            ("Can our auditor's access be limited to just the framework they're auditing?", AU, None),
        ),
    ),
    Cause(
        "concurrent_audits_same_framework_unsupported_workflow",
        AU,
        "The platform's audit workflow assumes one active audit per framework at a time - "
        "running two audits with two firms in the same cycle isn't a supported flow.",
        (("Can we run two separate SOC 2 audits with two different audit firms in the same year?", AU, None),),
    ),
    Cause(
        "no_third_party_audit_tool_integration",
        AU,
        "There's no native integration for an auditor's own audit-management software - "
        "everything happens inside the platform's own auditor view.",
        (("Our auditor wants a native integration with their own audit-management software", AU, None),),
    ),
    Cause(
        "no_in_platform_evidence_commenting_for_auditors",
        AU,
        "Auditors can view and download evidence but can't leave comments on a specific item "
        "directly - questions have to go through email instead.",
        (("Can our auditor leave comments directly on a piece of evidence instead of emailing separately?", AU, None),),
    ),
    Cause(
        "auditor_access_not_revoked_after_engagement",
        AU,
        "Auditor access doesn't automatically expire or get revoked when the engagement "
        "wraps up - it has to be removed manually.",
        (("Our audit wrapped up months ago and the auditor we invited still has access - is that supposed to happen?", AU, None),),
    ),
    Cause(
        "no_auditor_review_progress_tracking",
        AU,
        "There's no way to see which controls the auditor has actually opened or reviewed "
        "versus which are still untouched.",
        (("Is there a way to tell which controls our auditor has actually looked at versus what's still pending?", AU, None),),
    ),
    Cause(
        "certificate_missing_scope_statement",
        AU,
        "The issued certificate doesn't list the specific systems or boundaries that were in "
        "scope for the audit.",
        (("The certificate we got doesn't list which systems were actually in scope - our customers are asking for that", AU, None),),
    ),
    Cause(
        "surveillance_audit_evidence_reuse_unclear",
        AU,
        "For a surveillance audit, evidence that hasn't changed since the prior year still "
        "needs to be explicitly re-attached - there's no automatic carry-forward.",
        (
            ("For our surveillance audit, do we have to re-upload evidence that hasn't changed since last year?", AU, None),
            ("Does evidence I uploaded last year still count, or do I need to re-upload it?", E, None),
        ),
    ),
    Cause(
        "no_formal_auditor_evidence_request_flow",
        AU,
        "Auditors can view what's shared with them but can't formally request a specific "
        "piece of evidence in-platform - that still happens over email.",
        (("Our auditor wants to formally request a specific piece of evidence through the platform instead of emailing us", AU, None),),
    ),
    Cause(
        "no_custom_billing_cycle_alignment",
        B,
        "Billing cycles are anchored to the signup date - there's no option to align them to "
        "a customer's fiscal year instead.",
        (("Can we get a custom invoice schedule that matches our fiscal year instead of our signup date?", B, None),),
    ),
    Cause(
        "no_multi_currency_billing_support",
        B,
        "All billing is in USD - there's no option to receive invoices in another currency.",
        (("We were charged in USD but our finance team needs invoices in EUR", B, None),),
    ),
    Cause(
        "seat_proration_policy_unclear",
        B,
        "Seats added mid-cycle are prorated, but the proration isn't explained anywhere a "
        "customer would see it before adding users.",
        (("If we add 10 users mid-month, are we charged a prorated amount or the full seat price?", B, None),),
    ),
    Cause(
        "cant_downgrade_below_minimum_framework_count",
        B,
        "The plan the customer is on has a two-framework minimum that can't be reduced "
        "without changing plans, even if they only need one framework now.",
        (("We only need one framework now but the plan won't let us go below two - is that a hard limit?", B, None),),
    ),
    Cause(
        "billing_admin_departed_no_successor",
        B,
        "The account's sole billing Admin left the company, and payment method changes "
        "require Admin access with no built-in transfer or recovery path.",
        (("Our billing admin left the company and nobody else can update the payment method - what do we do?", B, None),),
    ),
    Cause(
        "no_per_framework_invoice_breakdown",
        B,
        "Invoices show a single total - there's no line-item breakdown by framework for "
        "customers who need to allocate cost internally.",
        (
            ("Our invoice just shows one total - can we get it broken down by framework so we can allocate costs internally?", B, None),
            ("Can I see how much each of our frameworks is costing us separately?", F, None),
        ),
    ),
    Cause(
        "trial_removal_deadline_charge_bug",
        B,
        "A framework removed just before the 14-day trial window closed was still billed, "
        "suggesting the removal and the billing check raced against each other.",
        (("We removed a framework before the 14-day trial ended but got charged for it anyway", B, None),),
    ),
]

ALL_CAUSES: list[Cause] = DOCUMENTED_CAUSES + INVENTED_CAUSES
CAUSES_BY_ID: dict[str, Cause] = {cause.id: cause for cause in ALL_CAUSES}


@dataclass(frozen=True)
class Scenario:
    id: str
    split: str
    symptom: str
    cause: str
    primary_category: Category
    documented: bool
    kb_file: str | None
    audit_timing: AuditTiming
    workaround: bool
    tone: Tone
    presented_as: Intent
    difficulty: Difficulty
    secondary_category: Category | None = None  # only for multi_topic


def interleave(a: list[Cause], b: list[Cause]) -> list[Cause]:
    """Merge two lists so every prefix reflects the overall len(a):len(b) ratio - lets a
    positional split (front slice / rest) preserve each list's share instead of draining
    one list before touching the other."""
    result: list[Cause] = []
    ai = bi = 0
    while ai < len(a) or bi < len(b):
        a_share = ai / len(a) if a else 1.0
        b_share = bi / len(b) if b else 1.0
        if bi >= len(b) or (ai < len(a) and a_share <= b_share):
            result.append(a[ai])
            ai += 1
        else:
            result.append(b[bi])
            bi += 1
    return result


def split_causes(category: Category) -> tuple[list[Cause], list[Cause]]:
    """Partition a category's causes into disjoint dev/test pools (~30/70, matching the
    overall corpus split), so no cause - and therefore no symptom - crosses splits.

    Documented and invented causes are interleaved before slicing, so both pools carry
    the category's actual documented:invented ratio instead of dev skewing toward
    whichever group happens to sort first.
    """
    pool = [c for c in ALL_CAUSES if c.true_category == category]
    documented = [c for c in pool if c.symptoms[0][2] is not None]
    invented = [c for c in pool if c.symptoms[0][2] is None]
    ordered = interleave(documented, invented)
    split_point = math.ceil(len(ordered) * 0.3)
    return ordered[:split_point], ordered[split_point:]


def build_scenarios() -> list[Scenario]:
    categories = list(Category)
    hard_types = [
        Difficulty.MULTI_TOPIC,
        Difficulty.MISLEADING_SYMPTOM,
        Difficulty.WORKING_AS_DESIGNED,
        Difficulty.MISSING_DECIDING_FACT,
    ]
    scenarios: list[Scenario] = []

    for category in categories:
        dev_pool, test_pool = split_causes(category)
        for split, pool, counts in (("dev", dev_pool, DEV_COUNTS), ("test", test_pool, TEST_COUNTS)):
            multi_symptom = [c for c in pool if len(c.symptoms) >= 2]
            for i in range(counts[category]):
                cause = pool[i % len(pool)]

                if i % 4 == 3:
                    difficulty = hard_types[(i // 4) % len(hard_types)]
                else:
                    difficulty = Difficulty.PLAIN
                if difficulty == Difficulty.MISLEADING_SYMPTOM:
                    if multi_symptom:
                        # Route to a cause that actually has a cross-category symptom,
                        # rather than leaving it to whatever pool[i % len(pool)] lands on.
                        cause = multi_symptom[i % len(multi_symptom)]
                    else:
                        # No cross-category symptom exists anywhere in this pool - fall
                        # back rather than fabricate a pairing that isn't grounded in anything.
                        difficulty = Difficulty.WORKING_AS_DESIGNED

                symptom_text, _, kb_file = (
                    cause.symptoms[1] if difficulty == Difficulty.MISLEADING_SYMPTOM else cause.symptoms[0]
                )

                audit_timing = list(AuditTiming)[i % len(AuditTiming)]
                if difficulty == Difficulty.MISSING_DECIDING_FACT:
                    audit_timing = AuditTiming.NOT_MENTIONED

                secondary_category = None
                if difficulty == Difficulty.MULTI_TOPIC:
                    idx = categories.index(category)
                    offset = 1 + (i // 4) % (len(categories) - 1)
                    secondary_category = categories[(idx + offset) % len(categories)]

                # billing_request only makes sense as the intent for a billing ticket;
                # everywhere else, rotate through the remaining four.
                intent_options = (
                    list(Intent) if category == Category.ACCOUNT_BILLING
                    else [x for x in Intent if x != Intent.BILLING_REQUEST]
                )
                presented_as = intent_options[i % len(intent_options)]
                if difficulty == Difficulty.WORKING_AS_DESIGNED:
                    # The prompt tells the writer the customer is reporting a bug; a
                    # rotated presented_as of question/feature_request would contradict it.
                    presented_as = Intent.BUG

                scenarios.append(
                    Scenario(
                        id=f"{split}-{category.value}-{i:03d}",
                        split=split,
                        symptom=symptom_text,
                        cause=cause.id,
                        primary_category=category,
                        documented=kb_file is not None,
                        kb_file=kb_file,
                        audit_timing=audit_timing,
                        workaround=bool(i % 2),
                        tone=list(Tone)[i % len(Tone)],
                        presented_as=presented_as,
                        difficulty=difficulty,
                        secondary_category=secondary_category,
                    )
                )
    return scenarios


SYSTEM_PROMPT = """You write realistic support tickets for a compliance automation platform \
(SOC 2 / ISO 27001 / GDPR compliance tooling). You will be given a root cause and a set of \
situational details. Write the ticket a customer experiencing that situation would actually \
send in.

Write in the customer's voice, not a description of the situation:
- The customer does not know the internal root cause. Never restate it directly - describe \
only what they observed, using the symptom description you're given.
- Someone who believes something is broken writes a bug report even when the product behaved \
exactly as designed. Keep their framing and their mistaken assumptions if the situation calls \
for it - do not have them figure out or hint at the real explanation.
- Vary how much product vocabulary the customer uses and how much context they leave out, the \
way real, differently-technical people write tickets.
- Never mention or hint at internal generation concepts (category, priority, intent, \
difficulty, "scenario", "cause", audit timing as a labeled field, etc.) - those are not things \
a real customer would write.

Submit the ticket with the submit_ticket tool: a subject line and a body, exactly as the \
customer would type them."""


def render_prompt(scenario: Scenario) -> str:
    cause = CAUSES_BY_ID[scenario.cause]
    lines = [
        f"Root cause (internal, do not reveal): {cause.description}",
        f"How the customer would describe what they're seeing: {scenario.symptom}",
        "",
        f"How the customer is framing this request: {scenario.presented_as.value.replace('_', ' ')}",
        f"Customer's tone: {scenario.tone.value.replace('_', ' ')}",
    ]

    if scenario.tone == Tone.FRUSTRATED:
        lines.append("They're annoyed - this has cost them time or made them look bad.")
    elif scenario.tone == Tone.URGENT_STATED:
        lines.append("They explicitly say this is urgent or that they need a fast response.")
    elif scenario.tone == Tone.RELATIONSHIP_AT_RISK:
        lines.append(
            "They imply the relationship is at risk over this - evaluating alternatives, "
            "considering cancelling, or escalating to their own leadership."
        )

    if scenario.workaround:
        lines.append(
            "A manual workaround exists (e.g. doing the step by hand) and the customer could "
            "use it, though it's slower."
        )
    else:
        lines.append("No workaround exists - the customer is blocked until this is fixed.")

    if scenario.audit_timing == AuditTiming.IMMINENT:
        lines.append(
            "An audit is imminent or already underway, and this is holding it up - the "
            "customer should convey that urgency without using the word 'imminent'."
        )
    elif scenario.audit_timing == AuditTiming.SCHEDULED:
        lines.append(
            "An audit is scheduled for some time in the future, mentioned in passing, not "
            "framed as an immediate deadline."
        )
    elif scenario.audit_timing == AuditTiming.NONE:
        lines.append("No audit is relevant to this request at all.")
    else:
        lines.append(
            "Do not mention any audit, deadline, or timeline whatsoever - the customer just "
            "describes the problem."
        )

    if scenario.difficulty == Difficulty.MULTI_TOPIC and scenario.secondary_category:
        blurb = CATEGORY_BLURB[scenario.secondary_category]
        lines.append(
            f"This ticket should also raise a second, unrelated concern about {blurb}. Fold "
            "it into the same email as a customer would when they have two things on their "
            "mind, rather than writing two clearly separated topics."
        )
    elif scenario.difficulty == Difficulty.MISLEADING_SYMPTOM:
        lines.append(
            "Write this from the angle the symptom description above suggests - it reads like "
            "a different part of the product than what's actually going on. Do not have the "
            "customer correctly guess the real cause or area."
        )
    elif scenario.difficulty == Difficulty.WORKING_AS_DESIGNED:
        lines.append(
            "The customer believes this is a bug and is reporting it as one, even though the "
            "root cause above shows the product is behaving correctly. Write it fully from "
            "their mistaken point of view."
        )

    return "\n".join(lines)


SUBMIT_TICKET_TOOL = {
    "name": "submit_ticket",
    "description": "Submit the generated support ticket text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "The ticket's subject line, as the customer would write it.",
            },
            "body": {
                "type": "string",
                "description": "The ticket's body text, as the customer would write it.",
            },
        },
        "required": ["subject", "body"],
        "additionalProperties": False,
    },
    "strict": True,
}


def generate_ticket(client: anthropic.Anthropic, scenario: Scenario) -> Ticket:
    # max_tokens caps thinking + output together on Sonnet 5 (thinking is on by default);
    # 1024 was tight enough that a long body could truncate before any tool_use block.
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        tools=[SUBMIT_TICKET_TOOL],
        tool_choice={"type": "tool", "name": "submit_ticket"},
        messages=[{"role": "user", "content": render_prompt(scenario)}],
    )
    if response.stop_reason != "tool_use":
        raise RuntimeError(f"stop_reason={response.stop_reason!r}, no tool call to read")
    block = next(b for b in response.content if b.type == "tool_use")
    return Ticket(id=scenario.id, subject=block.input["subject"], body=block.input["body"])


def load_existing_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open() as f:
        return {json.loads(line)["id"] for line in f if line.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=None, help="Generate at most N tickets (for testing)."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print scenario counts without calling the API."
    )
    args = parser.parse_args()

    scenarios = build_scenarios()
    dev_count = sum(1 for s in scenarios if s.split == "dev")
    test_count = sum(1 for s in scenarios if s.split == "test")
    print(f"Built {len(scenarios)} scenarios ({dev_count} dev, {test_count} test).")

    if args.dry_run:
        for split in ("dev", "test"):
            split_scenarios = [s for s in scenarios if s.split == split]
            per_cause = Counter(s.cause for s in split_scenarios)
            documented_n = sum(1 for s in split_scenarios if s.documented)
            reuse = sorted(per_cause.values())
            print(
                f"\n{split}: {len(split_scenarios)} tickets, {len(per_cause)} distinct causes, "
                f"{documented_n}/{len(split_scenarios)} documented "
                f"({documented_n / len(split_scenarios):.0%})"
            )
            print(
                f"  tickets per cause: min={reuse[0]}, max={reuse[-1]}, "
                f"avg={sum(reuse) / len(reuse):.1f}"
            )
        return

    DEV_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing_ids = load_existing_ids(DEV_PATH) | load_existing_ids(TEST_PATH)
    pending = [s for s in scenarios if s.id not in existing_ids]
    if args.limit is not None:
        pending = pending[: args.limit]
    print(f"{len(existing_ids)} tickets already generated; {len(pending)} to go.")

    load_dotenv()
    client = anthropic.Anthropic()

    with (
        DEV_PATH.open("a") as dev_f,
        TEST_PATH.open("a") as test_f,
        LOG_PATH.open("a") as log_f,
    ):
        for i, scenario in enumerate(pending, 1):
            try:
                ticket = generate_ticket(client, scenario)
            except Exception as exc:
                print(f"[{i}/{len(pending)}] {scenario.id}: FAILED ({exc}) - will retry on next run")
                continue
            out = dev_f if scenario.split == "dev" else test_f
            out.write(json.dumps(asdict(ticket)) + "\n")
            out.flush()
            log_f.write(json.dumps(asdict(scenario)) + "\n")
            log_f.flush()
            print(f"[{i}/{len(pending)}] {scenario.id}: {ticket.subject}")


if __name__ == "__main__":
    main()
