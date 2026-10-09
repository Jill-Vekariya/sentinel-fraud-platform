FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --uid 10001 --create-home fraud && mkdir -p /app/data /app/models && chown -R fraud:fraud /app
USER fraud
EXPOSE 8000
CMD ["uvicorn", "fraud.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
