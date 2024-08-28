import logging
import os
from flask import Flask, redirect, url_for, session, request, render_template, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from werkzeug.utils import secure_filename

# Configurar el registro de errores
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')  # Usa una variable de entorno para el secreto
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database.db')  # Variable de entorno para la DB
db = SQLAlchemy(app)
oauth = OAuth(app)

# Configura la carpeta para subir memes
UPLOAD_FOLDER = 'static/memes'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Asegúrate de que existe la carpeta de memes
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Configura OAuth para Discord
discord_oauth = oauth.register(
    name='discord',
    client_id=os.getenv('DISCORD_CLIENT_ID'),
    client_secret=os.getenv('DISCORD_CLIENT_SECRET'),
    authorize_url='https://discord.com/api/oauth2/authorize',
    access_token_url='https://discord.com/api/oauth2/token',
    redirect_uri='https://memes-9qcu.onrender.com/callback',
    client_kwargs={'scope': 'identify email'}
)

# Modelos de Base de Datos
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    discord_id = db.Column(db.String, unique=True)
    username = db.Column(db.String)
    avatar_url = db.Column(db.String)
    memes = db.relationship('Meme', backref='user', lazy=True)
    badges = db.relationship('Badge', backref='user', lazy=True)

class Meme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    meme_url = db.Column(db.String)
    likes = db.Column(db.Integer, default=0)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    meme_id = db.Column(db.Integer, db.ForeignKey('meme.id'))

class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    badge_name = db.Column(db.String)

# Función para verificar si el archivo subido es válido
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Rutas de la Aplicación
@app.route('/')
def index():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return render_template('index.html', user=user)

@app.route('/login')
def login():
    redirect_uri = url_for('authorized', _external=True)
    return discord_oauth.authorize_redirect(redirect_uri)

@app.route('/logout')
def logout():
    session.pop('discord_token', None)
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/callback')
def authorized():
    try:
        token = discord_oauth.authorize_access_token()
        if not token:
            return 'Access denied', 403

        user_info = discord_oauth.get('https://discord.com/api/v10/users/@me').json()

        app.logger.debug(f'User info received: {user_info}')

        if 'id' not in user_info:
            app.logger.error(f'Error: "id" not found in user_info')
            return 'An error occurred: "id" not found', 500

        user = User.query.filter_by(discord_id=user_info['id']).first()
        if user is None:
            user = User(discord_id=user_info['id'],
                        username=user_info['username'],
                        avatar_url=user_info.get('avatar'))
            db.session.add(user)
            db.session.commit()
        session['user_id'] = user.id
        return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f'Error in /callback: {e}')
        return f'An error occurred: {e}', 500

@app.route('/ranking')
def ranking():
    try:
        top_users = db.session.execute("""
            SELECT u.username, COUNT(l.id) AS like_count
            FROM user u
            JOIN like l ON u.id = l.user_id
            GROUP BY u.id
            ORDER BY like_count DESC
            LIMIT 5
        """).fetchall()
        return render_template('ranking.html', ranking=top_users)
    except Exception as e:
        app.logger.error(f'Error in /ranking: {e}')
        return f'An error occurred: {e}', 500

@app.route('/profile/<user_id>')
def profile(user_id):
    try:
        user_id = int(user_id)  # Asegúrate de que user_id es un entero
        user = User.query.get(user_id)
        memes = Meme.query.filter_by(user_id=user_id).all()
        badges = Badge.query.filter_by(user_id=user_id).all()

        # Calcula el total de likes
        total_likes = sum(meme.likes for meme in memes)

        return render_template('perfil.html', user=user, memes=memes, badges=badges, total_likes=total_likes)
    except Exception as e:
        app.logger.error(f'Error in /profile/{user_id}: {e}')
        return f'An error occurred: {e}', 500

@app.route('/upload_page')
def upload_page():
    if 'user_id' not in session:
        flash('Debes estar logueado para subir un meme', 'error')
        return redirect(url_for('login'))
    return render_template('upload_meme.html')

@app.route('/upload_meme', methods=['POST'])
def upload_meme():
    if 'user_id' not in session:
        flash('Debes estar logueado para subir un meme', 'error')
        return redirect(url_for('login'))

    user_id = session['user_id']
    if 'meme' not in request.files:
        flash('No se seleccionó ningún archivo', 'error')
        return redirect(url_for('profile', user_id=user_id))

    file = request.files['meme']
    if file.filename == '':
        flash('Nombre de archivo vacío', 'error')
        return redirect(url_for('profile', user_id=user_id))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        meme_url = f'static/memes/{filename}'
        meme = Meme(user_id=user_id, meme_url=meme_url)
        db.session.add(meme)
        db.session.commit()

        flash('Meme subido exitosamente', 'success')
        return redirect(url_for('profile', user_id=user_id))
    else:
        flash('El archivo seleccionado no es válido', 'error')
        return redirect(url_for('profile', user_id=user_id))

if __name__ == '__main__':
    app.run(debug=True)
