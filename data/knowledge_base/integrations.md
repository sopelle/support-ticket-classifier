# Integrations

## FAQ

### What integrations are supported?

Cloud providers (AWS, GCP, Azure), identity providers (Okta, Google Workspace, Azure AD), source control (GitHub, GitLab), and common SaaS tools (Slack, Jira, Zoom) are all supported for automatic evidence collection. New integrations are added regularly.

### How do I connect an integration?

From the Integrations page, select the tool and follow the OAuth or API-key flow. Most integrations connect in under five minutes and start their first sync immediately.

### What permissions does the platform request?

Read-only access scoped to what's needed for the controls you have mapped to that integration, for example, IAM configuration for AWS, or user and MFA status for an identity provider. The exact scopes are listed before you authorize.

### How often do integrations sync?

Once every 24 hours by default. You can trigger a manual sync from the integration's page if you need fresher data before a specific control check.

### Can I disconnect an integration?

Yes, at any time from the Integrations page. Disconnecting stops future syncs but doesn't delete evidence already collected.

### Does the platform ever write to my systems?

No. All integrations are read-only; the platform never creates, modifies, or deletes resources in your connected accounts.

### What happens to evidence collected before I disconnect an integration?

It stays in place and continues to count toward controls until it expires. Once disconnected, no new evidence is collected, so those controls will need a new evidence source before their next renewal.

### Can I connect the same integration for multiple environments?

Yes, you can connect separate AWS accounts, GCP projects, or GitHub organizations (e.g. staging and production) independently, and choose which ones are in scope per framework.

## Troubleshooting

### An integration shows "Error" or disconnected unexpectedly

This is almost always an expired credential or a revoked API key/OAuth grant on the source system's side. Reconnect the integration from the Integrations page; you won't lose previously collected evidence.

### Sync hasn't run in several days

Check the integration's status page for a rate-limit or permission warning. If the status looks healthy but the "last synced" timestamp is stale, trigger a manual sync; if that also doesn't complete, the source account may have revoked a scope the sync depends on.

### I get a permission or scope error when connecting

The account you're authenticating with needs admin-level (or equivalent) permissions on the source system to grant the requested read-only scopes. Connecting with a standard user account is the most common cause of this error.

### Evidence isn't appearing after a successful sync

Confirm the resource the evidence should come from actually exists in the connected account or project, syncs only pull what's present. Also check that the integration is scoped to the right account/project if you have more than one connected.
