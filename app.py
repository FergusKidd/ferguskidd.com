from flask import Flask, render_template
import os
from dotenv import load_dotenv
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

from extensions import db, migrate

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///blog.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

from models import Post

with app.app_context():
    db.create_all()

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

@app.route('/')
def home():
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    return render_template('home.html', posts=posts)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/post/<slug>')
def post_detail(slug):
    post = Post.query.filter_by(slug=slug).first_or_404()
    return render_template('post_detail.html', post=post)

if __name__ == '__main__':
    app.run(debug=True) 