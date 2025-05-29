#!/bin/bash

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI application
python -m uvicorn main:app --host 0.0.0.0 --port $PORT 