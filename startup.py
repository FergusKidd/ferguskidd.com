import os
import sys
from main import app

if __name__ == "__main__":
    import uvicorn
    # Azure Web Apps will set the PORT environment variable
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port) 