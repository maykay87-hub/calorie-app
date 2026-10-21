# Payment-to-membership integration checkpoint

**Implemented on the development channel; not released to students. Live payment fulfillment, email delivery, cloud deployment and calendar integrations remain unconnected.**

The new `automation_service` accepts signed payment notifications, retrieves canonical Stripe objects and records one entitlement per fulfilled checkout or paid invoice. Monthly rights follow paid invoice periods. One-time consultation packages include their own duration and credit count, with no automatic subscription conversion.

The service provides email activation, session-based member access, an encrypted email queue, operator exception visibility, published consultation availability, atomic booking and credit consumption, Malaysia-time confirmation emails, calendar attachments and reminder jobs. Live mode requires a deliberate release gate and durable PostgreSQL. Synthetic fixtures and temporary SQLite files are used for local tests.

`member_access.py` connects Streamlit to the service only when the new secrets section is enabled. Existing accounts remain available when the integration is disabled. Original students link membership after authenticating their original Tracker account; the Sheets identity is preserved. The service prevents silent renaming of an already-used new Tracker identity. Newly managed students are included in the coach's feedback selector. Demo mode still stops before credentials or external connections.

The separate website patch contains the approved payment destinations and optional member-service entry. Both checkout release and automatic member entry stay disabled pending deployment, terms review and end-to-end acceptance. No website deployment is made by this commit.

## Remaining release work

Configure the private service host, PostgreSQL, Stripe test credentials/price mappings/webhook, transactional SMTP sender, coach notification address and scheduled jobs. Publish only owner-approved consultation slots. Test PostgreSQL concurrency and the real email inbox, then test the complete buyer journey with Stripe test mode and isolated records. Review access start, overlapping packages, refunds, privacy, rescheduling and expiry terms before a separate validated student release.

Google Calendar conflict synchronization, meeting-link creation and automatic rescheduling are not implemented. Booking currently protects published slots inside this service; the operator must keep outside-calendar commitments aligned. Meeting links are supplied separately.

The member page was inspected on desktop and a narrow mobile layout using synthetic API response fixtures. This was UI validation, not a real Stripe/SMTP/cloud end-to-end test. The Python service could not run inside the managed browser preview environment, so HTTP tests exercised the actual backend separately.

See `automation_service/README.md` for the implementation contract and deployment checklist. Preserve the student deployment branch, stored records and existing release snapshots.

May also has an email-verified owner portal for publishing/closing availability, viewing member appointments and following up delivery/payment exceptions. Students cannot access these controls. Owner access requires the exact configured coach mailbox; it does not require a paid membership.
