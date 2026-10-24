# Existing website integration

Status: prepared, not installed on maybloomwellness.com. The website source and
its Cloudflare/AI Studio publishing project have not been provided to this checkout.

For the existing React/AI Studio website, import MayBloomTrackerLinks.tsx into the
current course page. Render `<MayBloomTrackerLinks />` beside the course's tracker
benefit. Render `<MayBloomTrackerLinks compact />` only where two navigation
actions are wanted. Use either placement as appropriate; do not create a second
website or replace the existing layout. Keep the existing keyboard focus styles.

The two actual destinations are:

- Try the tracker: the existing Streamlit URL with `?demo=1`; all sample data is
  local to that app session, and it does not read student accounts.
- Student sign-in: the same app's root URL; it retains coach-provided sign-in.

The links open a separate tab so visitors can return to the website. The component
does not embed the app, transfer profile values, pass credentials through URLs,
create accounts, change DNS or change database sharing.

Before publishing the actual website, check both links from the updated website
preview and from its Cloudflare production deployment. Confirm that the first
shows the public demo and the second shows the actual sign-in screen.

AI Studio implementation brief:

> In this existing May Bloom Wellness website, add a compact Lifestyle Tracker
> section to the course benefits area, using MayBloomTrackerLinks.tsx. Keep the
> current brand and other content. Add the actual Try tracker and Student sign-in
> links exactly as supplied. Do not add an iframe, login form or AI claims to the
> website. Keep the actual application on Streamlit. Build and check mobile link
> layout before updating the existing Cloudflare project.
