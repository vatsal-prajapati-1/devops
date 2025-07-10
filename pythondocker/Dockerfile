# Use official Python base image
FROM python:3.10-slim
 
# Set working directory
WORKDIR /myapp
 
# Copy project files into the container
COPY . .
 
# Upgrade pip and install dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt
 
# Expose the Streamlit port
EXPOSE 8501
 
# Set environment variable so Streamlit knows it's running in a Docker container
ENV STREAMLIT_SERVER_HEADLESS=true
 
# Run the Streamlit app and bind it to 0.0.0.0 for external access
CMD ["streamlit", "run", "alm.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableCORS=false"]