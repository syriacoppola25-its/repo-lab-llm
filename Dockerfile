FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY assistente/ assistente/
COPY server_note/ server_note/
COPY server_calcolatrice/ server_calcolatrice/

CMD ["python", "-m", "assistente"]
