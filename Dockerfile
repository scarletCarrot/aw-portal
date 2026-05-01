# AW Client Report Portal — production container
#
# Base image: Microsoft's official Playwright Python image. It already includes
# Chromium plus every system library Chromium needs (libgobject, fontconfig,
# nss, etc). Skipping it would force us to apt-install ~30 packages by hand.

FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Install Python deps first (better Docker layer caching).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY . .

# Render (and most PaaS) injects $PORT at runtime. Default to 8000 locally.
EXPOSE 8000

# 2 workers is plenty for a 3-person internal tool. --timeout=60 because
# Playwright PDF generation can briefly spike beyond the default 30s.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 60 app:app"]
