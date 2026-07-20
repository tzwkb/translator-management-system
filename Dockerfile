FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/alembic.ini backend/
COPY backend/migrations/ backend/migrations/
COPY backend/app/ backend/app/
COPY backend/docker-entrypoint.sh backend/
COPY frontend/ frontend/

RUN chmod 755 /app/backend/docker-entrypoint.sh && mkdir -p /data

ENV DB_URL=sqlite:////data/app.db
ENV TOKEN_TTL=28800

EXPOSE 8000

ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
