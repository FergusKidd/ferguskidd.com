# Fergus Kidd's Personal Website

This is the source code for my personal website and blog, built with FastAPI, Jinja2, and deployed on Azure Web Apps. It features a modern, accessible design with animated backgrounds, dark mode, and high-contrast accessibility mode.

---

## Features

- **Editorial layout** with a dark-first theme, light mode, and high-contrast mode
- **Responsive, mobile-friendly design**
- **Private studio** at `/ai` — a single-user agent behind a signed-in session
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
3. **Create a `.env` file** (see `.env.example`) with your Azure Storage connection string, and the studio settings if you want `/ai`:
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
   - Studio settings from `.env.example` if you use `/ai` (`AI_PASSWORD_HASH`, `AI_SESSION_SECRET`, and either Azure OpenAI or `OPENAI_API_KEY`)
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

- **Dark mode** is the default. The sun/moon button switches to light mode.
- **High-contrast mode:** the lightning button. Modes persist across sessions.

---

## Customization

- **Edit `static/css/site.css`** for the visual design.
- **Edit `templates/base.html`** for layout, navigation, and theme logic.
- **Edit markdown in `content/posts/`** for blog content.

---

## Private studio (`/ai`)

`/ai` is a single-user chat agent. It stays locked until the server has a password hash and a session secret. Transcripts are stored on the server for that sign-in only and deleted on sign-out.

1. Generate a hash (12+ characters). The plaintext password is never saved:
   ```bash
   python scripts/hash_ai_password.py
   ```
2. Generate a session secret:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
3. Put both in the environment, plus a model connection. Azure OpenAI is used when `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, and `AZURE_OPENAI_DEPLOYMENT` are all set. Otherwise set `OPENAI_API_KEY`.
4. Optional: write a custom system prompt to `data/ai/prompt.md`, or set `AI_SYSTEM_PROMPT`.
5. Open `/ai`, sign in, and chat. Failed attempts lock that client out for 15 minutes after 8 misses.

The username defaults to `fergus` (`AI_USERNAME`). Set these as Azure App Settings in production. Do not commit them.

## Requirements

- Python 3.8+
- FastAPI, Uvicorn, Jinja2, markdown2, Azure Storage SDK, python-dotenv, Gunicorn

---

## License

This project is licensed under the MIT License - see the LICENSE file for details. 