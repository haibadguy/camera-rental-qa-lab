FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir pip==26.2 \
    && python -m pip install --no-cache-dir -r requirements.txt
COPY . .
RUN DJANGO_SECRET_KEY=build-only-key POSTGRES_HOST=unused POSTGRES_DB=unused \
    POSTGRES_USER=unused POSTGRES_PASSWORD=unused python manage.py collectstatic --noinput

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
