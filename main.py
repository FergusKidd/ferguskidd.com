from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import markdown2
import json
from datetime import datetime

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up templates
templates = Jinja2Templates(directory="templates")

# Blog posts directory
POSTS_DIR = Path("content/posts")

def get_posts():
    posts = []
    for post_file in POSTS_DIR.glob("*.md"):
        with open(post_file, "r", encoding="utf-8") as f:
            content = f.read()
            # Extract metadata from the first few lines
            metadata = {}
            content_lines = content.split("\n")
            body_lines = []
            for i, line in enumerate(content_lines):
                if line.startswith("title: "):
                    metadata["title"] = line[7:]
                elif line.startswith("date: "):
                    metadata["date"] = line[6:]
                elif line.startswith("slug: "):
                    metadata["slug"] = line[6:]
                elif line.strip() == "" and len(metadata) >= 3:
                    # After all metadata, the rest is content
                    body_lines = content_lines[i+1:]
                    break
            if not body_lines:
                # fallback: skip first 3 lines
                body_lines = content_lines[3:]
            body = "\n".join(body_lines)
            html_content = markdown2.markdown(body)
            metadata["content"] = html_content

            # Extract summary: first paragraph or first 40 words
            summary_text = body.strip().split("\n\n")[0]  # first paragraph
            words = summary_text.split()
            if len(words) > 40:
                summary_text = " ".join(words[:40]) + "..."
            summary_html = markdown2.markdown(summary_text)
            metadata["summary"] = summary_html

            posts.append(metadata)
    
    # Sort posts by date
    posts.sort(key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d"), reverse=True)
    return posts

@app.get("/")
async def home(request: Request):
    posts = get_posts()
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "posts": posts, "current_year": datetime.now().year}
    )

@app.get("/about")
async def about(request: Request):
    return templates.TemplateResponse(
        "about.html",
        {"request": request, "current_year": datetime.now().year}
    )

@app.get("/posts/{slug}")
async def post(request: Request, slug: str):
    posts = get_posts()
    post = next((p for p in posts if p["slug"] == slug), None)
    if not post:
        return templates.TemplateResponse(
            "404.html",
            {"request": request, "current_year": datetime.now().year}
        )
    return templates.TemplateResponse(
        "post.html",
        {"request": request, "post": post, "current_year": datetime.now().year}
    )

# Add a custom Jinja2 filter for date formatting
def format_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        return value

templates.env.filters['format_date'] = format_date

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 