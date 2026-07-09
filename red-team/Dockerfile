FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    git curl build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir garak pyrit

WORKDIR /workspace
CMD ["/bin/bash"]