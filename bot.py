import json
import requests
import discord
from discord.ext import commands
import os
from datetime import datetime
from threading import Thread
from flask import Flask

#KeepAlive con Flask
app = Flask(__name__)
 
@app.route('/')
def home():
    return "Bot Kai está activo! 🎴", 200
 
@app.route('/health')
def health():
    return {"status": "alive", "timestamp": datetime.now().isoformat()}, 200
 
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
 
def keep_alive():
    server = Thread(target=run_flask)
    server.daemon = True
    server.start()
    print(f"✅ Servidor HTTP iniciado en puerto {os.environ.get('PORT', 5000)}")
 
 

intents = discord.Intents.default()
intents.message_content = True  # Solo si activaste en el portal

bot = commands.Bot(command_prefix='!', intents=intents)

# Estructura para guardar progreso: {usuario : {serie: {temporada,capitulo,estado}}}
progresos = {}

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')

# Añadimos serie
@bot.command(name='addserie')
async def add_serie(ctx, nombre_serie):
    user = str(ctx.author)
    if user not in progresos:
        progresos[user] = {}
    if nombre_serie in progresos[user]:
        await ctx.send(f'La serie {nombre_serie} ya está en tu lista.')
    else:
        progresos[user][nombre_serie] = {'temporada':0, 'capitulo':0, 'estado':'En progreso'}
        await ctx.send(f'Serie {nombre_serie} añadida a tu lista.')

# Actualizamos capitulo y temporada
@bot.command(name='updatecap')
async def update_capitulo(ctx, nombre_serie, temporada:int, capitulo:int):
    user = str(ctx.author)
    if user in progresos and nombre_serie in progresos[user]:
        progresos[user][nombre_serie]['temporada'] = temporada
        progresos[user][nombre_serie]['capitulo'] = capitulo
        progresos[user][nombre_serie]['estado'] = 'En progreso'
        await ctx.send(f'Actualizado {nombre_serie}: Temporada {temporada}, Capítulo {capitulo}')
    else:
        await ctx.send(f'Primero añade la serie con !addserie {nombre_serie}')

# Marcamos serie como completada
@bot.command(name='markcomplete')
async def mark_complete(ctx, nombre_serie):
    user = str(ctx.author)
    if user in progresos and nombre_serie in progresos[user]:
        progresos[user][nombre_serie]['estado'] = 'Completada'
        await ctx.send(f'Marcaste la serie {nombre_serie} como completada.')
    else:
        await ctx.send(f'Primero añade la serie con !addserie {nombre_serie}')


# Consultamos el estado
@bot.command(name='miestado')
async def mi_estado(ctx):
    user = str(ctx.author)
    if user in progresos:
        mensaje = 'Tu progreso en series:\n'
        for serie, datos in progresos[user].items():
            mensaje += f"{serie}: Temporada {datos['temporada']} Capítulo {datos['capitulo']} - {datos['estado']}\n"
        await ctx.send(mensaje)
    else:
        await ctx.send('No has registrado ninguna serie todavía.')

# Guardamos y cargamos el progreso en json
def guardar_progresos():
    with open('progresos.json', 'w') as f:
        json.dump(progresos, f)

def cargar_progresos():
    global progresos
    try:
        with open('progresos.json', 'r') as f:
            progresos = json.load(f)
    except FileNotFoundError:
        progresos = {}
        
# Borramos serie
@bot.command(name='deleteserie')
async def delete_serie(ctx, nombre_serie):
    user = str(ctx.author)
    if user in progresos and nombre_serie in progresos[user]:
        del progresos[user][nombre_serie]
        guardar_progresos()
        await ctx.send(f'Serie {nombre_serie} eliminada de tu lista.')
    else:
        await ctx.send('Esa serie no está en tu lista.')

# Listamos series
@bot.command(name='listseries')
async def list_series(ctx):
    user = str(ctx.author)
    if user in progresos and progresos[user]:
        lista = ', '.join(progresos[user].keys())
        await ctx.send(f'Tus series: {lista}')
    else:
        await ctx.send('No tienes series registradas.')

# Comando de ayuda
@bot.command(name='ayuda')
async def ayuda(ctx):
    mensaje_ayuda = (
        "Aquí tienes la lista de comandos disponibles:\n"
        "!addserie <nombre> - Añade una serie a tu lista.\n"
        "!updatecap <nombre> <temporada> <capítulo> - Actualiza tu progreso.\n"
        "!markcomplete <nombre> - Marca la serie como completada.\n"
        "!miestado - Muestra tu progreso actual.\n"
        "!deleteserie <nombre> - Elimina una serie de tu lista.\n"
        "!listseries - Lista todas tus series guardadas.\n"
        "!buscar - Busca la serie que indiques.\n"
    )
    await ctx.send(mensaje_ayuda)


# apikey del buscador
API_KEY = '54157f0247cd582245af02be17b7aee3'

def buscar_serie(nombre):
    url = f'https://api.themoviedb.org/3/search/tv?api_key={API_KEY}&query={nombre}'
    response = requests.get(url)
    if response.status_code == 200:
        resultados = response.json().get('results')
        if resultados:
            return resultados[0]['name'], resultados[0]['first_air_date']
    return None, None

# Buscamos una serie especifica
@bot.command(name='buscar')
async def buscar(ctx, *, nombre_serie: str):
    nombre, fecha = buscar_serie(nombre_serie)
    if nombre and fecha:
        await ctx.send(f'Serie encontrada: {nombre}\nFecha de estreno: {fecha}')
    else:
        await ctx.send('No se encontró ninguna serie con ese nombre.')
        
        
# Token del bot
TOKEN=os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)