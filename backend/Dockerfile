FROM python:3.13-slim

# System deps for shapely/pyproj/scipy
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgeos-dev libproj-dev gcc g++ && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Static files
RUN python manage.py collectstatic --noinput 2>/dev/null || true

# Migrate DB
RUN python manage.py migrate --run-syncdb 2>/dev/null || true

ENV DJANGO_SETTINGS_MODULE=backend.settings
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["gunicorn", "backend.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "300", \
     "--access-logfile", "-"]
