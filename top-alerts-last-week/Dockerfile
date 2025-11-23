# Use official lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
RUN INSTALL_PIP="streamlit-week-selector \
    altair \
    streamlit \
    pyzabbix \
    pandas \
    python-dotenv" &&  \
    pip install --no-cache-dir ${INSTALL_PIP}

# Copy application code
COPY app.py .
COPY zabbix_icon.svg .

# Disable Streamlit telemetry
ENV STREAMLIT_BROWSER_GATHERUSAGESTATS=false

# Expose Streamlit default port
EXPOSE 8501

# Run Streamlit app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]


