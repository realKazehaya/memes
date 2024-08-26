from flask import Flask, redirect, url_for, session, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
oauth = OAuth(app)

# Configura OAuth para Discord
discord = oauth.register(
    name='discord',
    client_id='1277073573894291589',
    client_secret='g6s0xgeBakZH7QoIcX9sO_grPoU5In7u',
    authorize_url='https://discord.com/api/oauth2/authorize',
    authorize_params=None,
    access_token_url='https://discord.com/api/oauth2/token',
    access_token_params=None,
    refresh_token_url=None,
    redirect_uri='http://localhost:5000/callback',
    client_kwargs={'scope': 'email'}
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

# Rutas de la Aplicación
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    redirect_uri = url_for('authorized', _external=True)
    return discord.authorize_redirect(redirect_uri)

@app.route('/logout')
def logout():
    session.pop('discord_token')
    session.pop('user_id')
    return redirect(url_for('index'))

@app.route('/callback')
def authorized():
    token = discord.authorize_access_token()
    if not token:
        return 'Access denied'

    session['discord_token'] = token
    user_info = discord.parse_id_token(token)
    user_data = user_info['user']
    user = User.query.filter_by(discord_id=user_data['id']).first()
    if user is None:
        user = User(discord_id=user_data['id'],
                    username=user_data['username'],
                    avatar_url=user_data['avatar'])
        db.session.add(user)
        db.session.commit()
    session['user_id'] = user.id
    return redirect(url_for('index'))

@app.route('/ranking')
def ranking():
    top_users = db.session.execute("""
        SELECT u.username, COUNT(l.id) AS like_count
        FROM user u
        JOIN like l ON u.id = l.user_id
        GROUP BY u.id
        ORDER BY like_count DESC
        LIMIT 5
    """).fetchall()
    return render_template('ranking.html', ranking=top_users)

@app.route('/profile/<user_id>')
def profile(user_id):
    user = User.query.get(user_id)
    memes = Meme.query.filter_by(user_id=user_id).all()
    badges = Badge.query.filter_by(user_id=user_id).all()
    return render_template('perfil.html', user=user, memes=memes, badges=badges)

@app.route('/api/memes')
def api_memes():
    memes = Meme.query.all()
    return jsonify({'memes': [{'meme_url': meme.meme_url, 'likes': meme.likes} for meme in memes]})

@app.route('/api/ranking')
def api_ranking():
    top_users = db.session.execute("""
        SELECT u.username, COUNT(l.id) AS like_count
        FROM user u
        JOIN like l ON u.id = l.user_id
        GROUP BY u.id
        ORDER BY like_count DESC
        LIMIT 5
    """).fetchall()
    return jsonify({'ranking': [{'username': user.username, 'like_count': user.like_count} for user in top_users]})

# Crear la base de datos
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Crea la base de datos si no existe
    app.run(debug=True)
