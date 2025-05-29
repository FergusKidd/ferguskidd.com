#!/bin/bash

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI application with Gunicorn and Uvicorn worker
cd /home/site/wwwroot
gunicorn --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 application:app 