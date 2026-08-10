# Access Management

## FAQ

### What user roles exist?

Admin, Contributor, and Viewer. Admins manage billing, users, and integrations; Contributors can edit controls, evidence, and policies; Viewers have read-only access, commonly used for auditors and leadership.

### How do I invite a teammate?

From Settings > Users, enter their email and select a role. They'll receive an invite link that expires after 7 days.

### How do I change someone's role?

From Settings > Users, select the user and choose a new role. Role changes take effect immediately and don't require the user to log out and back in.

### How do I remove a user?

From Settings > Users, select "Remove access." This immediately revokes their login; it doesn't delete their historical activity (e.g. evidence they uploaded), which stays attributed to them for audit purposes.

### What is an access review?

A periodic check confirming that everyone with access to your systems (in the platform and in connected integrations) still needs it. Most frameworks require this quarterly. The platform generates a review checklist pulling current users from your connected integrations.

### Can I set up SSO/SAML?

Yes, on plans that include SSO. Configure your identity provider under Settings > Security, using the metadata URL or XML file your IdP provides.

### What's the difference between deactivating and deleting a user?

Deactivating suspends login immediately but keeps the account and its history intact, useful if access needs to be restored later. Deleting permanently removes the account; historical activity is retained but shown as attributed to a removed user.

### Is there an audit trail of access changes?

Yes, every role change, invite, and removal is logged with a timestamp and the admin who made the change, visible under Settings > Audit Log.

## Troubleshooting

### An invited teammate never received the invite email

Check whether the invite shows as "Pending" in Settings > Users, if so, it was sent; ask them to check spam, or resend it, which generates a fresh link. If the invite shows as "Expired," it's past the 7-day window and needs to be resent.

### A role change isn't taking effect

The user likely has an active session from before the change; ask them to log out and back in. If the issue persists, confirm the role change actually saved by refreshing the Users page.

### SSO login is failing or stuck in a redirect loop

This is almost always a mismatch between the metadata configured in the platform and what your identity provider is issuing, commonly a changed certificate. Re-upload the current metadata from your IdP under Settings > Security.

### A removed user still appears in an access review

Access reviews pull a snapshot from connected integrations at generation time. If the user was removed from the platform but not from the underlying system (e.g. still has an active AWS IAM user), they'll still appear until removed there too.
