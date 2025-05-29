# Fergus Kidd's Personal Website

This is the source code for my personal website, built with FastAPI and deployed on Azure Web Apps.

## Local Development

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your Azure Storage connection string:
```
AZURE_CONNECTION_STRING=your_connection_string_here
AZURE_CONTAINER_NAME=video
```

4. Run the development server:
```bash
uvicorn main:app --reload
```

## Deployment to Azure Web Apps

1. Create an Azure Web App with Python 3.9 runtime
2. Configure the following application settings in Azure Portal:
   - `AZURE_CONNECTION_STRING`: Your Azure Storage connection string
   - `AZURE_CONTAINER_NAME`: video
3. Deploy using Azure CLI or GitHub Actions

## Project Structure

- `main.py`: FastAPI application entry point
- `application.py`: ASGI entry point for Azure Web Apps
- `startup.sh`: Startup script for Azure Web Apps
- `web.config`: IIS configuration for Azure Web Apps
- `templates/`: Jinja2 templates
- `static/`: Static files (CSS, JavaScript, images)
- `content/`: Markdown content files

## Video Integration

Videos are stored in Azure Blob Storage and accessed using SAS tokens. The application automatically generates SAS tokens for video access and replaces local video references with Azure Storage URLs.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 