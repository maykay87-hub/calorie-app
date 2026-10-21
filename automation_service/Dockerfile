FROM python:3.12-slim
WORKDIR /app
COPY automation_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 maybloom
COPY automation_service /app/automation_service
USER maybloom
EXPOSE 8080
CMD ["uvicorn", "automation_service.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
