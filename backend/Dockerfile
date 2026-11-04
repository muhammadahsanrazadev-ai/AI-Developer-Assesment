FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app:create_app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# Apply migrations on every start, then serve the API (threaded, so pipeline runs don't block requests).
CMD ["sh", "-c", "flask db upgrade && flask run --host 0.0.0.0 --port 5000"]
