from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import markdown2
import json
from datetime import datetime
from azure.storage.blob import BlobServiceClient
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Azure Storage configuration
AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "video")

# Initialize Azure Blob Service Client
try:
    if AZURE_CONNECTION_STRING:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    else:
        print("Warning: AZURE_CONNECTION_STRING not found in environment variables")
        blob_service_client = None
except Exception as e:
    print(f"Warning: Could not initialize Azure Storage client: {e}")
    blob_service_client = None

# Set up templates first
templates = Jinja2Templates(directory="templates")

# Mount static files - ensure proper configuration for url_for
static_files = StaticFiles(directory="static")
app.mount("/static", static_files, name="static")

# Blog posts directory
POSTS_DIR = Path("content/posts")

def get_azure_video_url(blob_name):
    """Generate a direct URL to a video blob in Azure Storage"""
    if not blob_service_client:
        return None
    
    try:
        # Generate the blob URL
        blob_client = blob_service_client.get_blob_client(
            container=AZURE_CONTAINER_NAME, 
            blob=blob_name
        )
        return blob_client.url
    except Exception as e:
        print(f"Error generating video URL for {blob_name}: {e}")
        return None

def list_azure_videos():
    """List all video files in the Azure Storage container"""
    if not blob_service_client:
        return []
    
    try:
        container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)
        videos = []
        
        for blob in container_client.list_blobs():
            # Filter for video file extensions
            if blob.name.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
                video_info = {
                    'name': blob.name,
                    'url': get_azure_video_url(blob.name),
                    'size': blob.size,
                    'last_modified': blob.last_modified
                }
                videos.append(video_info)
        
        # Sort by last modified date (newest first)
        videos.sort(key=lambda x: x['last_modified'], reverse=True)
        return videos
    except Exception as e:
        print(f"Error listing videos from Azure Storage: {e}")
        return []

def get_video_by_name(video_name):
    """Get a specific video by name from Azure Storage"""
    if not blob_service_client:
        return None
    
    try:
        blob_client = blob_service_client.get_blob_client(
            container=AZURE_CONTAINER_NAME, 
            blob=video_name
        )
        
        # Check if blob exists
        if blob_client.exists():
            return {
                'name': video_name,
                'url': blob_client.url,
                'properties': blob_client.get_blob_properties()
            }
        return None
    except Exception as e:
        print(f"Error getting video {video_name}: {e}")
        return None

def get_posts():
    posts = []
    markdown_files = list(POSTS_DIR.glob("*.md"))
    
    for post_file in markdown_files:
        try:
            with open(post_file, "r", encoding="utf-8") as f:
                content = f.read()
                # Extract metadata from the first few lines
                metadata = {}
                content_lines = content.split("\n")
                body_lines = []
                in_body = False
                
                for line in content_lines:
                    if not in_body:
                        if line.startswith("title: "):
                            metadata["title"] = line[7:].strip()
                        elif line.startswith("date: "):
                            metadata["date"] = line[6:].strip()
                        elif line.startswith("slug: "):
                            metadata["slug"] = line[6:].strip()
                        elif line.startswith("summary: "):
                            metadata["summary"] = line[9:].strip()
                        elif line.startswith("feature_image: "):
                            metadata["feature_image"] = line[15:].strip()
                        elif line.strip() == "":
                            in_body = True
                            continue
                    else:
                        body_lines.append(line)
                
                # Generate slug from filename if not provided
                if "slug" not in metadata:
                    metadata["slug"] = post_file.stem
                
                # Use filename as title if not provided
                if "title" not in metadata:
                    metadata["title"] = post_file.stem.replace("-", " ").title()
                
                # Use current date if not provided
                if "date" not in metadata:
                    metadata["date"] = datetime.now().strftime("%Y-%m-%d")
                
                if not body_lines:
                    continue
                    
                body = "\n".join(body_lines)
                
                # Clean up Ghost CMS specific content
                body = body.replace("__GHOST_URL__", "")
                
                # Extract summary from caption or first few sentences
                summary_text = ""
                
                # First try to get the video caption
                if "<figcaption>" in body:
                    caption_start = body.find("<figcaption>")
                    caption_end = body.find("</figcaption>")
                    if caption_start != -1 and caption_end != -1:
                        summary_text = body[caption_start + 12:caption_end].strip()
                
                # If no caption found, try to find first few sentences from the content
                if not summary_text:
                    # First, clean up HTML tags and get plain text
                    clean_text = ""
                    for line in body_lines:
                        line = line.strip()
                        if line and not line.startswith("<"):
                            # Remove any remaining HTML tags
                            line = line.replace("<p>", "").replace("</p>", "")
                            line = line.replace("<br>", " ").replace("<br/>", " ")
                            line = line.replace("&nbsp;", " ")
                            clean_text += line + " "
                    
                    # Split into sentences (basic sentence detection)
                    sentences = []
                    current_sentence = ""
                    for char in clean_text:
                        current_sentence += char
                        if char in '.!?' and len(current_sentence.strip()) > 10:  # Only split on punctuation if sentence is long enough
                            sentences.append(current_sentence.strip())
                            current_sentence = ""
                    
                    if current_sentence.strip():
                        sentences.append(current_sentence.strip())
                    
                    # Take first 2-3 sentences or first 200 characters
                    if sentences:
                        summary_text = " ".join(sentences[:3])
                    else:
                        summary_text = clean_text[:200]
                    
                    # Add ellipsis if we cut off the text
                    if len(clean_text) > len(summary_text):
                        summary_text = summary_text.rstrip() + "..."
                
                # Clean up any remaining HTML in the summary
                summary_text = summary_text.replace("<", "&lt;").replace(">", "&gt;")
                
                # Remove video player HTML from body
                if "<figure class=\"kg-card kg-video-card" in body:
                    body = f"<p>{summary_text}</p>"
                
                # Convert to HTML if it's not already HTML
                if not body.strip().startswith("<"):
                    html_content = markdown2.markdown(
                        body,
                        extras=["html-classes", "html"],
                        safe_mode="escape"
                    )
                else:
                    html_content = body
                
                metadata["content"] = html_content

                # If no summary was provided in metadata, use a default
                if "summary" not in metadata:
                    metadata["summary"] = "Click to read more..."

                posts.append(metadata)
        except Exception as e:
            continue
    
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

@app.get("/talk")
async def talk(request: Request):
    return templates.TemplateResponse(
        "talk.html",
        {"request": request, "current_year": datetime.now().year}
    )

@app.get("/videos")
async def videos(request: Request):
    """Display all available videos from Azure Storage"""
    video_list = list_azure_videos()
    return templates.TemplateResponse(
        "videos.html",
        {
            "request": request, 
            "videos": video_list, 
            "current_year": datetime.now().year
        }
    )

@app.get("/videos/{video_name}")
async def video_detail(request: Request, video_name: str):
    """Display a specific video"""
    video = get_video_by_name(video_name)
    if not video:
        return templates.TemplateResponse(
            "404.html",
            {"request": request, "current_year": datetime.now().year}
        )
    return templates.TemplateResponse(
        "video_detail.html",
        {
            "request": request, 
            "video": video, 
            "current_year": datetime.now().year
        }
    )

@app.get("/api/videos")
async def api_videos():
    """API endpoint to get video list as JSON"""
    return {"videos": list_azure_videos()}

# Add a custom Jinja2 filter for date formatting
def format_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        return value

templates.env.filters['format_date'] = format_date

if __name__ == "__main__":
    import uvicorn
    # Use PORT environment variable if available (Azure Web Apps sets this)
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False) 