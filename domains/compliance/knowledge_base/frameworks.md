# Frameworks

## FAQ

### What frameworks does the platform support?

SOC 2 (Type I and Type II), ISO 27001, and GDPR are supported out of the box, each with a pre-built control set mapped to the framework's official requirements. You can run multiple frameworks in the same account.

### What's the difference between SOC 2 Type I and Type II?

A Type I report assesses whether your controls are designed correctly as of a single point in time. A Type II report assesses whether those controls operated effectively over an observation window, typically 3-12 months. Most customers start with Type I and move to Type II the following cycle.

### How do I scope a framework to my systems?

During setup you select which production systems, vendors, and data types are in scope. Scoping determines which controls apply and which integrations are required to collect evidence for them. You can re-scope later, but narrowing scope after an audit has started requires auditor sign-off.

### Can I run two frameworks at once?

Yes. When you add a second framework, the platform cross-maps controls that satisfy both frameworks so you don't collect duplicate evidence. Look for the "shared control" badge on the controls list.

### How long does it take to get certified?

Readiness typically takes 4-8 weeks depending on how many controls need net-new evidence or process changes. The audit itself (fieldwork through report issuance) is separate and depends on your auditor's schedule: see the Audits FAQ.

### What is a readiness assessment?

A readiness assessment scans your current control status and evidence coverage against the framework's requirements and flags gaps before you formally start an audit. Run it any time from the framework's overview page.

### Can I remove a framework I no longer need?

Yes, from Framework Settings. Removing a framework unlinks its framework-specific controls but keeps any evidence that's shared with another active framework.

## Troubleshooting

### Readiness score is stuck at 0% even though controls are marked complete

The readiness score recalculates on a nightly job, not in real time. If it's been more than 24 hours, check whether the completed controls are actually mapped to the framework in question: controls added manually aren't auto-mapped and need to be linked from the control's detail page.

### The framework switched to a different version of the standard

Standards bodies periodically release new versions (e.g. ISO 27001:2013 vs. 2022). The platform migrates accounts to the current version automatically at renewal. If you need to stay on the prior version for an in-progress audit, contact support before your renewal date to freeze it.

### Shared control mapping isn't showing between two active frameworks

Cross-mapping only applies to controls with identical evidence requirements. If a control looks like it should be shared but isn't, it's most often because the two frameworks scope different systems for that control: check the scoping settings for each framework.

### Scope changes aren't reflected in the control list

Control lists are regenerated when scope is saved, not while editing. If controls still look stale after saving, do a hard refresh; if that doesn't fix it, the scope change may be queued behind a pending audit lock.
