import discord
from discord.ext import commands
from discord.ui import View, Button
import asyncio
import json
import random
from collections import Counter

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

try:
    with open("players.json", "r") as f:
        players = json.load(f)
except FileNotFoundError:
    players = {}

def save_data(data):
    with open("players.json", "w") as f:
        json.dump(data, f, indent=4)

def create_player(uid, name):
    players[uid] = {
        "name": name,
        "hp": 100,
        "atk": 10,
        "lvl": 1,
        "xp": 0,
        "inventory": ["Potion"],
        "location": "camp",
        "walking": False,
        "max_hp": 100,
        "gold": 100
    }
    save_data(players)

SHOP_ITEMS = {
    "Potion": {"price": 50, "description": "Restaure 30 HP."},
    "Épée En Bois": {"price": 200, "description": "Augmente l'attaque de 5."},
    "Armure Légère": {"price": 300, "description": "Augmente les PV max de 20."}
}

@bot.command()
async def start(ctx):
    uid = str(ctx.author.id)
    if uid in players:
        return await ctx.send("Tu as déjà commencé.")
    create_player(uid, ctx.author.name)
    await ctx.send("Bienvenue dans l'aventure !")

@bot.command()
async def stats(ctx):
    uid = str(ctx.author.id)
    if uid not in players:
        return await ctx.send("Fais `!start` d'abord.")
    p = players[uid]

    for key, default in {"max_hp": 100, "atk": 10, "lvl": 1, "xp": 0, "location": "camp", "walking": False, "gold": 100}.items():
        if key not in p:
            p[key] = default
    save_data(players)

    embed = discord.Embed(title=f"📊 Stats de {p['name']}", color=0x2ecc71)
    embed.add_field(name="HP", value=f"{p['hp']} / {p['max_hp']}")
    embed.add_field(name="ATK", value=p["atk"])
    embed.add_field(name="Niveau", value=p["lvl"])
    embed.add_field(name="XP", value=f"{p['xp']}/100")
    embed.add_field(name="Gold", value=p["gold"])
    embed.add_field(name="Localisation", value=p["location"])
    await ctx.send(embed=embed)

class FightView(View):
    def __init__(self, player_id, players):
        super().__init__(timeout=60)
        self.player_id = player_id
        self.players = players
        self.player = players[player_id]
        self.logs = []

        location = self.player.get("location", "camp")

        if location == "ville":
            level = random.randint(2, 6)
            self.enemy = {
                "name": f"Aventurier Lv{level}",
                "hp": 40 + level * 12,
                "max_hp": 40 + level * 12,
                "atk": 8 + level * 3,
                "lvl": level
            }
        else:
            level = random.randint(1, 5)
            self.enemy = {
                "name": f"Goblin Lv{level}",
                "hp": 20 + level * 10,
                "max_hp": 20 + level * 10,
                "atk": 5 + level * 2,
                "lvl": level
            }

    def add_log(self, message):
        self.logs.append(message)
        if len(self.logs) > 6:
            self.logs.pop(0)

    async def update_embed(self, interaction):
        embed = discord.Embed(title=f"Combat contre {self.enemy['name']}", color=0xff0000)
        embed.add_field(name="Tes PV", value=f"{self.player['hp']} / {self.player['max_hp']}", inline=True)
        embed.add_field(name="PV Ennemi", value=f"{self.enemy['hp']} / {self.enemy['max_hp']}", inline=True)
        embed.add_field(name="Logs", value="\n".join(self.logs) or "Début du combat...", inline=False)
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Attaquer", style=discord.ButtonStyle.primary)
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != int(self.player_id):
            return await interaction.response.send_message("Ce n'est pas ton combat.", ephemeral=True)
        await interaction.response.defer()

        # Joueur attaque
        if random.random() < 0.2:
            self.add_log("❌ Tu as raté ton attaque !")
        else:
            dmg = random.randint(self.player["atk"] // 2, self.player["atk"])
            self.enemy["hp"] -= dmg
            self.add_log(f"⚔️ Tu infliges {dmg} dégâts au {self.enemy['name']}.")

        # Si ennemi mort
        if self.enemy["hp"] <= 0:
            if "Aventurier" in self.enemy["name"]:
                xp_gain = self.enemy["lvl"] * 30
                gold_gain = self.enemy["lvl"] * 50
            else:
                xp_gain = self.enemy["lvl"] * 20
                gold_gain = self.enemy["lvl"] * 20

            self.player["xp"] += xp_gain
            self.player["gold"] += gold_gain
            self.add_log(f"☠️ {self.enemy['name']} est vaincu ! +{xp_gain} XP, +{gold_gain} gold.")

            while self.player["xp"] >= 100:
                self.player["xp"] -= 100
                self.player["lvl"] += 1
                self.player["atk"] += 2
                self.player["max_hp"] += 10
                self.player["hp"] = self.player["max_hp"]
                self.add_log(f"⬆️ Tu montes niveau {self.player['lvl']} !")

            self.player["inventory"].append("Potion")
            save_data(self.players)
            await self.update_embed(interaction)
            await interaction.followup.send("🏆 Tu as gagné le combat !", ephemeral=True)
            self.stop()
            return

        # Ennemi attaque
        if random.random() < 0.2:
            self.add_log(f"❌ Le {self.enemy['name']} a raté son attaque !")
        else:
            dmg_enemy = random.randint(self.enemy["atk"] // 2, self.enemy["atk"])
            self.player["hp"] -= dmg_enemy
            self.add_log(f"🔥 Le {self.enemy['name']} t’inflige {dmg_enemy} dégâts.")
            if self.player["hp"] <= 0:
                self.player["hp"] = self.player["max_hp"]
                self.player["xp"] = 0
                self.player["inventory"] = ["Potion"]
                self.add_log("💀 Tu es mort. Réinitialisation.")
                save_data(self.players)
                await self.update_embed(interaction)
                await interaction.followup.send("💀 Tu es mort. Ton personnage a été réinitialisé.", ephemeral=True)
                self.stop()
                return

        save_data(self.players)
        await self.update_embed(interaction)

    @discord.ui.button(label="Potion", style=discord.ButtonStyle.success)
    async def use_potion(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != int(self.player_id):
            return await interaction.response.send_message("Ce n'est pas ton combat.", ephemeral=True)

        if "Potion" not in self.player["inventory"]:
            return await interaction.response.send_message("❌ Tu n'as pas de potion !", ephemeral=True)

        self.player["inventory"].remove("Potion")
        heal = min(30, self.player["max_hp"] - self.player["hp"])
        self.player["hp"] += heal
        self.add_log(f"🧪 Tu utilises une potion et récupères {heal} PV.")
        save_data(self.players)
        await self.update_embed(interaction)
        await interaction.response.send_message("🧪 Potion utilisée !", ephemeral=True)

    @discord.ui.button(label="Fuir", style=discord.ButtonStyle.danger)
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != int(self.player_id):
            return await interaction.response.send_message("Ce n'est pas ton combat.", ephemeral=True)

        self.add_log("🏃 Tu as fui le combat.")
        await self.update_embed(interaction)
        await interaction.followup.send("🚪 Tu as quitté le combat.", ephemeral=True)
        self.stop()

@bot.command()
async def fight(ctx):
    uid = str(ctx.author.id)
    if uid not in players:
        return await ctx.send("Fais `!start` d'abord.")
    view = FightView(uid, players)
    embed = discord.Embed(title="Combat", description="Choisis ton action !", color=0xff0000)
    embed.add_field(name="Tes PV", value=f"{players[uid]['hp']} / {players[uid]['max_hp']}", inline=True)
    embed.add_field(name="PV Ennemi", value="??? / ???", inline=True)
    await ctx.send(embed=embed, view=view)

@bot.command()
async def inventory(ctx):
    uid = str(ctx.author.id)
    if uid not in players:
        return await ctx.send("Fais `!start` d'abord.")
    p = players[uid]
    inv = Counter(p.get("inventory", []))
    embed = discord.Embed(title=f"🎒 Inventaire de {p['name']}", color=0x8e44ad)
    if not inv:
        embed.description = "Ton inventaire est vide."
    else:
        for item, count in inv.items():
            embed.add_field(name=item, value=f"x{count}" if count > 1 else "\u200b", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def balance(ctx):
    uid = str(ctx.author.id)
    if uid not in players:
        return await ctx.send("Fais `!start` d'abord.")
    p = players[uid]
    if "gold" not in p:
        p["gold"] = 100
    embed = discord.Embed(title=f"💰 Argent de {p['name']}", color=0xFFFF00)
    embed.add_field(name="Gold", value=str(p["gold"]))
    await ctx.send(embed=embed)

@bot.command()
async def shop(ctx):
    embed = discord.Embed(title="🛒 Boutique", color=0xFFD700)
    for item, data in SHOP_ITEMS.items():
        embed.add_field(name=f"{item} - {data['price']} gold", value=data["description"], inline=False)
    embed.set_footer(text="Pour acheter: !buy <nom_objet>")
    await ctx.send(embed=embed)

@bot.command()
async def buy(ctx, *, item_name: str):
    uid = str(ctx.author.id)
    if uid not in players:
        return await ctx.send("Fais `!start` d'abord.")
    p = players[uid]
    if "gold" not in p:
        p["gold"] = 100

    item_name = item_name.title()
    if item_name not in SHOP_ITEMS:
        return await ctx.send("Objet inconnu en boutique.")

    price = SHOP_ITEMS[item_name]["price"]
    if p["gold"] < price:
        return await ctx.send("Tu n'as pas assez d'or.")

    p["gold"] -= price

    if item_name == "Potion":
        p["inventory"].append("Potion")
    elif item_name == "Épée En Bois":
        p["atk"] += 5
    elif item_name == "Armure Légère":
        p["max_hp"] += 20
        p["hp"] += 20
        if p["hp"] > p["max_hp"]:
            p["hp"] = p["max_hp"]

    save_data(players)
    await ctx.send(f"Tu as acheté **{item_name}** pour {price} gold.")

@bot.command()
async def addgold(ctx, member: discord.Member, amount: int):
    CREATOR_ID = 1175261012027514970
    if ctx.author.id != CREATOR_ID:
        embed = discord.Embed(title="⛔ Accès refusé", description="Tu n'as pas la permission d'utiliser cette commande.", color=0xFF0000)
        return await ctx.send(embed=embed)

    uid = str(member.id)
    if uid not in players:
        return await ctx.send("Ce joueur n'a pas encore commencé.")
    if "gold" not in players[uid]:
        players[uid]["gold"] = 0

    players[uid]["gold"] += amount
    save_data(players)

    embed = discord.Embed(title="💸 Gold ajouté", color=0x00FF00)
    embed.add_field(name="Joueur", value=member.display_name, inline=True)
    embed.add_field(name="Montant", value=f"{amount} gold", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def walk(ctx):
    uid = str(ctx.author.id)
    if uid not in players:
        return await ctx.send("Fais `!start` d'abord.")
    p = players[uid]
    if "walking" not in p:
        p["walking"] = False

    if p["walking"]:
        return await ctx.send("**__🚶 Tu es déjà en train de marcher.__**")

    if p["location"] == "camp":
        destination = "ville"
    elif p["location"] == "ville":
        destination = "camp"
    else:
        return await ctx.send("**❌ Tu ne peux marcher que depuis le camp ou la ville.**")

    p["walking"] = True
    save_data(players)

    embed = discord.Embed(title=f"**__🚶 Marche vers {destination}__**", description="**Temps restant : 10 secondes**", color=0x3498db)
    message = await ctx.send(embed=embed)

    for remaining in range(8, -1, -2):
        await asyncio.sleep(2)
        embed.description = f"**Temps restant : {remaining} secondes**"
        await message.edit(embed=embed)

    p["location"] = destination
    p["walking"] = False
    save_data(players)

    embed.description = f"🏙️ Tu es arrivé(e) à {destination}."
    await message.edit(embed=embed)

bot.run("MTM1Njc5NTQxNzg5NDk3NzY4Ng.GsPeu8.YX23WBzLcI0IWZA97UMyiuE-zApZf2YRf9oXYw")