# Controls

## FAQ

### What is a control?

A control is a specific safeguard (a process, policy, or technical setting) that maps to one or more framework requirements. Each control has a status, an owner, evidence attached to it, and (for automated controls) a test that runs on a schedule.

### What are the possible statuses for a control?

Not Started, In Progress, Needs Evidence, Passing, and Failing. A control moves to Passing once it has current, valid evidence attached (and, for automated controls, its last test succeeded).

### Who should be the control owner?

Whoever is accountable for the underlying process, not necessarily whoever uploads the evidence. Auditors will contact the listed owner directly with follow-up questions during fieldwork.

### How often are controls tested?

Automated controls run their test daily. Manual controls are tested on the cadence you set (commonly quarterly or annually) and prompt the owner when a test is due.

### What's the difference between automated and manual controls?

Automated controls pull evidence directly from a connected integration and evaluate it against a rule (e.g. "MFA is enabled for all users"). Manual controls require a human to upload evidence or attest that the control is in place.

### Can I mark a control as not applicable?

Yes, if it's genuinely outside your scope (e.g. a control about physical data centers when you're fully cloud-hosted). Marking a control not applicable requires a written justification, which auditors will review.

### How do I map a control to multiple frameworks?

Open the control's detail page and add the additional framework under "Mapped frameworks." Evidence uploaded once then satisfies all mapped frameworks, provided the requirements are equivalent.

### What happens if a control fails its automated test?

The control status changes to Failing and the owner is notified. The control reverts to Passing automatically once the underlying issue is fixed and the test re-runs, no manual re-approval needed.

## Troubleshooting

### A control shows "Not Started" even though evidence is attached

This usually means the evidence was uploaded to the wrong control, or is still in "Processing" status: see the Evidence FAQ. Confirm the evidence appears in the control's evidence list, not just in the general evidence library.

### An automated control keeps failing with a stale integration error

The control is likely reading from an integration that's disconnected or whose credentials expired. Check the integration's status on the Integrations page: reconnecting it triggers an immediate re-test.

### Control owner assignment isn't saving

This is usually caused by assigning a user who doesn't have a role with control-management permissions. Confirm the intended owner has at least the "Contributor" role before assigning them.

### Duplicate controls appeared after adding a second framework

When two frameworks have similar but not identical requirements, the platform creates separate controls rather than merging them automatically to avoid misrepresenting coverage. You can manually mark them as related from either control's detail page.
