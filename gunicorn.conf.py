import os

# Bind to the port Azure provides
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Worker configuration
workers = 1  # Start with 1 worker for Azure Web Apps
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Timeouts
timeout = 30
keepalive = 2

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"

# Process naming
proc_name = "ferguskidd_com"

# Preload the application
preload_app = True 