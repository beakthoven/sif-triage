/* INGEST feature — public surface for the SHELL router.
 * Wire at /ingest (first-class route; today's ingest controls are buried in
 * Insights → Locations). Props: { lang, onIngested?, syncBudgetMs? } —
 * onIngested fires on every terminal run (feed/health refetch), syncBudgetMs
 * is a test hook, omit in production. */
export { IngestPage, default } from "./ingest-page";