# likha-poha-promo-assets

Static assets + GitHub Actions cron jobs that post Likha Poha AI's daily
Instagram content, plus a lead-capture questionnaire for the "Learn More"
CTA in those captions.

## What's running

Three independent cron workflows, each owning its own queue file so they
never contend over the same file on `git push`:

- **`.github/workflows/daily-post.yml`** — cron 3x/day (8am, 2pm, 7pm IST).
  Runs `scripts/post_next_instagram_post.py` for
  `queue/instagram_post_queue.json` (Instagram feed posts only).
- **`.github/workflows/daily-whatsapp.yml`** — cron 2x/day (10:30am, 5pm
  IST). Runs `scripts/post_next_whatsapp_post.py` for
  `queue/whatsapp_queue.json` (WhatsApp image posts, English only).
- **`.github/workflows/daily-reel.yml`** — cron `30 10 * * *` (4pm IST).
  Runs `scripts/post_next_reel.py`, which posts the next `pending` item in
  `queue/reel_queue.json` to Instagram as a Reel via the Meta Graph API.

Each script always posts whichever item is first with `"status": "pending"`
in its queue (plain FIFO — no per-run decision logic), then commits that
queue file back with `status: "posted"` and a `posted_at` timestamp.

### Language rotation

Every queue item carries a `"lang": "en" | "hi"` field. It's informational
only — nothing in the scripts reads it. The 2 English : 1 Hindi daily ratio
comes entirely from how each queue's *pending* items are pre-ordered: in
repeating groups of `[EN, EN, HI]`. Since `daily-post.yml` fires exactly 3x/day
and `daily-reel.yml` fires exactly 1x/day, that ordering alone is enough to
guarantee 2 English + 1 Hindi Instagram post every calendar day, and an
English/English/Hindi day rotation for reels (since only one reel posts
per day). WhatsApp has no Hindi content in rotation yet.

When adding a new content batch (English or Hindi), preserve this pattern:
interleave the new pending items into their queue in `[EN, EN, HI]` groups
rather than appending them all at the end, or the daily ratio will drift
until the batch is reached.

- Assets are served by GitHub Pages at
  `https://pradipbhuyan.github.io/likha-poha-promo-assets/`.

## Lead capture ("Learn More" CTA)

Instagram's Graph API cannot attach interactive stickers (polls, quizzes,
link buttons) to Reels or feed posts — that's app-UI-only, Stories-only.
So the interactive layer is: **caption CTA -> bio link -> questionnaire ->
email**.

- `interest/index.html` — a 2-step mobile questionnaire, live at
  `https://pradipbhuyan.github.io/likha-poha-promo-assets/interest/`:
  1. Who are you? (Student / Parent / Teacher)
  2. Grade, headcount (contextual per role), name, WhatsApp number -> Submit
- It posts to `POST https://api.likhapoha.in/api/leads` — the same
  Render-hosted FastAPI backend the main `cbse-tutor-platform` app runs
  (see `backend/app/routes/leads.py` there). No separate service: the
  lead is written to a Supabase table (`instagram_leads`, migration
  `backend/migrations/20260826_instagram_leads.sql`) and emailed to
  **likhapohaai@gmail.com** via the backend's existing Resend/SMTP email
  service (`send_instagram_lead_notification` in `email_service.py`).
  Rate-limited per IP (`LEAD_CAPTURE_LIMITER`, 5/min) since it's a public,
  unauthenticated endpoint.
- Every pending **English** Instagram caption in
  `queue/instagram_post_queue.json` ends with
  `👉 Learn More — free study plan, link in bio` before the hashtags. The
  Hindi captions (added for the 2:1 language rotation, see above) don't
  have this CTA line yet — it wasn't part of that batch and would need a
  Hindi-appropriate version added deliberately, not just appended.

### One-time setup

1. In `cbse-tutor-platform`: run `backend/migrations/20260826_instagram_leads.sql`
   against the Supabase project (SQL editor, same as any other migration
   in that folder), then deploy the backend as usual — the new
   `POST /api/leads` route and CORS entry for
   `https://pradipbhuyan.github.io` ship with the next Render deploy.
2. In the Instagram app: **Edit Profile -> Link** -> set it to
   `https://pradipbhuyan.github.io/likha-poha-promo-assets/interest/`.
   This is the only way to set an Instagram bio link — it isn't exposed
   through the Graph API.

Once the migration's run and the bio link is set, every new submission
lands in Supabase and in your inbox within seconds.
