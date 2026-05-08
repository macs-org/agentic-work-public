FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AUDITOR_API_KEY=change-me \
    X402_PAY_TO=0x0000000000000000000000000000000000000000 \
    AUDIT_HISTORY_PATH=/data/audit_history.jsonl

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY README.md DEPLOYMENT.md DEMO.md ACCEPTANCE_CHECKLIST.md ./
RUN mkdir -p /data && chown -R nobody:nogroup /data
USER nobody

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import json, urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8000/ready'))['status'] == 'ready'"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
