FROM pgvector/pgvector:pg16
COPY migrations/*.sql /docker-entrypoint-initdb.d/
