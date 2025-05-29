#!/bin/bash

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI application with Gunicorn and Uvicorn worker
gunicorn --config gunicorn.conf.py main:app 