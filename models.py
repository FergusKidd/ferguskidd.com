from app import db
from datetime import datetime

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    tags = db.Column(db.String(200))
    category = db.Column(db.String(100))

    def __repr__(self):
        return f"Post('{self.title}', '{self.date_posted}')" 