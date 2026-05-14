FROM python:3.11-slim

# Install system dependencies required for Rust and PyO3
RUN apt-get update && apt-get install -y curl build-essential && rm -rf /var/lib/apt/lists/*

# Install Rust toolchain
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

# Create and activate a Python Virtual Environment strictly
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# Maturin explicitly requires this variable to know it's safe to install
ENV VIRTUAL_ENV="/opt/venv" 

# Install Python dependencies inside the venv
COPY frontend/requirements.txt /app/frontend/
RUN pip install --no-cache-dir -r frontend/requirements.txt maturin

# Copy the Rust backend and build it
COPY backend /app/backend
WORKDIR /app/backend

# Build the rust extension and install it into the active venv
RUN maturin develop --release

# Copy the frontend code
WORKDIR /app
COPY frontend /app/frontend

# Default command
CMD ["python", "frontend/src/main.py"]