FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && adduser --disabled-password --gecos "" appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data
COPY --chown=appuser:appuser app ./app

ENV DATABASE_URL=sqlite:////data/github_activity.db
ENV APP_API_KEY=change-me
ENV PAY_TO=0x9c768177521C9A832B0f8567265ef02E89D0282e
EXPOSE 8000
USER appuser
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import json,urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=3)); assert data['status']=='ok'"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
