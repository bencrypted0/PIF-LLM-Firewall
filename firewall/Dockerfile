FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip wheel
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download and cache the classifier model from Hugging Face
RUN python -c "from transformers import pipeline; pipeline('text-classification', model='bennetsharwin/distilbert-prompt-injection-v2')"

COPY . .

EXPOSE 5000

CMD ["python", "main.py"]
