# Use an official Python runtime
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Postgres (required for psycopg2)
RUN apt-get update && apt-get install -y libpq-dev gcc

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app code
COPY . .

# Expose the port Flask runs on
EXPOSE 5000

# Command to run the app (using gunicorn for production is better, but python app.py works for now)
CMD ["python", "app.py"]