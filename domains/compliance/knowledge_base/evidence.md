# Evidence

## FAQ

### What counts as evidence?

Anything that demonstrates a control is actually in place: screenshots, exported reports, config snapshots, signed attestations, or files pulled automatically from a connected integration. Each framework's control set specifies what's acceptable per control.

### How do I upload evidence manually?

From a control's detail page, click "Add evidence" and upload a file or paste a link. You'll be asked to note the collection date, which starts the clock on its expiration.

### How often does evidence need to be renewed?

It depends on the control's testing cadence, most manual evidence expires after 90 days and needs to be re-collected. The platform sends a reminder 14 days before expiration.

### What file types are supported?

PDF, PNG, JPG, CSV, and plain text are all accepted, up to 25MB per file. For larger exports (e.g. full audit logs), link to the file in cloud storage instead of uploading it directly.

### Can one piece of evidence satisfy multiple controls?

Yes. When uploading, you can attach the same evidence to any control it's relevant to instead of uploading duplicates. This is common for evidence like a company-wide security policy.

### What happens to evidence when I remove a framework?

Evidence isn't deleted. It stays attached to any other control (in any other framework) it's linked to, and remains in the evidence library for reference.

### Can auditors see evidence directly?

Yes, once you grant them auditor access, they can view and download evidence for controls in scope of the audit they're assigned to, without needing to request each file individually.

### Is there a limit on how much evidence I can store?

No, evidence storage is unlimited on all plans.

## Troubleshooting

### Upload is stuck on "Processing"

Files are scanned and OCR'd after upload, which usually takes under a minute. If a file has been stuck for more than 15 minutes, it likely failed silently: delete it and re-upload, ideally in a supported format under the size limit.

### Evidence is marked expired but I just uploaded it

Check the "collection date" you entered when uploading, not the upload date. If you backdated the collection date to match when a screenshot was actually taken, the expiration is calculated from that date, not today.

### An uploaded file was rejected as an unsupported format

Only PDF, PNG, JPG, CSV, and plain text are accepted. Common culprits are Excel files (export as CSV instead) and HEIC photos from iPhones (convert to JPG or PNG before uploading).

### Evidence isn't linking to the control after upload

If you uploaded through the general evidence library instead of from the control's own detail page, it won't auto-attach. Open the evidence item and use "Link to control" to attach it manually.
