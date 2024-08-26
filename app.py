import logging
import os
from flask import Flask, redirect, url_for, session, request, render_template, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from werkzeug.utils import secure_filename

# Configurar el registro de errores
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
oauth = OAuth(app)

# Configura la carpeta para subir memes
UPLOAD_FOLDER = 'static/memes'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Asegúrate de que existe la carpeta de memes
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Configura OAuth para Discord
discord = oauth.register(
    name='discord',
    client_id='1277073573894291589',
    client_secret='g6s0xgeBakZH7QoIcX9sO_grPoU5In7u',
    authorize_url='https://discord.com/api/oauth2/authorize',
    access_token_url='https://discord.com/api/oauth2/token',
    redirect_uri='https://memes-9qcu.onrender.com/callback',
    client_kwargs={'scope': 'identify email'}  # Actualiza el scope para incluir 'identify'
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
    return discord.authorize_redirect(redirect_uri)

@app.route('/logout')
def logout():
    session.pop('discord_token', None)
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/callback')
def authorized():
    try:
        token = discord.authorize_access_token()
        if not token:
            return 'Access denied', 403

        user_info = discord.get('https://discord.com/api/v10/users/@me').json()
        
        # Log para ver el contenido de user_info
        app.logger.debug(f'User info received: {user_info}')

        # Verifica si 'id' está en user_info
        if 'id' not in user_info:
            app.logger.error(f'Error: "id" not found in user_info')
            return 'An error occurred: "id" not found', 500

        user = User.query.filter_by(discord_id=user_info['id']).first()
        if user is None:
            user = User(discord_id=user_info['id'],
                        username=user_info['username'],
                        avatar_url=user_info.get('avatar'))  # Usa .get() por si 'avatar' no está presente
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
        user = User.query.get(user_id)
        memes = Meme.query.filter_by(user_id=user_id).all()
        badges = Badge.query.filter_by(user_id=user_id).all()
        return render_template('perfil.html', user=user, memes=memes, badges=badges)
    except Exception as e:
        app.logger.error(f'Error in /profile/{user_id}: {e}')
        return f'An error occurred: {e}', 500

# Ruta para subir memes
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

        # Guardar el meme en la base de datos
        meme_url = f'static/memes/{filename}'
        meme = Meme(user_id=user_id, meme_url=meme_url)
        db.session.add(meme)
        db.session.commit()

        flash('Meme subido exitosamente', 'success')
        return redirect(url_for('profile', user_id=user_id))
    else:
        flash('Archivo no permitido', 'error')
        return redirect(url_for('profile', user_id=user_id))

@app.route('/api/memes')
def api_memes():
    try:
        memes = Meme.query.all()
        return jsonify({'memes': [{'id': meme.id, 'meme_url': meme.meme_url, 'likes': meme.likes} for meme in memes]})
    except Exception as e:
        app.logger.error(f'Error in /api/memes: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/like/<int:meme_id>', methods=['POST'])
def like_meme(meme_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Debes iniciar sesión para dar like'}), 403

    user_id = session['user_id']
    existing_like = Like.query.filter_by(user_id=user_id, meme_id=meme_id).first()
    if existing_like:
        return jsonify({'error': 'Ya has dado like a este meme'}), 400

    new_like = Like(user_id=user_id, meme_id=meme_id)
    meme = Meme.query.get(meme_id)
    meme.likes += 1

    db.session.add(new_like)
    db.session.commit()

    return jsonify({'message': 'Like registrado', 'likes': meme.likes})

@app.route('/api/ranking')
def api_ranking():
    try:
        top_users = db.session.execute("""
            SELECT u.username, COUNT(l.id) AS like_count
            FROM user u
            JOIN like l ON u.id = l.user_id
            GROUP BY u.id
            ORDER BY like_count DESC
            LIMIT 5
        """).fetchall()
        return jsonify({'ranking': [{'username': user.username, 'like_count': user.like_count} for user in top_users]})
    except Exception as e:
        app.logger.error(f'Error in /api/ranking: {e}')
        return jsonify({'error': str(e)}), 500

# Crear la base de datos
if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()  # Crea la base de datos si no existe
            app.logger.info('Database created successfully.')
        except Exception as e:
            app.logger.error(f'Error creating database: {e}')
    app.run(debug=True)
