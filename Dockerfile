FROM python:3.9-slim

WORKDIR /Youwant_UserInterface_EInvoice_converter

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m myuser
RUN chown -R myuser:myuser /Youwant_UserInterface_EInvoice_converter

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create directories with proper permissions
RUN mkdir -p uploads Downloaded processed && \
    chown -R myuser:myuser uploads Downloaded processed

USER myuser

EXPOSE 5000

ENV FLASK_APP=submitButtonHandling.py
ENV FLASK_ENV=development
ENV FLASK_RUN_HOST=0.0.0.0

CMD ["flask", "run"]