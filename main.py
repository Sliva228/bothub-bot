#imports & froms
from sys import executable
import discord
import random
from discord import player
from discord.ext import commands, tasks
from discord.components import Button, ButtonStyle
import pafy
import logging
import asyncio
import json
import youtube_dl

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=">", intents=intents)

# Имитируем переменные для тестирования
intents = discord.Intents.default()
intents.members = True  # Чтобы бот мог получать список участников

# Список участников, которых не нужно наказывать (белый список)
whitelist = set()

# Поддержка YouTubeDL для воспроизведения музыки
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # Могут быть проблемы с Replit, но попробуем
}

ffmpeg_options = {'options': '-vn'}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


@bot.event
async def on_ready():
    print(f"Бот {bot.user.name} успешно запущен и готов к работе!")


class YTDLSource(discord.PCMVolumeTransformer):

    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options),
                   data=data)


@bot.command(name='play', help='Проигрывает музыку по URL или названию.')
async def play(ctx, url):
    try:
        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
            ctx.voice_client.play(player,
                                  after=lambda e: print(f'Ошибка: {e}')
                                  if e else None)

        await ctx.send(f'Сейчас играет: {player.title}')
    except Exception as e:
        await ctx.send(f'Ошибка при воспроизведении: {str(e)}')


@bot.command(name='pause', help='Ставит музыку на паузу.')
async def pause(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send('Музыка на паузе.')


@bot.command(name='resume', help='Продолжает воспроизведение музыки.')
async def resume(ctx):
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send('Музыка продолжена.')


@bot.command(name='skip', help='Пропускает текущий трек.')
async def skip(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send('Текущий трек пропущен.')


@bot.command(
    name='stop',
    help='Останавливает воспроизведение музыки и выходит из голосового канала.'
)
async def stop(ctx):
    await ctx.voice_client.disconnect()
    await ctx.send('Бот покинул голосовой канал.')


@bot.command(name='join', help='Присоединяется к голосовому каналу.')
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send(
            'Вы должны быть в голосовом канале, чтобы использовать эту команду.'
        )
        return
    channel = ctx.message.author.voice.channel
    await channel.connect()


@bot.command(name='leave', help='Оставляет голосовой канал.')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.guild.voice_client.disconnect()
        await ctx.send('Бот покинул голосовой канал.')
    else:
        await ctx.send('Бот не находится в голосовом канале.')


@bot.slash_command(name='ping', description='Проверка пинга')
async def ping(ctx):
    await ctx.respond("PONG!!!!")


@bot.slash_command(name='pip', description='Команда для проверки')
async def pip(ctx):
    await ctx.send("pip не является внутренним или внешним аргументом...",
                   file=discord.File("pip.gif"))


@bot.slash_command(name='admins', description='Команда для проверки')
async def admins(ctx):
    await ctx.send(
        "На данный момент администраторами являются: <@530510099509411840> И <@612720307156811776>"
    )


# Система предложений
suggestions = []


@bot.slash_command(name="suggest", description="Оставить предложение")
async def suggest(ctx, *, idea):
    embed = discord.Embed(title="Новое предложение",
                          description=idea,
                          color=0x00ff00)
    embed.set_author(name=ctx.author.display_name,
                     icon_url=ctx.author.avatar.url)
    message = await ctx.send(embed=embed)
    await message.add_reaction("👍")
    await message.add_reaction("👎")
    suggestions.append(message.id)
    await ctx.respond(
        f"Ваше предложение зарегистрировано и выставлено на голосование.")


@bot.slash_command(name="suggestions",
                   description="Посмотреть активные предложения")
async def list_suggestions(ctx):
    if not suggestions:
        await ctx.respond("Нет активных предложений.")
        return

    embed = discord.Embed(title="Активные предложения", color=0x00ff00)
    for suggestion_id in suggestions:
        message = await ctx.fetch_message(suggestion_id)
        embed.add_field(name=message.embeds[0].description,
                        value=f"ID: {suggestion_id}",
                        inline=False)

    await ctx.respond(embed=embed)


@bot.slash_command(name="suggestion_result",
                   description="Посмотреть результат голосования по ID")
async def suggestion_result(ctx, suggestion_id: int):
    try:
        message = await ctx.fetch_message(suggestion_id)
        reaction_up = discord.utils.get(message.reactions, emoji="👍")
        reaction_down = discord.utils.get(message.reactions, emoji="👎")

        upvotes = reaction_up.count - 1  # Исключаем сам бот
        downvotes = reaction_down.count - 1

        embed = discord.Embed(title="Результат голосования",
                              description=message.embeds[0].description,
                              color=0x00ff00)
        embed.add_field(name="👍 Голосов ЗА:", value=upvotes)
        embed.add_field(name="👎 Голосов ПРОТИВ:", value=downvotes)

        await ctx.respond(embed=embed)
    except:
        await ctx.respond("Невозможно найти предложение с таким ID.")


@bot.slash_command(name='mods',
                   description='Наши актуальные сборки модов для разных игр')
async def mods(ctx):

    async def check_reaction(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ['1️⃣', '2️⃣']

    message = await ctx.send(
        "Выберите игру к которой вы хотите добавить нашу сборку модов:\n 1️⃣ - Lethal Company \n 2️⃣ - Rounds"
    )
    await message.add_reaction("1️⃣")
    await message.add_reaction("2️⃣")
    try:
        reaction, user = await bot.wait_for('reaction_add',
                                            timeout=60.0,
                                            check=check_reaction)
    except asyncio.TimeoutError:
        await ctx.send('Прошло слишком много времени, команда отменена.')
    else:
        if str(reaction.emoji) == '1️⃣':
            await ctx.message.delete()
            embed = discord.Embed(
                title="Видео туториал по установке",
                description=
                "Наша октуальная сборка модов для **Lethal Company** \nВаш код: 018d94d7-4279-5752-1c0f-b7a766965319 \n Cкачать Thunderstore Mod Manager \n https://download.overwolf.com/install/Download?ExtensionId=ahpflogoookodlegojjphcjpjaejgghjnfcdjdmi&utm_source=web_app_store",
                colour=0x9402FF,
                url='https://youtu.be/l5Ytn6beTtI',
            )
            await ctx.send(embed=embed)
        elif str(reaction.emoji) == '2️⃣':
            embed = discord.Embed(
                title="Видео туториал по установке",
                description=
                "Наша октуальная сборка модов для **Rounds** \nВаш код: 018dc79e-095e-c768-67e6-5204cfa664e1 \n Cкачать Thunderstore Mod Manager \n https://download.overwolf.com/install/Download?ExtensionId=ahpflogoookodlegojjphcjpjaejgghjnfcdjdmi&utm_source=web_app_store",
                colour=0x9402FF,
                url='https://youtu.be/l5Ytn6beTtI',
            )
            await ctx.send(embed=embed)


@tasks.loop(hours=6)  # Запуск задачи каждые 6 часов
async def schedule_random_actions():
    guild = bot.guilds[0]  # Используем первый сервер, на котором работает бот
    members = [
        member for member in guild.members
        if not member.bot and member.id not in whitelist
        and member.status == discord.Status.online
    ]

    if not members:
        print(
            "Не найдено доступных участников или все участники в белом списке."
        )
        return

    selected_member = random.choice(members)
    print(f'Выбранный участник: {selected_member.mention}')

    # Планирование случайных действий на день
    await perform_actions_throughout_day(guild, selected_member)


async def perform_actions_throughout_day(guild, member):
    actions = [move_member_to_channel, timeout_member]

    # Увеличьте количество действий (например, от 6 до 10 раз)
    num_actions = random.randint(6, 10)

    for _ in range(num_actions):
        action = random.choice(actions)
        await action(guild, member)

        # Уменьшите перерыв между действиями (например, от 10 до 30 минут)
        await asyncio.sleep(random.randint(600, 1800)
                            )  # 600 секунд = 10 минут, 1800 секунд = 30 минут


async def move_member_to_channel(guild, member):
    voice_channel = guild.get_channel(
        123456789012345678)  # Замените на ID целевого канала
    if member.voice:
        await member.move_to(voice_channel)
        await send_action_webhook(
            guild,
            f'{member.mention} был перемещен в канал {voice_channel.name}.')


async def timeout_member(guild, member):
    timeout_duration = random.randint(
        300, 900)  # 300 секунд = 5 минут, 900 секунд = 15 минут
    await member.edit(timed_out_until=discord.utils.utcnow() +
                      discord.utils.timedelta(seconds=timeout_duration))
    await send_action_webhook(
        guild,
        f'{member.mention} был отправлен в тайм-аут на {timeout_duration // 60} минут.'
    )


async def send_action_webhook(guild, message):
    channel = guild.get_channel(1132302748898041936)  # ID целевого канала
    if channel:
        # Создаем вебхук, отправляем сообщение и удаляем вебхук
        webhook = await channel.create_webhook(name="Бот")
        await webhook.send(content=message,
                           username="Наказания",
                           avatar_url=bot.user.avatar.url)
        await webhook.delete()


@bot.slash_command(
    name="pick_random",
    description="Выбирает случайного участника и проводит с ним действия")
async def pick_random(ctx):
    guild = ctx.guild
    members = [
        member for member in guild.members
        if not member.bot and member.id not in whitelist
        and member.status == discord.Status.online
    ]

    if not members:
        await ctx.respond(
            "На сервере нет доступных участников или все участники в белом списке."
        )
        return

    selected_member = random.choice(members)
    await ctx.respond(
        f'Выбран {selected_member.mention}. Начинаем выполнение случайных действий.'
    )

    await perform_actions_throughout_day(guild, selected_member)


# Команда для добавления пользователя в белый список
@bot.slash_command(name="whitelist_add",
                   description="Добавляет пользователя в белый список")
async def whitelist_add(ctx, member: discord.Member):
    if member.id in whitelist:
        await ctx.respond(f'{member.mention} уже находится в белом списке.')
    else:
        whitelist.add(member.id)
        await ctx.respond(f'{member.mention} был добавлен в белый список.')


# Команда для удаления пользователя из белого списка
@bot.slash_command(name="whitelist_remove",
                   description="Удаляет пользователя из белого списка")
async def whitelist_remove(ctx, member: discord.Member):
    if member.id not in whitelist:
        await ctx.respond(f'{member.mention} не находится в белом списке.')
    else:
        whitelist.remove(member.id)
        await ctx.respond(f'{member.mention} был удален из белого списка.')


# Команда для отображения белого списка
@bot.slash_command(name="whitelist_list",
                   description="Отображает текущий белый список")
async def whitelist_list(ctx):
    if not whitelist:
        await ctx.respond("Белый список пуст.")
    else:
        members_in_whitelist = [
            ctx.guild.get_member(member_id) for member_id in whitelist
        ]
        members_mentions = [
            member.mention for member in members_in_whitelist if member
        ]
        await ctx.respond(f'Белый список: {", ".join(members_mentions)}')


# Модераторские команды
@bot.slash_command(name="warn",
                   description="Выдать предупреждение пользователю.")
async def warn(ctx, member: discord.Member, *, reason=None):
    if reason is None:
        reason = "Причина не указана"
    await member.send(
        f"Вам выдано предупреждение на сервере {ctx.guild.name}. Причина: {reason}"
    )
    await ctx.respond(
        f"{member.mention} получил предупреждение. Причина: {reason}")


@bot.slash_command(name="clear", description="Очистить сообщения в канале.")
async def clear(ctx, amount: int):
    await ctx.channel.purge(limit=amount)
    await ctx.respond(f"Удалено {amount} сообщений.", ephemeral=True)


# Мини-игры
@bot.slash_command(name="coinflip", description="Подбрасывает монетку.")
async def coinflip(ctx):
    result = random.choice(["Орел", "Решка"])
    await ctx.respond(f"Монетка показала: {result}")


@bot.slash_command(name="dice", description="Бросает кубик.")
async def dice(ctx, sides: int = 6):
    if sides < 1:
        await ctx.respond("Число граней должно быть больше 0.")
        return
    result = random.randint(1, sides)
    await ctx.respond(f"Кубик показал: {result}")


@bot.slash_command(name="rps", description="Игра 'Камень, ножницы, бумага'.")
async def rps(ctx, choice: str):
    choices = ["Камень", "Ножницы", "Бумага"]
    if choice.capitalize() not in choices:
        await ctx.respond("Выберите Камень, Ножницы или Бумагу.")
        return

    bot_choice = random.choice(choices)
    result = ""
    if bot_choice == choice.capitalize():
        result = "Ничья!"
    elif (bot_choice == "Камень" and choice.capitalize() == "Ножницы") or \
         (bot_choice == "Ножницы" and choice.capitalize() == "Бумага") or \
         (bot_choice == "Бумага" and choice.capitalize() == "Камень"):
        result = "Бот победил!"
    else:
        result = "Вы победили!"

    await ctx.respond(f"Бот выбрал {bot_choice}. {result}")


# Рандомайзер задач

challenges = [
    "Отправьте сообщение с 10 разными эмодзи.",
    "Присоединитесь к голосовому каналу на 5 минут.",
    "Создайте опрос с минимум 3 вариантами ответа.",
    "Поставьте лайк на 5 разных сообщений."
]


@bot.slash_command(name="challenge", description="Получить случайное задание.")
async def challenge(ctx):
    challenge = random.choice(challenges)
    await ctx.respond(f"Ваше задание: {challenge}")


@bot.slash_command(name="challenges",
                   description="Просмотреть список активных заданий.")
async def list_challenges(ctx):
    embed = discord.Embed(title="Доступные задания", color=0x00ff00)
    for idx, challenge in enumerate(challenges, 1):
        embed.add_field(name=f"Задание {idx}", value=challenge, inline=False)
    await ctx.respond(embed=embed)


bot.run(
    "MTIwNTIxNTgzNzYyODI2ODU0NQ.G44Kr9.1c0dgaFUkKz6PSCbSu3ZQKWFALKwXG2-oLyZao")
