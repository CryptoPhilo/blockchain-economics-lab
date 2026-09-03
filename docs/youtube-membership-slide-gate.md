# YouTube Membership Slide Gate

BCELAB report detail pages render HTML slide decks only for verified paid members of the BCELAB YouTube channel.

## Runtime Environment

Configure these values in the production Vercel project:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY` or `SUPABASE_SERVICE_ROLE_KEY`
- `YOUTUBE_API_KEY` or `NEXT_PUBLIC_YOUTUBE_API_KEY`
- `YOUTUBE_MEMBERS_OAUTH_CLIENT_ID` or `YOUTUBE_OAUTH_CLIENT_ID`
- `YOUTUBE_MEMBERS_OAUTH_CLIENT_SECRET` or `YOUTUBE_OAUTH_CLIENT_SECRET`
- `YOUTUBE_MEMBERS_REFRESH_TOKEN` or `YOUTUBE_OAUTH_REFRESH_TOKEN`
- `NEXT_PUBLIC_BCELAB_YOUTUBE_JOIN_URL` optional; defaults to `https://www.youtube.com/@BCELAB/join`

The creator OAuth refresh token must belong to a BCELAB channel owner account with access to the YouTube channel membership API.

## Database

Apply `supabase/migrations/20260903000100_add_youtube_membership_links.sql` before or with the web deployment.

The table allows authenticated users to read only their own membership link. Inserts and updates are performed by server routes through the service-role key.

## Rollout Check

1. Deploy the migration with the Database Migration workflow or by merging the migration to `main`.
2. Confirm the Vercel production environment contains the runtime variables above.
3. Deploy the web branch through the Production Deploy workflow.
4. Verify `/en/auth` no longer shows Google or GitHub sign-in buttons.
5. Verify a signed-out request to `/en/reports/megaeth/econ` shows the YouTube paid-member gate and does not include the HTML slide iframe or slide storage URL.
6. Verify a paid YouTube channel member can sign in, complete `/en/membership`, and view the HTML slides.
