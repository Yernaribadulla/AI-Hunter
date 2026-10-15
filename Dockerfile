FROM python:3.12-slim
WORKDIR /app
COPY requirements-services.txt .
RUN pip install --no-cache-dir -r requirements-services.txt
COPY config.py candidate.py models.py safety.py ./
COPY services ./services
CMD ["python", "-m", "uvicorn", "services.analysis:app", "--host", "0.0.0.0", "--port", "8011"]
