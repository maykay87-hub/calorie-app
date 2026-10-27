FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY webhook_app.py /app/webhook_app.py
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "exec uvicorn webhook_app:app --host 0.0.0.0 --port ${PORT:-8080}"]
