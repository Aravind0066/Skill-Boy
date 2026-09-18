# Skill-Boy

## Evaluation history and website recognition

The evaluator stores each completed score in Supabase when `SUPABASE_PERSIST_RESULTS=true`.
Use a server-only `SUPABASE_SECRET_KEY` or `SUPABASE_SERVICE_ROLE_KEY`; a publishable or
anonymous key cannot write evaluation history. Run `supabase_schema.sql` in the Supabase
SQL editor before the first persisted evaluation.

Each browser receives an anonymous `skillblade_player_id` cookie. The `/history` endpoint
returns that browser's latest 50 evaluations, including score, tier, mode, and the website
recognition confidence. No account is required for this first history version.

Uploads pass through a conservative OpenCV website-screen heuristic before the scoring
modules run. Tune `WEBSITE_MIN_CONFIDENCE` during trials; the default is `55` out of `100`.
This is intentionally a gate against unrelated images, not a claim of semantic image
understanding. Review false positives and false negatives from real website captures before
raising the threshold in production.

## Database migration

Install the migration dependencies and apply the Supabase PostgreSQL schema from the terminal:

```bash
npm install
DATABASE_URL="your_supabase_postgres_connection_string" npm run migrate
```

Set `DATABASE_SSL=false` for a local PostgreSQL server. The migration is idempotent and can be
run again safely after schema changes.