import logging
import os
from flask import Flask, redirect, url_for, session, request, render_template, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect

# Configurar el registro de errores
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')  # Usa una variable de entorno para el secreto
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database.db')  # Variable de entorno para la DB
db = SQLAlchemy(app)
oauth = OAuth(app)
csrf = CSRFProtect(app)

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
    avatar_url = db.Column(db.String, default='static/avatars/default-avatar.png')  # Valor predeterminado para el avatar
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
    
    try:
        # Obtener todos los memes para mostrar en la página de inicio
        memes = Meme.query.order_by(Meme.id.desc()).all()

        # Obtener todos los usuarios relacionados a los memes
        user_ids = {meme.user_id for meme in memes}
        users = {user.id: user for user in User.query.filter(User.id.in_(user_ids)).all()}

        return render_template('index.html', user=user, memes=memes, users=users)
    except Exception as e:
        app.logger.error(f'Error al obtener memes: {e}')
        return 'Ocurrió un error al cargar los memes', 500

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
        if not user:
            user = User(
                discord_id=user_info['id'],
                username=user_info['username'],
                avatar_url=f'https://cdn.discordapp.com/avatars/{user_info["id"]}/{user_info["avatar"]}.png'
            )
            db.session.add(user)
            db.session.commit()
        
        session['user_id'] = user.id
        session['discord_token'] = token

        return redirect(url_for('profile', user_id=user.id))

    except Exception as e:
        app.logger.error(f'Exception occurred during OAuth callback: {e}')
        return f'An error occurred during login: {str(e)}', 500

@app.route('/profile/<int:user_id>')
def profile(user_id):
    user = User.query.get_or_404(user_id)
    memes = Meme.query.filter_by(user_id=user.id).all()
    badges = Badge.query.filter_by(user_id=user.id).all()
    total_likes = sum(meme.likes for meme in memes)
    return render_template('perfil.html', user=user, memes=memes, badges=badges, total_likes=total_likes)

@app.route('/upload_meme', methods=['POST'])
@csrf.exempt  # Excluir del CSRF en esta ruta si no se está usando en el frontend
def upload_meme():
    if 'user_id' not in session:
        flash('No estás autenticado')
        return redirect(url_for('index'))

    user_id = session['user_id']
    user = User.query.get(user_id)

    if not user:
        flash('Usuario no encontrado')
        return redirect(url_for('index'))

    if 'meme' not in request.files:
        flash('No se seleccionó un archivo')
        return redirect(request.referrer)

    file = request.files['meme']

    if file.filename == '':
        flash('No se seleccionó un archivo')
        return redirect(request.referrer)

    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            meme = Meme(user_id=user.id, meme_url=f'memes/{filename}')
            db.session.add(meme)
            db.session.commit()

            return redirect(url_for('profile', user_id=user.id))
        except Exception as e:
            app.logger.error(f'Error al guardar el meme: {e}')
            flash('Error al guardar el meme')
            return redirect(request.referrer)

    flash('Archivo no permitido')
    return redirect(request.referrer)

@app.route('/ranking')
def ranking():
    try:
        # Consulta a la base de datos para obtener los 5 usuarios con más likes en sus memes
        ranking_data = db.session.query(User, db.func.sum(Meme.likes).label('total_likes')).join(Meme).group_by(User.id).order_by(db.desc('total_likes')).limit(5).all()
        
        # Formatea los datos para pasarlos al template
        ranking_list = [{
            'username': user.username,
            'total_likes': total_likes
        } for user, total_likes in ranking_data]

        return render_template('ranking.html', ranking=ranking_list)
    except Exception as e:
        app.logger.error(f'Error al obtener el ranking: {e}')
        return 'Ocurrió un error al cargar el ranking', 500

@app.route('/api/meme/<int:meme_id>', methods=['GET'])
def get_meme(meme_id):
    meme = Meme.query.get(meme_id)
    if not meme:
        return jsonify({'error': 'Meme no encontrado'}), 404

    user = User.query.get(meme.user_id)
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    return jsonify({
        'meme_url': url_for('static', filename=meme.meme_url),
        'avatar_url': user.avatar_url,
        'username': user.username,
        'likes': meme.likes
    })

@app.route('/api/like', methods=['POST'])
def like_meme():
    meme_id = request.form.get('meme_id')
    if not meme_id:
        return jsonify({'error': 'Meme ID es requerido'}), 400

    meme = Meme.query.get(meme_id)
    if not meme:
        return jsonify({'error': 'Meme no encontrado'}), 404

    meme.likes += 1
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/otorgar_insignia', methods=['POST'])
@csrf.exempt  # Excluir del CSRF en esta ruta si no se está usando en el frontend
def otorgar_insignia():
    data = request.get_json()
    user_id = data.get('user_id')
    badge_name = data.get('badge_name')

    if not badge_name or not badge_name.isalnum():  # Verifica si el nombre de la insignia es seguro
        return jsonify({'error': 'Nombre de insignia inválido'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404

    try:
        badge = Badge(user_id=user.id, badge_name=badge_name)
        db.session.add(badge)
        db.session.commit()
        return jsonify({'success': 'Insignia otorgada exitosamente'}), 200
    except Exception as e:
        app.logger.error(f'Error al otorgar la insignia: {e}')
        return jsonify({'error': 'Error al otorgar la insignia'}), 500

if __name__ == '__main__':
    app.run(debug=True)