\set ON_ERROR_STOP on

\if :{?fuckup_schema}
\else
  \echo 'ERROR: set -v fuckup_schema=<trusted_schema>'
  \quit
\endif

\if :{?fuckup_authorizer_role}
\else
  \echo 'ERROR: set -v fuckup_authorizer_role=<existing_authorizer_role>'
  \quit
\endif

SELECT current_database() AS fuckup_database \gset

SET search_path TO :"fuckup_schema", pg_catalog;

SELECT configure_fuckup_authorizer_role(:'fuckup_authorizer_role'::name);

ALTER ROLE :"fuckup_authorizer_role"
    IN DATABASE :"fuckup_database"
    SET search_path TO :"fuckup_schema", pg_catalog;
