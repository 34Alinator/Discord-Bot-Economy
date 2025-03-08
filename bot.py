import os
import json
from dotenv import load_dotenv
from discord.ext import commands
import discord
from discord import app_commands
from typing import Literal, Optional

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

# Load JSON data
def load_json(filename):
    with open(filename, 'r') as f:
        return json.load(f)

data = load_json('bank_accs.json')
jnation = load_json('Nations.json')
jfaction = load_json('Factions.json')

# Save JSON data
def save_json(filename, content):
    with open(filename, 'w') as f:
        json.dump(content, f, indent=4)

# Find nation for a user
def find_nation(user_id):
    for nation, info in jnation.items():
        if user_id in info['citizen']:
            return nation
    return "User  is not in a Nation"

# Initialize bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents)

@bot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
    if not guilds:
        if spec == "~":
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "*":
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "^":
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            synced = []
        else:
            synced = await ctx.bot.tree.sync()

        await ctx.send(f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}")
        return

    ret = 0
    for guild in guilds:
        try:
            await ctx.bot.tree.sync(guild=guild)
            ret += 1
        except discord.HTTPException:
            pass

    await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD))
    print(f'{bot.user.name} has connected to Discord!')

#Update user balance
async def update_user_balance(user_id, amount):
    if user_id not in data:
        data[user_id] = {"money": 2500}
    data[user_id]['money'] += amount
    save_json('bank_accs.json', data)

# Commands
#Ping
@bot.tree.command()
async def ping(inter: discord.Interaction) -> None:
    await inter.response.send_message(f"> Pong! {round(bot.latency * 1000)}ms")


#User ID
@bot.tree.command(name='userid', description="Prints the user id")
@commands.has_role('admin')
async def userid(interaction: discord.Interaction, user: discord.Member = None):
    user_id = str(user.id)
    print(user_id)
    await interaction.response.send_message(f'User  Id from {user}: {user_id}')


#User Info
@bot.tree.command(name='userinfo', description='Shows the stats of a user')
async def user_info(interaction: discord.Interaction, user: discord.Member = None):
    if user is None:
        user = interaction.user
    user_id = str(user.id)
    await update_user_balance(user_id, 0)
    current_money = data[user_id]['money']
    await interaction.response.send_message(f'<@{user_id}>:\n   Money: {current_money}\n   Nation: {find_nation(user_id)}')


#add_money
@bot.tree.command(name="add_money", description='first is the account then the amount')
@app_commands.checks.has_permissions(administrator=True)
async def add_money(interaction: discord.Interaction, account: discord.Member, amount: int) -> None:
    user_id = str(account.id)
    await update_user_balance(user_id, amount)
    new_money = data[user_id]['money']
    await interaction.response.send_message(f'New balance of: <@{user_id}> is: {new_money}')


#remove_money
@bot.tree.command(name="remove_money", description='first is the account then the amount')
@app_commands.checks.has_permissions(administrator=True)
async def remove_money(interaction: discord.Interaction, account: discord.Member, amount: int) -> None:
    user_id = str(account.id)
    await update_user_balance(user_id, -amount)
    new_money = data[user_id]['money']
    await interaction.response.send_message(f'New balance of: <@{user_id}> is: {new_money}')


#pay
@bot.tree.command(name="pay", description='Pay money to another user or a nation')
async def pay(interaction: discord.Interaction, amount: int, recipient_user: discord.Member = None, recipient_nf: str = None):
    user_id = str(interaction.user.id)

#Check what has been entered (nation/faction or user)
    if recipient_user is None and recipient_nf is None:
        await interaction.response.send_message('Please specify a recipient (either a user or a nation).')
        return

    recipient_id = None
    recipient_type = None

    if recipient_user is not None:
        recipient_id = str(recipient_user.id)   #Get the user id from the recipient
        recipient_type = "user"
    elif recipient_nf is not None:
        recipient_id = recipient_nf  # Use the nation name directly
        recipient_type = "nation"

    if user_id not in data:
        await interaction.response.send_message(f'User  {interaction.user} not found in the database.')
        return

    current_money = data[user_id]['money']

    # Check if recipient exists in the database
    if recipient_type == "user":
        if recipient_id not in data:
            await interaction.response.send_message(f'Recipient user not found in the database.')
            return
    elif recipient_type == "nation":
        if recipient_id not in data or 'money' not in data[recipient_id]:  # Adjust this check based on your data structure
            await interaction.response.send_message(f'Recipient nation "{recipient_nf}" not found in the database.')
            return

    # Check if the user has enough money to make the payment
    if current_money >= amount:
        data[user_id]['money'] -= amount
        if recipient_type == "user":
            data[recipient_id]['money'] += amount
        elif recipient_type == "nation":
            # Assuming nations have a separate money attribute
            data[recipient_id]['money'] += amount  # Adjust this based on your data structure

        # Save the updated data
        with open('bank_accs.json', 'w') as json_file:
            json.dump(data, json_file, indent=4)

        await interaction.response.send_message(f'You have paid {amount} to {recipient_nf if recipient_type == "nation" else f"<@{recipient_id}>"}.')
    else:
        await interaction.response.send_message(f'You do not have enough money to pay {amount}.')


#balance user
@bot.tree.command(name='bal-user', description='Prints the money of a user')
async def bal_user(interaction: discord.Interaction, user: discord.Member):
    money = data[str(user.id)]['money']
    await interaction.response.send_message(f'{user.mention} balance is: {money}.')


#Nation
#Nation Info
@bot.tree.command(name='nationinfo', description='See the information from a Nation')
async def nationinfo(interaction: discord.Interaction, nation: str):
    if nation in jnation:
        description = jnation[nation]['description']
        money = data.get(nation, {}).get('money', 0)
        citizens = len(jnation[nation]['citizen'])
        await interaction.response.send_message(f'{nation}\n   Description: {description}\n   Citizens: {citizens}\n   Money: {money}')
    else:
        await interaction.response.send_message(f'{nation} was not found.')


#Invite-Nation
@bot.tree.command(name='invite-nation', description='Invite a Player to your Nation')
async def invite_nation(interaction: discord.Interaction, nation: str, user: discord.Member):
    user_id = str(interaction.user.id)

    if user_id != jnation[nation]['Leader']:
        await interaction.response.send_message(f'You are not the leader of {nation}.', ephemeral=True)
        return

    if user.id == interaction.client.user.id:
        await interaction.response.send_message("You cannot invite the bot to a nation.", ephemeral=True)
        return

#Button
    class InviteView(discord.ui.View):
        def __init__(self, user: discord.Member, nation: str):
            super().__init__()
            self.user = user
            self.nation = nation

        @discord.ui.button(label='Accept', style=discord.ButtonStyle.green)
        async def accept(self, button: discord.ui.Button, interaction: discord.Interaction):
            if str(self.user.id) not in jnation[self.nation]['citizen']:
                jnation[self.nation]['citizen'].append(str(self.user.id))
                save_json('Nations.json', jnation)
                await self.user.send(f'You have accepted the invitation to join {self.nation}!')
            else:
                await self.user.send(f'You are already a citizen of {self.nation}.')
            self.stop()

        @discord.ui.button(label='Decline', style=discord.ButtonStyle.red)
        async def decline(self, button: discord.ui.Button, interaction: discord.Interaction):
            await self.user.send(f'You have declined the invitation to join {self.nation}.')
            self.stop()

    await user.send(
        f'You have been invited to join the nation {nation} by <@{interaction.user.id}>. Do you accept?',
        view=InviteView(user, nation)
    )
    await interaction.response.send_message(f'Invitation sent to {user.mention}!', ephemeral=True)


#Balance Nation/Faction
@bot.tree.command(name='bal', description='Prints the money of a Nation or Faction')
async def bal_nation(interaction: discord.Interaction, nof: str):
    money = data.get(nof, {}).get('money', 0)
    await interaction.response.send_message(f'{nof} balance is: {money}.')


#Factions
#Faction Info
@bot.tree.command(name='factioninfo', description='See the information from a Faction')
async def factioninfo(interaction: discord.Interaction, faction: str):
    if faction in jfaction:
        description = jfaction[faction]['description']
        money = data.get(faction, {}).get('money', 0)
        workers = len(jfaction[faction]['workers'])
        await interaction.response.send_message(f'{faction}\n   Description: {description}\n   Workers: {workers}\n   Money: {money}')
    else:
        await interaction.response.send_message(f'{faction} was not found.')

@bot.tree.command(name='invite-faction', description='Invite a Player to your Faction')
async def invite_faction(interaction: discord.Interaction, faction: str, user: discord.Member):
    user_id = str(interaction.user.id)

    if user_id != jfaction[faction]['Leader']:
        await interaction.response.send_message(f'You are not the leader of {faction}.', ephemeral=True)
        return

    if user.id == interaction.client.user.id:
        await interaction.response.send_message("You cannot invite the bot to a faction.", ephemeral=True)
        return

    class InviteView(discord.ui.View):
        def __init__(self, user: discord.Member, faction: str):
            super().__init__()
            self.user = user
            self.faction = faction

        @discord.ui.button(label='Accept', style=discord.ButtonStyle.green)
        async def accept(self, button: discord.ui.Button, interaction: discord.Interaction):
            if str(self.user.id) not in jfaction[self.faction]['workers']:
                jfaction[self.faction]['workers'].append(str(self.user.id))
                save_json('Factions.json', jfaction)
                await self.user.send(f'You have accepted the invitation to join {self.faction}!')
            else:
                await self.user.send(f'You are already a worker of {self.faction}.')
            self.stop()

        @discord.ui.button(label='Decline', style=discord.ButtonStyle.red)
        async def decline(self, button: discord.ui.Button, interaction: discord.Interaction):
            await self.user.send(f'You have declined the invitation to join {self.faction}.')
            self.stop()

    await user.send(
        f'You have been invited to join the faction {faction} by <@{interaction.user.id}>. Do you accept?',
        view=InviteView(user, faction)
    )
    await interaction.response.send_message(f'Invitation sent to {user.mention}!', ephemeral=True)


#Create-Faction
@bot.tree.command(name='create-faction', description='Creates a Faction for a fee of 2500')
async def create_faction(interaction: discord.Interaction, name: str, description: str):
    user_id = str(interaction.user.id)
    if data[user_id]['money'] >= 2500:
        data[user_id]['money'] -= 2500
        data[name] = {"money": 0}
        save_json('bank_accs.json', data)
        new_faction = {name: {'Leader': user_id, 'Workers': [user_id], 'Description': description}}
        jfaction.update(new_faction)
        save_json('Factions.json', jfaction)
        await interaction.response.send_message('Faction Created!', ephemeral=True)
    else:
        await interaction.response.send_message('Not enough Money', ephemeral=True)

@bot.tree.command(name='edit-faction', description='Edit one of your Factions')
async def edit_faction(interaction: discord.Interaction, current_name: str, new_name: str, new_description: str):
    user_id = str(interaction.user.id)

    if current_name not in jfaction:
        await interaction.response.send_message(f'The faction "{current_name}" does not exist.', ephemeral=True)
        return

    if jfaction[current_name]['Leader'] != user_id:
        await interaction.response.send_message(f'You are not the leader of the faction "{current_name}".', ephemeral=True)
        return

    faction_data = jfaction[current_name]
    faction_data['description'] = new_description

    if new_name != current_name:
        jfaction[new_name] = faction_data
        del jfaction[current_name]

    save_json('Factions.json', jfaction)

    await interaction.response.send_message(f'Faction "{current_name}" has been edited to "{new_name}".', ephemeral=True)


#Nof (Nation or Faction) pay
@bot.tree.command(name='nofpay', description='Paying for a nation or faction (nof)')
async def nofpay(interaction: discord.Interaction, amount: int, sender_acc: str, recipient_user: discord.Member = None, recipient_nf: str = None):
    user_id = str(interaction.user.id)
    print(user_id)

    # Check if the sender_acc exists in jfaction and jnation
    faction_leader = jfaction.get(sender_acc, {}).get('Leader')
    nation_leader = jnation.get(sender_acc, {}).get('Leader')

    # Check if the user is the leader of the faction or nation
    if faction_leader != user_id and nation_leader != user_id:
        await interaction.response.send_message(f'You are not the leader of the faction "{sender_acc}" or the nation "{sender_acc}".', ephemeral=True)
        return

    # Check if both recipient_user and recipient_nf are None
    if recipient_user is None and recipient_nf is None:
        await interaction.response.send_message('Please specify a recipient (either a user or a nation).', ephemeral=True)
        return

    # Determine recipient ID and type
    recipient_id = None
    recipient_type = None

    if recipient_user is not None:
        recipient_id = str(recipient_user.id)  # Use string for consistency with user_id
        recipient_type = "user"
    elif recipient_nf is not None:
        recipient_id = recipient_nf  # Use the nation name directly
        recipient_type = "nation"

    if user_id not in data:
        await interaction.response.send_message(f'User  {interaction.user} not found in the database.', ephemeral=True)
        return

    current_money = data[user_id]['money']

    # Check if recipient exists in the database
    if recipient_type == "user":
        if recipient_id not in data:
            await interaction.response.send_message(f'Recipient user not found in the database.', ephemeral=True)
            return
    elif recipient_type == "nation":
        # Check if the nation exists in the data
        if recipient_id not in data or 'money' not in data[recipient_id]:  # Adjust this check based on your data structure
            await interaction.response.send_message(f'Recipient nation "{recipient_nf}" not found in the database.', ephemeral=True)
            return

    # Check if the user has enough money to make the payment
    if current_money >= amount:
        data[sender_acc]['money'] -= amount
        data[recipient_id]['money'] += amount

        # Save the updated data
        with open('bank_accs.json', 'w') as json_file:
            json.dump(data, json_file, indent=4)

        await interaction.response.send_message(f'You have paid {amount} to {recipient_nf if recipient_type == "nation" else f"<@{recipient_id}>"}.', ephemeral=True)
    else:
        await interaction.response.send_message(f'You do not have enough money to pay {amount}.', ephemeral=True)

bot.run(TOKEN)