import json
import os
from pathlib import Path
from datetime import datetime
from slugify import slugify

def convert_json_to_markdown():
    # Create content/posts directory if it doesn't exist
    posts_dir = Path("content/posts")
    posts_dir.mkdir(parents=True, exist_ok=True)

    # Read the JSON file
    with open("data/json_content/fergus-kidd.ghost.2025-05-29-11-01-11.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # Process each post
    for post in data.get("db", [{}])[0].get("data", {}).get("posts", []):
        # Create slug from title if not present
        slug = post.get("slug", slugify(post.get("title", "")))
        
        # Format date - handle both string and timestamp formats
        published_at = post.get("published_at")
        if isinstance(published_at, (int, float)):
            date = datetime.fromtimestamp(published_at).strftime("%Y-%m-%d")
        elif isinstance(published_at, str):
            try:
                date = datetime.fromisoformat(published_at).strftime("%Y-%m-%d")
            except ValueError:
                date = datetime.now().strftime("%Y-%m-%d")
        else:
            date = datetime.now().strftime("%Y-%m-%d")
        
        # Create markdown content
        markdown_content = f"""title: {post.get('title', '')}
date: {date}
slug: {slug}

{post.get('html', '')}
"""
        
        # Write to file
        output_file = posts_dir / f"{slug}.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)

if __name__ == "__main__":
    convert_json_to_markdown() 