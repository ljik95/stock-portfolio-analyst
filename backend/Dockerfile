FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
# (No system deps needed — asyncpg ships as a prebuilt wheel and
#  doesn't require gcc / libpq-dev like psycopg2 does.)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
