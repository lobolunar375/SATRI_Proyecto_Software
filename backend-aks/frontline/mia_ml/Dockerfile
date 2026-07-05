FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias de compilacion si son necesarias para numpy/scipy/scikit-learn
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Regenerar el modelo con la versión de sklearn del contenedor para evitar incompatibilidades
RUN python train_isolation_forest.py

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]

