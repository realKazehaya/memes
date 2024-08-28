#!/bin/bash
# Iniciar la aplicación Flask con Gunicorn
gunicorn app:app &

# Iniciar el bot de Discord
python bot.py
