FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Scrapy and Playwright
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libxml2-dev \
    libxslt-dev \
    libffi-dev \
    libssl-dev \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers
RUN pip install playwright==1.40.0 && \
    playwright install chromium --with-deps && \
    playwright install-deps chromium

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default command
CMD ["python", "-m", "scrapy", "crawl", "sina"]
