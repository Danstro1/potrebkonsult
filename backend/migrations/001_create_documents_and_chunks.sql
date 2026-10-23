-- База знаний: документы и фрагменты с эмбеддингами BGE-M3 (1024) для гибридного поиска.
-- Применение: docker exec -i potreb-pg psql -U potreb -d potrebkonsult -f /migrations/001_create_documents_and_chunks.sql

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Стабильный ключ документа (например, zozpp): новая редакция заменяет старую по ключу, а не по названию.
    key          text NOT NULL UNIQUE,
    title        text NOT NULL,
    edition_date date NOT NULL,
    chunks_count integer NOT NULL DEFAULT 0,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id    uuid NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    document_title text NOT NULL,
    article        text,
    article_title  text,
    part           integer NOT NULL DEFAULT 1 CHECK (part >= 1),
    content        text NOT NULL,
    embedding      vector(1024) NOT NULL,
    -- Полнотекстовый вектор с русской морфологией для будущего гибридного поиска (вектор + BM25-подобный).
    tsv            tsvector GENERATED ALWAYS AS (
                       to_tsvector('russian', coalesce(article_title, '') || ' ' || content)
                   ) STORED,
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- Метрика поиска — косинусное расстояние (оператор <=>), поэтому vector_cosine_ops.
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_gin_idx ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_document_id_idx ON chunks (document_id);
