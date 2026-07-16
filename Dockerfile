FROM python:3.14-slim

WORKDIR /app

# 装依赖（先拷 requirements，变依赖时重装，不变用缓存）
COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 拷代码（分层放下面，依赖缓存优先）
COPY backend/app/ backend/app/
COPY frontend/ frontend/

ENV JWT_SECRET=change-me-in-production
ENV TOKEN_TTL=28800
EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
