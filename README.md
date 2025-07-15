# Fergus Kidd's Personal Website

This is the source code for my personal website and blog, built with FastAPI, Jinja2, and deployed on Azure Web Apps. It features a modern, accessible design with animated backgrounds, dark mode, and high-contrast accessibility mode.

---

## Features

- **Modern, accessible blog** with dark mode and high-contrast accessibility mode (toggle in the top right)
- **Animated morphing gradient background** and floating particles, with mode-aware colors
- **Responsive, mobile-friendly design**
- **Markdown-based content system** (`content/posts/`)
- **Video and audio integration** via Azure Blob Storage
- **Jinja2 templates** for all pages (home, post, about, videos, etc.)
- **Custom navigation layout** (centered links, logo left, toggles right)

---

## Local Development

1. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Create a `.env` file** (see `.env.example`) with your Azure Storage connection string:
   ```
   AZURE_CONNECTION_STRING=your_connection_string_here
   AZURE_CONTAINER_NAME=video
   ```
4. **Run the development server:**
   ```bash
   uvicorn main:app --reload
   ```

---

## Deployment to Azure Web Apps

1. Create an Azure Web App with Python 3.13 runtime
2. Configure the following application settings in Azure Portal:
   - `AZURE_CONNECTION_STRING`: Your Azure Storage connection string
   - `AZURE_CONTAINER_NAME`: video
3. Deploy using Azure CLI or GitHub Actions
4. The app uses Gunicorn with Uvicorn workers for production (see `startup.sh` and `gunicorn.conf.py`)

---

## Project Structure

- `main.py`: FastAPI application entry point
- `application.py`: ASGI entry point for Azure Web Apps
- `startup.sh`: Startup script for Azure Web Apps
- `gunicorn.conf.py`: Gunicorn configuration for production
- `templates/`: Jinja2 templates (HTML)
- `static/`: Static files (CSS, JavaScript, images)
- `static/css/particles.css`: Animated backgrounds and particles
- `content/posts/`: Markdown blog posts
- `requirements.txt`: Python dependencies
- `.env.example`: Example environment variables

---

## Content Management

- **Add a blog post:** Place a markdown file in `content/posts/`.
- **Add images:** Place in `static/images/` and reference in markdown.
- **Add videos/audios:** Upload to Azure Blob Storage (see Video Integration below).

---

## Video & Audio Integration

- Videos and audios are stored in Azure Blob Storage and accessed using SAS tokens.
- The app automatically generates SAS tokens for secure access and replaces local references with Azure Storage URLs.

---

## Theme & Accessibility

- **Dark mode:** Click the moon icon (top right) to toggle dark mode.
- **High-contrast mode:** Click the lightning bolt icon (top right) for high-contrast accessibility mode.
- Modes are mutually exclusive and persist across sessions.
- All backgrounds, text, and particles adapt to the selected mode.

---

## Customization

- **Edit `static/css/particles.css`** to change background/particle effects or colors.
- **Edit `templates/base.html`** for layout, navigation, and theme logic.
- **Edit markdown in `content/posts/`** for blog content.

---

## Requirements

- Python 3.8+
- FastAPI, Uvicorn, Jinja2, markdown2, Azure Storage SDK, python-dotenv, Gunicorn

---

## License

This project is licensed under the MIT License - see the LICENSE file for details. 