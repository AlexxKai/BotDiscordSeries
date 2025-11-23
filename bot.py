import json
import requests
import discord
from discord.ext import commands
import os
from datetime import datetime
from threading import Thread
from flask import Flask

# KeepAlive con Flask
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot Kai está activo!", 200


@app.route("/health")
def health():
    return {"status": "alive", "timestamp": datetime.now().isoformat()}, 200


def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    server = Thread(target=run_flask)
    server.daemon = True
    server.start()
    print(f"✅ Servidor HTTP iniciado en puerto {os.environ.get('PORT', 5000)}")


intents = discord.Intents.default()
intents.message_content = True  # Solo si activaste en el portal

bot = commands.Bot(command_prefix="!", intents=intents)

# Estructura para guardar progreso: {usuario : {serie: {temporada,capitulo,estado}}}
progresos = {}


@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")

    # Lista de canales donde quieres fijar el mensaje (pon los IDs reales)
    canales_ids = [
        1440123514651803750,  # Canal 1
        # Canal 2 234567890123456789,  
        # Añade más IDs si quieres, por ejemplo para varios servidores o categorías
    ]

    mensaje_texto = "Pon el comando `!ayuda` para saber qué hacer."

    for canal_id in canales_ids:
        canal = bot.get_channel(canal_id)
        if canal:
            try:
                # Obtener mensajes fijados actuales
                mensajes_fijados = await canal.pins()

                # Desfijar y borrar mensajes antiguos con el mismo texto para evitar duplicados
                for msg in mensajes_fijados:
                    if msg.author == bot.user and msg.content == mensaje_texto:
                        try:
                            await msg.unpin()
                            await msg.delete()
                        except Exception as e:
                            print(f"Error al quitar mensaje fijado antiguo en canal {canal.name}: {e}")

                # Enviar y fijar nuevo mensaje
                mensaje = await canal.send(mensaje_texto)
                await mensaje.pin()
                print(f"Mensaje fijado en el canal {canal.name}")

            except Exception as e:
                print(f"Error gestionando canal {canal_id}: {e}")
        else:
            print(f"Canal con ID {canal_id} no encontrado")



# Añadimos serie
@bot.command(name="addserie")
async def add_serie(ctx, nombre_serie):
    user = str(ctx.author)
    if user not in progresos:
        progresos[user] = {}
    if nombre_serie in progresos[user]:
        await ctx.send(f"La serie {nombre_serie} ya está en tu lista.")
    else:
        progresos[user][nombre_serie] = {
            "temporada": 0,
            "capitulo": 0,
            "estado": "En progreso",
        }
        await ctx.send(f"Serie {nombre_serie} añadida a tu lista.")


# Actualizamos capitulo y temporada
@bot.command(name="actualizar")
async def update_capitulo(ctx, nombre_serie, temporada: int, capitulo: int):
    user = str(ctx.author)
    if user in progresos and nombre_serie in progresos[user]:
        progresos[user][nombre_serie]["temporada"] = temporada
        progresos[user][nombre_serie]["capitulo"] = capitulo
        progresos[user][nombre_serie]["estado"] = "En progreso"
        await ctx.send(
            f"Actualizado {nombre_serie}: Temporada {temporada}, Capítulo {capitulo}"
        )
    else:
        await ctx.send(f"Primero añade la serie con !addserie {nombre_serie}")


# Marcamos serie como completada
@bot.command(name="completada")
async def mark_complete(ctx, nombre_serie):
    user_id = str(ctx.author)
    if user_id not in progresos:
        await ctx.send(f"Primero añade la serie con !addserie {nombre_serie}")
        return

    pendientes = progresos[user_id]["pendientes"]
    completadas = progresos[user_id]["completadas"]
    for i, s in enumerate(pendientes):
        if s["name"].lower() == nombre_serie.lower():
            s["estado"] = "Completada"
            completadas.append(s)
            pendientes.pop(i)
            await ctx.send(f"Marcaste la serie {nombre_serie} como completada.")
            return

    await ctx.send(f"No encontré la serie {nombre_serie} en pendientes. Usa !addserie para añadirla.")



# Consultamos el estado
@bot.command(name="miestado")
async def mi_estado(ctx):
    user_id = str(ctx.author)
    if user_id not in progresos or (not progresos[user_id]["pendientes"] and not progresos[user_id]["completadas"]):
        await ctx.send("No has registrado ninguna serie todavía.")
        return

    embed = discord.Embed(title=f"Progreso de {ctx.author.name}", color=0x3498db)

    def format_serie(s):
        return f"Temporada {s['temporada']} Capítulo {s['capitulo']} - {s['estado']}"
    
    if progresos[user_id]["pendientes"]:
        texto_pendientes = ""
        for s in progresos[user_id]["pendientes"]:
            texto_pendientes += f"**{s['name']}**\n{format_serie(s)}\n\n"
        embed.add_field(name="Pendientes / En progreso", value=texto_pendientes, inline=False)

    if progresos[user_id]["completadas"]:
        texto_completadas = ""
        for s in progresos[user_id]["completadas"]:
            texto_completadas += f"**{s['name']}**\n{format_serie(s)}\n\n"
        embed.add_field(name="Completadas", value=texto_completadas, inline=False)

    # Opcional: agregar imagenes de las series (solo la primera como ejemplo)
    if progresos[user_id]["pendientes"]:
        imagen = progresos[user_id]["pendientes"][0]["image"]
        if imagen:
            embed.set_thumbnail(url=imagen)
    elif progresos[user_id]["completadas"]:
        imagen = progresos[user_id]["completadas"][0]["image"]
        if imagen:
            embed.set_thumbnail(url=imagen)

    await ctx.send(embed=embed)



# Guardamos y cargamos el progreso en json
def guardar_progresos():
    with open("progresos.json", "w") as f:
        json.dump(progresos, f)


def cargar_progresos():
    global progresos
    try:
        with open("progresos.json", "r") as f:
            progresos = json.load(f)
    except FileNotFoundError:
        progresos = {}


# Borramos serie
@bot.command(name="deleteserie")
async def delete_serie(ctx, nombre_serie):
    user = str(ctx.author)
    if user in progresos and nombre_serie in progresos[user]:
        del progresos[user][nombre_serie]
        guardar_progresos()
        await ctx.send(f"Serie {nombre_serie} eliminada de tu lista.")
    else:
        await ctx.send("Esa serie no está en tu lista.")


# Listamos series
@bot.command(name="listseries")
async def list_series(ctx):
    user = str(ctx.author)
    if user in progresos and progresos[user]:
        lista = ", ".join(progresos[user].keys())
        await ctx.send(f"Tus series: {lista}")
    else:
        await ctx.send("No tienes series registradas.")


# Comando de ayuda
@bot.command(name="ayuda")
async def ayuda(ctx):
    mensaje_ayuda = (
        "😁  Aquí tienes la lista de comandos disponibles: 😁\n"
        "➕  !addserie <nombre> - Añade una serie a tu lista.\n"
        "☝🏾  !actualizar <nombre> <temporada> <capítulo> - Actualiza tu progreso.\n"
        "👌🏾  !completada <nombre> - Marca la serie como completada.\n"
        "🤔  !miestado - Muestra tu progreso actual.\n"
        "❌  !deleteserie <nombre> - Elimina una serie de tu lista.\n"
        "📝  !listseries - Lista todas tus series guardadas.\n"
        "🔎  !buscar - Busca la serie que indiques.\n"
    )
    await ctx.send(mensaje_ayuda)


# apikey del buscador
API_KEY = "54157f0247cd582245af02be17b7aee3"


def buscar_series(nombre, max_resultados=5):
    url = f"https://api.themoviedb.org/3/search/tv?api_key={API_KEY}&query={nombre}"
    response = requests.get(url)
    if response.status_code == 200:
        resultados = response.json().get("results")
        if resultados:
            return [
                {
                    "name": serie["name"],
                    "year": serie["first_air_date"][:4] if serie["first_air_date"] else "N/A",
                    "image": f'https://image.tmdb.org/t/p/w500{serie["poster_path"]}' if serie.get("poster_path") else None
                }
                for serie in resultados[:max_resultados]
            ]
    return []



# Buscamos una serie especifica
@bot.command(name='buscar')
async def buscar(ctx, *, nombre_serie: str):
    resultados = buscar_series(nombre_serie)
    if not resultados:
        await ctx.send('No se encontraron series con ese nombre.')
        return

    emojis = ["0️⃣","1️⃣","2️⃣","3️⃣","4️⃣","5️⃣"]
    max_opciones = min(len(resultados), 5)

    opciones_texto = ""
    for i in range(max_opciones):
        opciones_texto += f"{emojis[i+1]} {resultados[i]['name']} ({resultados[i]['year']})\n"
    opciones_texto += f"{emojis[0]} Cancelar búsqueda\n\nSelecciona reaccionando con el emoji."

    embed = discord.Embed(title="Resultados encontrados", description=opciones_texto, color=0x1abc9c)
    await ctx.send(embed=embed)
    mensaje = await ctx.send("Selecciona la opción:")

    for i in range(max_opciones + 1):
        await mensaje.add_reaction(emojis[i])

    def check(reaction, user):
        return (
            user == ctx.author
            and reaction.message.id == mensaje.id
            and str(reaction.emoji) in emojis[:max_opciones+1]
        )

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=120.0, check=check)
    except asyncio.TimeoutError:
        await mensaje.edit(content="⏰ Tiempo de selección agotado. Usa !buscar para intentarlo de nuevo.")
        await mensaje.clear_reactions()
        return

    try:
        await mensaje.clear_reactions()
    except discord.Forbidden:
        pass

    if str(reaction.emoji) == emojis[0]:
        await ctx.send("Búsqueda cancelada.")
        return

    opcion = emojis.index(str(reaction.emoji))
    serie_seleccionada = resultados[opcion-1]

    user_id = str(ctx.author)
    if user_id not in progresos:
        progresos[user_id] = {"pendientes": [], "completadas": []}

    # Verificar que no esté en ninguna lista
    all_series = progresos[user_id]["pendientes"] + progresos[user_id]["completadas"]
    if any(s["name"].lower() == serie_seleccionada["name"].lower() for s in all_series):
        await ctx.send(f'La serie "{serie_seleccionada["name"]}" ya está en tu lista.')
        return
    
    # Añadir a pendientes por defecto
    progresos[user_id]["pendientes"].append({
        "name": serie_seleccionada["name"],
        "temporada": 0,
        "capitulo": 0,
        "estado": "En progreso",
        "image": serie_seleccionada["image"]
    })

    await ctx.send(f'Serie "{serie_seleccionada["name"]}" añadida a tu lista de pendientes.')



        
        
        
# Token del bot
TOKEN = os.getenv("DISCORD_TOKEN")
keep_alive()
bot.run(TOKEN)
