FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt requirements-core.txt requirements-e2e.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-e2e.txt

COPY app ./app
COPY data ./data
COPY generated ./generated
COPY tests ./tests
COPY README.md SPEC.md TASKS.md pytest.ini .env.example ./

RUN mkdir -p /app/data/runs /app/data/normalized /app/data/api_inputs /app/generated/tests /app/generated/reports

EXPOSE 8000

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
