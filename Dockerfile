FROM --platform=linux/amd64 python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY . /app/

# (Optional) If you use Django's static files:
# RUN python manage.py collectstatic --noinput

# Expose the port
EXPOSE 8000


# Use Gunicorn to serve the WSGI application
# Adjust "wajo_backend.wsgi:application" if your WSGI module is named differently.
# Add workers/threads based on your app's needs.
CMD ["gunicorn", "wajo_backend.wsgi:application", "--bind", "0.0.0.0:8000", "--workers=3", "--threads=2"]