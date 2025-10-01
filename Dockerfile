FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install system dependencies including OpenGL libraries for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 \
    libjpeg-dev libpng-dev libtiff-dev \
    wget \
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


# Copy entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Use entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]