# Python 3.10 base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create instance directory for SQLite database
RUN mkdir -p instance

# Expose port
EXPOSE 8002

# Environment variables (can be overridden)
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Run the application with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8002", "--workers", "4", "--timeout", "120", "app:app"]
