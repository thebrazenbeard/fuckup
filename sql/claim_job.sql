-- Claim or reclaim one job through the guarded database function defined
-- by migrations/0001_core.sql.
--
-- The function:
-- - rejects blank worker IDs;
-- - requires a positive bounded lease;
-- - dead-letters exhausted work;
-- - reclaims expired RUNNING leases;
-- - never increments attempts past max_attempts;
-- - uses FOR UPDATE SKIP LOCKED for collision-free concurrent claims.
--
-- Bind parameters:
--   :worker_id      text
--   :lease_seconds  integer (1..86400)

SELECT *
FROM claim_worker_job(:worker_id, :lease_seconds);
