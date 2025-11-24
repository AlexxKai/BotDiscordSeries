import json
import requests
import discord
import asyncio
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
        1442214865438638130,  # Canal 1
        # Canal 2 234567890123456789,  
        # Añade más IDs para varios servidores o categorías, pero a ver como en auto xq sino no funciona TODO
    ]

    mensaje_texto = "Pon el comando `!ayuda` para saber qué hacer."

    for canal_id in canales_ids:
        canal = bot.get_channel(canal_id)
        if canal:
            try:
                # Obtener mensajes fijados actuales
                mensajes_fijados = []
                async for msg in canal.pins():
                    mensajes_fijados.append(msg)

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



# Añadimos serie de forma manual, aunque no este en el registro de la API
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

    # Agregar imagenes de las series, ahora solo la primera, TODO
    if progresos[user_id]["pendientes"]:
        imagen = progresos[user_id]["pendientes"][0]["image"]
        if imagen:
            embed.set_thumbnail(url=imagen)
    elif progresos[user_id]["completadas"]:
        imagen = progresos[user_id]["completadas"][0]["image"]
        if imagen:
            embed.set_thumbnail(url=imagen)

    await ctx.send(embed=embed)



# Guardamos y cargamos el progreso en json, solo funciona en local
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
@bot.command(name="borrarserie")
async def delete_serie(ctx, *, nombre_serie: str):
    user = str(ctx.author)
    if user in progresos:
        pendientes = progresos[user].get("pendientes", [])
        completadas = progresos[user].get("completadas", [])

        # Buscamos en pendientes
        for i, serie in enumerate(pendientes):
            if serie["name"].lower() == nombre_serie.lower():
                pendientes.pop(i)
                guardar_progresos()
                await ctx.send(f"Serie {nombre_serie} eliminada de tu lista (pendientes).")
                return

        # Buscamos en completadas        
        for i, serie in enumerate(completadas):
            if serie["name"].lower() == nombre_serie.lower():
                completadas.pop(i)
                guardar_progresos()
                await ctx.send(f"Serie {nombre_serie} eliminada de tu lista (completadas).")
                return

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


# Comando de ayuda TODO
@bot.command(name="ayuda")
async def ayuda(ctx):
    mensaje_ayuda = (
        "😁  Aquí tienes la lista de comandos disponibles: 😁\n"
        "➕  !addserie <nombre> - Añade una serie a tu lista.\n"
        "☝🏾  !actualizar <nombre> <temporada> <capítulo> - Actualiza tu progreso.\n"
        "👌🏾  !completada <nombre> - Marca la serie como completada.\n"
        "🤔  !miestado - Muestra tu progreso actual.\n"
        "❌  !borrarserie <nombre> - Elimina una serie de tu lista.\n"
        "📝  !listseries - Lista todas tus series guardadas.\n"
        "🔎  !buscar <texto> - Busca la serie que indiques.\n"
    )
    await ctx.send(mensaje_ayuda)


# apikey del buscador
API_KEY = "54157f0247cd582245af02be17b7aee3"

def buscar_series(nombre):
    url = f"https://api.themoviedb.org/3/search/tv?api_key={API_KEY}&query={nombre}&language=es-ES"
    response = requests.get(url)
    if response.status_code == 200:
        resultados = response.json().get("results")
        if resultados:
            return [
                {
                    "name": serie["name"],
                    "year": serie["first_air_date"][:4] if serie.get("first_air_date") else "N/A",
                    "image": f'https://image.tmdb.org/t/p/w500{serie["poster_path"]}' if serie.get("poster_path") else None,
                    "vote_average": serie.get("vote_average", 0.0)
                }
                for serie in resultados
            ]
    return []

page_size = 5
numeros = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
otros = ["⬅️", "➡️", "0️⃣"]

def crear_embed_unico(resultados, pagina):
    start = pagina * page_size
    end = start + page_size
    opciones = resultados[start:end]

    embed = discord.Embed(
        title=f"Resultados encontrados (página {pagina+1}/{(len(resultados)-1)//page_size + 1})",
        color=0x1abc9c
    )

    texto = ""
    for i, serie in enumerate(opciones):
        puntuacion = serie.get("vote_average", 0.0)
        puntuacion_fmt = f"{puntuacion:.1f}" if isinstance(puntuacion, (float, int)) else "N/A"
        imagen_url = serie.get("image") or "https://via.placeholder.com/50x70?text=NA"
        
        texto += f"{numeros[i]} **[{serie['name']}]({imagen_url})** - ⭐ {puntuacion_fmt}\n"

    embed.description = texto
    embed.set_footer(text="Selecciona con las reacciones. ⬅️ y ➡️ para navegar páginas. 0️⃣ para cancelar.")
    return embed, len(opciones)

@bot.command(name='buscar')
async def buscar(ctx, *, nombre_serie: str = None):
    if not nombre_serie:
        await ctx.send("Debes escribir el nombre de la serie después del comando, por ejemplo:\n`!buscar Friends`")
        return

    try:
        resultados = buscar_series(nombre_serie)
    except Exception as e:
        await ctx.send(f"Error consultando la API: {e}")
        return

    if not resultados:
        await ctx.send("No se encontraron series con ese nombre.")
        return

    user_id = str(ctx.author)
    if user_id not in progresos:
        progresos[user_id] = {"pendientes": [], "completadas": []}

    total_pages = (len(resultados) - 1) // page_size + 1
    pagina_actual = 0

    try:
        embed, total_opciones = crear_embed_unico(resultados, pagina_actual)
        mensaje = await ctx.send(embed=embed)

        opciones_emoji = numeros[:total_opciones] + otros
        for emoji in opciones_emoji:
            await mensaje.add_reaction(emoji)
            await asyncio.sleep(0.3)

        def check(reaction, user):
            return (
                user == ctx.author and
                reaction.message.id == mensaje.id and
                str(reaction.emoji) in opciones_emoji
            )

        while True:
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=120.0, check=check)
            except asyncio.TimeoutError:
                await mensaje.clear_reactions()
                await ctx.send("⏰ Tiempo de selección agotado. Usa !buscar para intentarlo de nuevo.")
                return

            emoji = str(reaction.emoji)
            await mensaje.remove_reaction(reaction.emoji, user)

            if emoji == "0️⃣":
                await mensaje.clear_reactions()
                await ctx.send("Búsqueda cancelada.")
                return

            elif emoji == "➡️" and pagina_actual < total_pages - 1:
                pagina_actual += 1
            elif emoji == "⬅️" and pagina_actual > 0:
                pagina_actual -= 1
            elif emoji in numeros:
                idx = numeros.index(emoji)
                start = pagina_actual * page_size
                if start + idx < len(resultados):
                    serie_seleccionada = resultados[start + idx]
                    all_series = progresos[user_id]["pendientes"] + progresos[user_id]["completadas"]
                    if any(s["name"].lower() == serie_seleccionada["name"].lower() for s in all_series):
                        await ctx.send(f'La serie "{serie_seleccionada["name"]}" ya está en tu lista.')
                    else:
                        progresos[user_id]["pendientes"].append({
                            "name": serie_seleccionada["name"],
                            "temporada": 0,
                            "capitulo": 0,
                            "estado": "En progreso",
                            "image": serie_seleccionada["image"]
                        })
                        guardar_progresos()
                        await ctx.send(f'Serie "{serie_seleccionada["name"]}" añadida a tu lista de pendientes.')
                    await mensaje.clear_reactions()
                    return

            embed, total_opciones = crear_embed_unico(resultados, pagina_actual)
            await mensaje.edit(embed=embed)

            opciones_emoji = numeros[:total_opciones] + otros
            await mensaje.clear_reactions()
            for e in opciones_emoji:
                await mensaje.add_reaction(e)
                await asyncio.sleep(0.3)  # Pausa para evitar rate limited

    except Exception as e:
        await ctx.send(f"Error en la interacción: {e}")

   
# Token del bot
TOKEN = os.getenv("DISCORD_TOKEN")
keep_alive()
bot.run(TOKEN)
