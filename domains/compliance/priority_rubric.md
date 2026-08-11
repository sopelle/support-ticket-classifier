# Priority rubric

Priority measures the response commitment a ticket deserves. It cuts across every
category and intent: a `frameworks` ticket and an `evidence` ticket can both be high
priority, for the same underlying reasons.

`high`, `medium` and `low` carry no inherent meaning, so this file defines them. It is the single source for both the classifier prompt and hand-labeling: if the two ever disagree, the evaluation measures the gap between two definitions rather than the
model's performance.

## Quick reference

A navigation aid, not the rubric itself — every row below drops the exceptions and
edge cases that decide close calls. Read the matching section for the full criterion
before labeling.

| Level | Criterion |
| --- | --- |
| High | Blocks an imminent or in-progress audit |
| High | Confirmed or suspected security exposure |
| High | Platform-wide outage with no workaround |
| High | Irrecoverable data loss |
| Medium | Blocks framework progress with no auditor waiting |
| Medium | Access or permission gap with no sign of misuse |
| Medium | Broken control or integration with a workaround |
| Medium | Billing issue that risks a future interruption |
| Medium | Bug blocking one user/team with no self-service fix |
| Low | How-to questions and clarifications |
| Low | Working as designed |
| Low | Obvious self-service fix |
| Low | Feature requests |
| Low | Cosmetic or minor bugs |
| Low | Billing questions/discrepancies with no service impact |
| Low | Complaints or feedback with nothing actively blocked |

Apply it in three steps:

1. Resolve whatever the ticket leaves unstated, using the defaults below.
2. Scan High, then Medium, then Low. The first bullet that matches is the base level.
3. Apply the stated-urgency adjustment.

## Deciding when the ticket is vague

Most tickets leave the deciding fact unsaid. Resolve these the same way every time
rather than case by case:

- **Audit timing is not mentioned.** Assume no audit is imminent. Do not promote to High on a deadline the requester never claimed. An audit mentioned without a date is scheduled, not imminent.
- **An auditor is involved but fieldwork status is unstated.** Assume fieldwork has not started. An auditor who cannot log in before the engagement begins is a setup problem, not a blocked audit.
- **A workaround exists but is slow or manual.** It still counts as a workaround, unless the requester states a deadline the manual path cannot meet.

## High

- **Blocks an imminent or in-progress audit.** An auditor is waiting on evidence, a
  control status, or an answer that stalls fieldwork; or a control in scope for an
  audit under way or dated within weeks is Failing or missing evidence. An auditor
  blocked by an access problem the customer can fix themselves is not High.
- **Confirmed or suspected security exposure.** Unauthorized access, leaked credentials, or evidence and policy data visible to the wrong audience. A
  misconfiguration that *could* permit exposure but shows no sign of it is not High —
  see Medium.
- **Platform-wide outage with no workaround.** No one on the team can log in or
  complete a core workflow, and no manual alternative exists.
- **Irrecoverable data loss.** Evidence, policies, or control history destroyed with no
  restore path and no way to re-collect before a deadline. If version history or
  re-collection can recover it, it is not irrecoverable.

## Medium

- **Blocks framework progress with no auditor waiting.** Readiness work is stalled — a
  broken integration stops evidence syncing — but no audit is at risk yet.
- **Access or permission gap with no sign of misuse.** Someone retains access they
  should have lost, or a scope is wider than intended, but nothing indicates it was
  used.
- **Broken control or integration with a workaround.** The automated path is down;
  evidence can still be collected manually.
- **Billing issue that risks a future interruption.** A failed payment or expiring card
  that has not yet caused a lockout.
- **A bug that blocks one user's or one team's work with no self-service fix.** Not
  org-wide, not on an audit path, but the person cannot proceed on their own.

## Low

- **How-to questions and clarifications.** No blocker, just a request for information.
- **Working as designed.** The product behaved correctly and the requester expected
  something else: an unsupported file format, a permission the account genuinely lacks,
  an expiry calculated from a date they entered themselves. Frustration does not make
  it a defect.
- **Anything with an obvious self-service fix**, such as resending an invite or
  re-uploading a file.
- **Feature requests.**
- **Cosmetic or minor bugs.** UI glitches and wording issues that do not stop work.
- **Billing questions and discrepancies with no service impact.** Invoice lookups, seat
  counts, plan questions, and charges the requester disputes but which match the
  documented billing rules.
- **Complaints or feedback with nothing actively blocked.**

## Stated urgency and frustration

A requester who marks an issue urgent, or who is clearly frustrated, is treated as
urgent. Responsiveness is the remedy for frustration: a slow reply to an annoyed
customer costs more than the ticket itself.

- **Stated urgency or clear frustration raises the base level by one.** A cosmetic bug
  flagged urgent becomes Medium, not High — the queue still has to be sortable.
- **An explicit statement putting the relationship at risk sets High on its own**, whatever
  the underlying blocker: evaluating alternatives, threatening cancellation, escalating
  to leadership.
- **It never lowers a level.** A technically blocking ticket stays High whatever the tone.
- **Say so in the reasoning when the level was raised this way**, so the agent knows to
  answer fast and reassure without necessarily pulling in engineering effort.

## Notes for labeling

- Judge the underlying blocker first, then apply the stated-urgency adjustment. Tone
  raises priority but never sets it alone.
- If nothing in High or Medium applies and no adjustment fires, it is Low. Do not
  invent urgency the ticket does not contain.
- When a case feels borderline, note which bullet you matched. Those are the cases to
  revisit when measuring labeling agreement.
