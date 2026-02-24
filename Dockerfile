FROM python:3.13-slim

WORKDIR /st_bea

RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    build-essential \
    git \
 && rm -rf /var/lib/apt/lists/*

ARG CORE_BRANCH=main
RUN pip install git+https://github.com/Skatetrax/skatetrax_core.git@${CORE_BRANCH}#egg=skatetrax_core

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /st_bea/app
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]