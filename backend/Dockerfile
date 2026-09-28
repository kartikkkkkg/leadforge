FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY leadforge/ ./leadforge/

# SQLite database file lives here when DATABASE_URL is not set.
VOLUME ["/app/data"]

EXPOSE 8000

# Default: serve the API. Jobs run in-process via FastAPI BackgroundTasks
# (there is no separate worker service); see DESIGN.md.
CMD ["uvicorn", "leadforge.main:app", "--host", "0.0.0.0", "--port", "8000"]
