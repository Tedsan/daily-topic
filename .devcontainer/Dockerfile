FROM mcr.microsoft.com/vscode/devcontainers/python:3.12

# Install additional system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js and Claude Code CLI (minimal installation)
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash && \
    export NVM_DIR="/usr/local/share/nvm" && \
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" && \
    nvm install 22 && \
    npm install -g @anthropic-ai/claude-code && \
    npm cache clean --force

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install pipx and Poetry for root user first
RUN pip install pipx && \
    pipx install poetry
ENV PATH="/root/.local/bin:$PATH"

# Create requirements.txt if it doesn't exist
RUN touch /tmp/requirements.txt

# Set working directory
WORKDIR /workspace

# Copy requirements if exists
COPY requirements.txt* ./

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install \
    pytest \
    black \
    flake8 \
    mypy \
    isort \
    ruff \
    requests \
    mcp-server-fetch

# Install additional requirements if file exists
RUN if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

# Clean up package cache to save space
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip cache purge && \
    rm -rf /tmp/* && \
    rm -rf /var/tmp/*

# Configure vscode user (may already exist)
RUN if ! id vscode > /dev/null 2>&1; then useradd -m -s /bin/bash vscode; fi && \
    echo "vscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# vscode ユーザーへコピー
RUN install -d /home/vscode/.local/bin \
    && cp /root/.local/bin/uv /root/.local/bin/uvx /home/vscode/.local/bin/ \
    && chown vscode:vscode /home/vscode/.local/bin/uv /home/vscode/.local/bin/uvx

# Setup nvm for vscode user
RUN cp -r /usr/local/share/nvm /home/vscode/.nvm && \
    chown -R vscode:vscode /home/vscode/.nvm && \
    echo 'export NVM_DIR="/home/vscode/.nvm"' >> /home/vscode/.bashrc && \
    echo '[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"' >> /home/vscode/.bashrc && \
    echo '[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"' >> /home/vscode/.bashrc && \
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/vscode/.bashrc

# Skip Poetry installation for vscode user to save space
# Poetry will be available via system installation

USER vscode

# Update environment variables for vscode user
ENV NVM_DIR="/home/vscode/.nvm"
ENV PATH="/home/vscode/.local/bin:$NVM_DIR/versions/node/v22.12.0/bin:$PATH"
