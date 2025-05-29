from app import app, db
from models import Post

with app.app_context():
    posts = Post.query.all()
    print(f"Found {len(posts)} posts.")
    for post in posts:
        print(f"- {post.title} (slug: {post.slug})") 