"""
ASGI entry point for Azure Web Apps
"""
from main import app

# Azure Web Apps expects this variable name
application = app

if __name__ == "__main__":
    import uvicorn
    import os
    
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("application:application", host="0.0.0.0", port=port) 