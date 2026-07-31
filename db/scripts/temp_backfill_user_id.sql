-- TEMPORARY: assign every existing Agent record to one real Java user.
-- WARNING: this intentionally overwrites existing user_id values.
-- Remove this file after the one-time backfill is complete.

\set ON_ERROR_STOP on

BEGIN;

DO $$
DECLARE
    target_user_id CONSTANT TEXT := '54d50aab-f937-4d47-8117-a528ded04663';
    affected_rows BIGINT;
BEGIN
    -- Relational Agent records.
    IF to_regclass('public.chat_sessions') IS NOT NULL THEN
        EXECUTE format(
            'UPDATE public.chat_sessions SET user_id = %L',
            target_user_id
        );
        GET DIAGNOSTICS affected_rows = ROW_COUNT;
        RAISE NOTICE 'chat_sessions updated: % rows', affected_rows;
    END IF;

    IF to_regclass('public.chat_messages') IS NOT NULL THEN
        EXECUTE format(
            'UPDATE public.chat_messages SET user_id = %L',
            target_user_id
        );
        GET DIAGNOSTICS affected_rows = ROW_COUNT;
        RAISE NOTICE 'chat_messages updated: % rows', affected_rows;
    END IF;

    IF to_regclass('public.chat_runs') IS NOT NULL THEN
        EXECUTE format(
            'UPDATE public.chat_runs SET user_id = %L',
            target_user_id
        );
        GET DIAGNOSTICS affected_rows = ROW_COUNT;
        RAISE NOTICE 'chat_runs updated: % rows', affected_rows;
    END IF;

    IF to_regclass('public.tool_runs') IS NOT NULL THEN
        EXECUTE format(
            'UPDATE public.tool_runs SET user_id = %L',
            target_user_id
        );
        GET DIAGNOSTICS affected_rows = ROW_COUNT;
        RAISE NOTICE 'tool_runs updated: % rows', affected_rows;
    END IF;

    IF to_regclass('public.vector_collections') IS NOT NULL THEN
        EXECUTE format(
            'UPDATE public.vector_collections SET user_id = %L',
            target_user_id
        );
        GET DIAGNOSTICS affected_rows = ROW_COUNT;
        RAISE NOTICE 'vector_collections updated: % rows', affected_rows;
    END IF;

    -- LangChain PGVector stores ownership inside cmetadata JSONB.
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'langchain_pg_collection'
          AND column_name = 'cmetadata'
    ) THEN
        EXECUTE format(
            $sql$
            UPDATE public.langchain_pg_collection
            SET cmetadata = jsonb_set(
                COALESCE(cmetadata, '{}'::jsonb),
                '{user_id}',
                to_jsonb(%L::text),
                true
            )
            $sql$,
            target_user_id
        );
        GET DIAGNOSTICS affected_rows = ROW_COUNT;
        RAISE NOTICE 'langchain_pg_collection metadata updated: % rows', affected_rows;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'langchain_pg_embedding'
          AND column_name = 'cmetadata'
    ) THEN
        EXECUTE format(
            $sql$
            UPDATE public.langchain_pg_embedding
            SET cmetadata = jsonb_set(
                COALESCE(cmetadata, '{}'::jsonb),
                '{user_id}',
                to_jsonb(%L::text),
                true
            )
            $sql$,
            target_user_id
        );
        GET DIAGNOSTICS affected_rows = ROW_COUNT;
        RAISE NOTICE 'langchain_pg_embedding metadata updated: % rows', affected_rows;
    END IF;
END
$$;

COMMIT;

