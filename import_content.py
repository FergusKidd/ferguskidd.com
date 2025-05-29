import json
import os
from app import app, db
from models import Post
from datetime import datetime


def import_ghost_posts():
    json_dir = 'data/json_content'
    ghost_files = [f for f in os.listdir(json_dir) if f.endswith('.json') and 'ghost' in f.lower()]
    if not ghost_files:
        print("No Ghost export file found in the data/json_content directory!")
        return

    with app.app_context():
        for json_file in ghost_files:
            file_path = os.path.join(json_dir, json_file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    ghost_data = json.load(f)
                    posts = ghost_data['db'][0]['data']['posts']
                    imported = 0
                    for item in posts:
                        if item.get('status') != 'published':
                            continue
                        # Skip the post titled 'Me' (case-insensitive) from March 21, 2023
                        if item.get('title', '').lower() == 'me' and item.get('published_at', '').startswith('2023-03-21'):
                            print(f"Skipping post: {item.get('title')} from {item.get('published_at')}")
                            continue
                        post = Post(
                            title=item.get('title', ''),
                            content=item.get('html', ''),
                            date_posted=datetime.fromisoformat(item.get('published_at').replace('Z', '+00:00')) if item.get('published_at') else datetime.utcnow(),
                            slug=item.get('slug', ''),
                            tags='',  # You can enhance this to pull tags if needed
                            category=''  # You can enhance this to pull category if needed
                        )
                        db.session.add(post)
                        imported += 1
                        print(f"Imported post: {post.title}")
                    db.session.commit()
                    print(f"Successfully imported {imported} posts from {json_file}!")
            except Exception as e:
                db.session.rollback()
                print(f"Error processing {json_file}: {str(e)}")

if __name__ == '__main__':
    import_ghost_posts() 