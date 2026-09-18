# Development image: installs dependencies fresh into the image (never reuses
# the host's backend/venv) and runs uvicorn with --reload against a bind-mounted
# copy of the source, so host edits hot-reload inside the container.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
