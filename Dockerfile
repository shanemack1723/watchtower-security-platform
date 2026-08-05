FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY backend ./backend
COPY dashboard ./dashboard
COPY detection_rules ./detection_rules
COPY migrations ./migrations
COPY scripts ./scripts

EXPOSE 8000

CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"]