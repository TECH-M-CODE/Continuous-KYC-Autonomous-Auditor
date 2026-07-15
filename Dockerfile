FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Create application directory
WORKDIR /workspace

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend codebase
COPY app/ app/
COPY demo/ demo/
COPY policy.yaml .
COPY data/ data/

# Create a non-privileged user and adjust directory ownership
RUN useradd -u 10001 -m appuser \
    && mkdir -p /workspace/data \
    && chown -R appuser:appuser /workspace

USER appuser

# Expose port
EXPOSE 8000

# Command to execute backend app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
