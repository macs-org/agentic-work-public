FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MARKETPLACE_API_KEY=dev-marketplace-key

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY sdk ./sdk
COPY contracts ./contracts
COPY README.md ACCEPTANCE_CHECKLIST.md DEMO.md LIMITATIONS.md ./

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
