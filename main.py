# imports
from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from typing import Callable
from functools import wraps
from html_inspector import strip_invalid_html
from dotenv import load_dotenv
import os

# app setup
app = Flask(__name__)
load_dotenv(".env")
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

# LoginManager setup
login_manager = LoginManager()
login_manager.init_app(app)

# init Gravatar
gravatar = Gravatar(app,
                    size=100,
                    rating="g",
                    default="retro",
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None,
                    )


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# database connection
class MySQLAlchemy(SQLAlchemy):
    Column: Callable
    Integer: Callable
    String: Callable
    Text: Callable
    ForeignKey: Callable


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = MySQLAlchemy(app)


# tables config
class BlogPost(db.Model):
    """
    This class(table) is responsible for storing all the data about blog posts
    """
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # creating a relationship(child) with User
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")

    # creating a relationship with Comment
    comments = relationship("Comment", back_populates="")

    def __init__(self, title, subtitle, author, date, body, img_url):
        self.title = title
        self.subtitle = subtitle
        self.author = author
        self.date = date
        self.body = body
        self.img_url = img_url


class User(db.Model, UserMixin):
    """
    This class(table) is responsible for storing users data(e.g. email, etc)
    """
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    name = db.Column(db.String(150), nullable=False)

    # creating a relationship
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="author")

    def __init__(self, email, password, name):
        self.email = email
        self.password = password
        self.name = name


class Comment(db.Model, UserMixin):
    """
    This class(table) is responsible for storing comments in the database
    """
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(150), nullable=False)

    # establishing a relationship with user database
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="comments")

    # establishing a relationship with blogpost database
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")

    def __init__(self, text, author, parent_post):
        self.text = text
        self.author = author
        self.parent_post = parent_post


# code for creating the database
# db.create_all()
# db.session.commit()

# decorator block
def admin_only(current_user_in_decorator):
    """Makes the page only accessible by the admin"""

    def decorator(function):
        @wraps(function)
        def decorated_function(*args, **kwargs):
            if current_user_in_decorator.is_authenticated and current_user_in_decorator.id == 1:
                return function(*args, **kwargs)
            else:
                abort(403)

        return decorated_function

    return decorator


# home page setup
@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, user=current_user)


# register page setup
@app.route('/register', methods=["GET", "POST"])
def register():
    # create a register form
    form = RegisterForm()

    # check to see if the form was submitted
    if form.validate_on_submit():
        # add new user to the database
        try:
            new_user = User(
                email=form.email.data,
                password=generate_password_hash(password=form.password.data, method="pbkdf2:sha3_512:10000",
                                                salt_length=21),
                name=form.name.data,
            )
            db.session.add(new_user)
            db.session.commit()
        except IntegrityError:
            flash("User already exists. Please Log In.")
            return redirect(url_for("login"))

        # log in user
        login_user(new_user, remember=True)

        # redirect to the home page
        return redirect(url_for("get_all_posts"))

    # render the register template
    return render_template("register.html", form=form)


# login page setup
@app.route('/login', methods=["GET", "POST"])
def login():
    # create a new login form
    form = LoginForm()

    # check to see if the form was submitted
    if form.validate_on_submit():
        # get the user from the database
        user = User.query.filter_by(email=form.email.data).first()

        # check to see if the user exists
        if not user:
            flash("Invalid email. Please try again.")
            return redirect(url_for("login"))
        elif not check_password_hash(pwhash=user.password, password=form.password.data):  # check password
            flash("Invalid password. Please try again.")
            return redirect(url_for("login"))

        # login user
        login_user(user, remember=True)

        # redirect to the home page
        return redirect(url_for("get_all_posts"))

    # render the page if form is not validated
    return render_template("login.html", form=form)


# logout page setup
@app.route('/logout')
def logout():
    # log out user
    logout_user()

    # redirect to the home page
    return redirect(url_for('get_all_posts'))


# blog page setup
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    # get the requested post and all the comments, create a wtf form object
    requested_post = BlogPost.query.get(post_id)
    comments = Comment.query.all()
    form = CommentForm()

    # check to see whether the form was submitted
    if form.validate_on_submit():
        # check whether current user is authenticated or not
        if not current_user.is_authenticated:
            flash("Please login or register to comment posts.")
            return redirect(url_for("login"))

        # add new comment to the database
        new_comment = Comment(text=strip_invalid_html(form.comment_editor.data),
                              author=current_user,
                              parent_post=requested_post,
                              )
        db.session.add(new_comment)
        db.session.commit()

    # clear the comment editor
    form.comment_editor.data = ""

    # render html template
    return render_template("post.html", post=requested_post, user=current_user, form=form, comments=comments)


# about page setup
@app.route("/about")
def about():
    return render_template("about.html")


# page for editing posts
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin_only(current_user)
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = strip_invalid_html(edit_form.body.data)
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


# contact page setup
@app.route("/contact")
def contact():
    return render_template("contact.html")


# page for adding new posts
@app.route("/new-post", methods=["GET", "POST"])
@login_required
@admin_only(current_user)
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=strip_invalid_html(form.body.data),
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# delete page setup
@app.route("/delete/<int:post_id>")
@login_required
@admin_only(current_user)
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


# easter egg
@app.route("/love-you")
def easter_egg():
    return render_template("danya.html")


# run config
if __name__ == "__main__":
    app.run(debug=True)
