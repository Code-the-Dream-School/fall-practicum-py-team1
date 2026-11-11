FROM python:3.11-slim
WORKDIR /app
# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Copy app code
# COPY services/pipeline/myapp.py .
# Expose Streamlit's default port
EXPOSE 8501
# Run the app
ENTRYPOINT ["streamlit", "run", "myapp.py", "--server.port=8501", "--server.address=0.0.0.0"]