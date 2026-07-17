FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies before copying source so code-only rebuilds reuse this
# layer instead of contacting PyPI on every change.
COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose port
EXPOSE 8000

# Run server
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]