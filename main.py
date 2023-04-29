import logging
import math
import os
import pprint

import telegram.error
from telegram.ext import Application, MessageHandler, filters, CommandHandler, CallbackQueryHandler, ConversationHandler
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

from Game import Imaginarium

from dotenv import load_dotenv

# get token from .env
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Запускаем логгирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG
)

logger = logging.getLogger(__name__)


games = []


def get_game_by_host(host):
    try:
        game: Imaginarium = list(filter(lambda x: x.host == host, games))[0]
        return game
    except IndexError:
        return ''


async def test(u, c):
    send = await c.bot.send_message(text=f'🔴adada', chat_id=u.message.chat.id)


async def callback_solver(update, context):
    # this function manages with button callbacks
    # buttons are used for voting, choosing cards and so on

    query = update.callback_query

    # join another game
    if query.data[:4] == 'join':
        game = list(filter(lambda x: x.host.id == int(query.data.split()[1]), games))
        # if game exists
        if game:
            if query.from_user in [i.user for i in game[0].players]:
                logger.info(f'{query.from_user} already in game')
                return

            # add player to a game and get him (add player only if there's enough cards to give)
            if list(filter(lambda x: query.from_user in [i.user for i in x.players], games)):
                await context.bot.send_message(chat_id=query.from_user.id, text=f'Вы уже играете')
                return

            if len(game[0].local_cards) < 6:
                username = f'[{query.from_user.first_name}](tg://user?id={query.from_user.id})'
                await context.bot.send_message(chat_id=game[0].main_chat_id,
                                               text=f'@{username} вы не можете присоединиться к игре, '
                                                    f'карты закончились, простите 😔', parse_mode='Markdown')
                return
            else:
                game[0].add_player(query.from_user)
            player = list(filter(lambda x: query.from_user == x.user, game[0].players))[0]

            host_name = game[0].host.first_name + (game[0].host.last_name if game[0].host.last_name is not None else "")
            await context.bot.send_message(chat_id=game[0].main_chat_id,
                                           text=f'{player.name} '
                                                f'присоединился к игре {host_name}')
        else:
            # game doesn't exist so it has ended or it was deleted
            # (I'm not sure if we have to inform the user because he presses a button (not writing anything))
            pass
        return

    # choose a card (matching description)
    elif query.data[:6] == 'choose':
        user_id = query.from_user.id
        # find a game player in
        game = list(filter(lambda x: user_id in [i.user.id for i in x.players], games))
        # if player in game
        if game:
            game = game[0]
            player = list(filter(lambda x: x.user.id == user_id, game.players))[0]

            # if vote is not on
            if game.vote_message_id == -1:
                # return if player is a current player
                if player == game.current_player:
                    await context.bot.send_message(chat_id=query.from_user.id, text='напишите ассоциацию к карте')
                    return

                # shouldn't be any errors
                # in error then that is my fault
                resp = player.pick_card(int(query.data.split()[1]))
                if resp.get('error', ''):
                    await context.bot.send_message(chat_id=query.from_user.id, text=resp['error'])
                await context.bot.send_message(chat_id=query.from_user.id, text='Ваша карта учтена')
                # try to make vote line for the game
                vote_img = game.make_vote_line()

                # if not everybody has chosen card: write who hasn't
                # actually writes the last player not to pick a card
                if vote_img.get('error', ''):
                    if vote_img['error'] != 'ignore':
                        await context.bot.send_message(chat_id=game.main_chat_id, text=resp['error'])
                    return

                # if everybody has chosen card: send images for voting with keyboard to vote
                else:
                    send = await context.bot.send_photo(chat_id=game.main_chat_id,
                                                        caption=f'выберите карту ведущего '
                                                                f'*({game.current_player.name})*',
                                                        photo=open(vote_img['image'], 'rb'),
                                                        reply_markup=InlineKeyboardMarkup(
                                                            [[InlineKeyboardButton(f'{ind + 1}',
                                                                                   callback_data=f'vote {ind + 1}')
                                                              for ind in range(len(game.vote_line))]]
                                                        ),
                                                        parse_mode='Markdown')
                    game.vote_message_id = send.id
        return

    # vote for a card from vote line
    elif query.data[:4] == 'vote':
        game = list(filter(lambda x: query.from_user in [i.user for i in x.players], games))

        # return if player is not in game
        if not game:
            return
        game = game[0]

        # return if vote message is inactive
        if query.message.message_id != game.vote_message_id:
            return

        player = list(filter(lambda x: x.user.id == query.from_user.id, game.players))[0]
        # return if player is current player
        if player == game.current_player:
            return

        # if there is error - then player votes for his own card
        resp = player.vote_for_card(int(query.data.split()[1]))
        if resp.get('error', ''):
            username = f'[{query.from_user.first_name}](tg://user?id={query.from_user.id})'
            await context.bot.send_message(chat_id=query.from_user.id, text=resp['error'] + f'{username}',
                                           parse_mode='Markdown')
            return

        # try to make a conclusion of round
        # if not everybody has voted: write who hasn't
        # else: write place for every player
        resp = game.conclusion()
        if resp.get('error', ''):
            await context.bot.send_message(chat_id=game.main_chat_id, text=resp['error'])
            return
        await context.bot.send_message(chat_id=game.main_chat_id, text=resp['success'], parse_mode='Markdown')

        if resp.get('img', ''):
            await context.bot.send_photo(chat_id=game.main_chat_id,
                                         caption='Ответы. (красный - ведущий)',
                                         photo=open(resp['img'], 'rb'))

        if resp.get('win', ''):
            winners = "\n".join([i.name for i in resp['win']])
            await context.bot.send_message(chat_id=game.main_chat_id, text=f'Победители:\n{winners}')
            await context.bot.send_message(chat_id=game.main_chat_id, text=f'Игра '
                                                                           f'{game.get_player_by_user(game.host).name} '
                                                                           f'окончена! Всем спасибо!🙂')
            game.delete_used_images()
            games.pop(games.index(game))
            game.players = []
            return

        if resp.get('no cards'):
            # if game hasn't ended yet
            if game.players:
                await context.bot.send_message(chat_id=game.main_chat_id, text='карты закончились, беру из раздачи...')

        await turn_start(update, context, game)


async def start(update, context):
    await update.message.reply_text('Привет! Я - бот для игры в Имаджинариум.\n'
                                    'Напиши:\n'
                                    '   /help, чтобы увидеть список команд\n'
                                    '   /rules, чтобы увидеть правила игры в Имаджинариум')


async def help_bot(update, _):
    await update.message.reply_text('Команды:\n'
                                    '\t/rules - правила игры\n\n'
                                    '\t/host - стать *хостом* новой игры. (_если указать число >0 через пробел, '
                                    'то финальное поле игры будет указанным (30 по умолчанию)_)\n\n'
                                    '_Чтобы присоединиться к чужой игре (в этом же чате), достаточно просто нажать_ '
                                    '*"присоединиться"* _под сообщением о создании новой игры._\n\n'
                                    '/set\_max\_place номер>0 - изменить финальное поле игры, '
                                    'хостом которой вы являетесь\n\n'
                                    '\t/delete - *удалить* игру, хостом которой вы являетесь\n\n'
                                    '\t/start - *начать* игру, хостом которой вы являетесь '
                                    '_(другие игроки больше не смогут присоединиться)_\n\n'
                                    '\t/quit чтобы *выйти* из игры (даже во время игры), _если вы хост, '
                                    'то права хоста будут переданы другому человеку_\n\n'
                                    '/kick _"упоминание игрока через @"_ - кикнуть игрока из игры '
                                    '(_нужно половина голосов чтобы кикнуть_)\n\n'
                                    'Остальные команды описываются по ходу игры.\n\n'
                                    '   _Ваши карты бот присылает вам в_ *лс.* '
                                    '_Туда же надо писать команду выбора карты '
                                    '(когда вы ведущий).\n'
                                    '   Когда вы не ведущий, '
                                    'бот сам предложит вам выбрать одну из ваших карт\n'
                                    '   Голосование проходит в общем чате, результаты отправляются туда же._\n\n'
                                    '_Доп. информация для ведущего: если вы ошиблись при написании ассоциации, '
                                    'можно написать или сказать другую, ассоциация никак не влияет на бота, '
                                    'она только рассылается для удобства каждому игроку для выбора карты_',
                                    parse_mode='Markdown')


async def help_game(update, _):
    await update.message.reply_text('Это бот для игры в *Имаджинарум*. Правила игры довольно просты: '
                                    'Каждому игроку раздается *6 карт*, затем определяется порядок ходов, '
                                    'каждый ход сменяется ведущий (_по очереди_). \n\n\tВедущий *выбирает карту '
                                    'и называет ассоциацию* (_то, с чем у него ассоцируется выбранная им картинка_)'
                                    '\n\n\tОстальные игроки выбирают из своих карт ту, которая более всего подходит '
                                    'к названной ассоциации.\n'
                                    '   Карты перемешивают и показывают всем, теперь ваша задача - '
                                    '*определить карту ведущего.*\n\n'
                                    '\tЕсли ее угадают все, то все (кроме ведущего) двигаются на 3 шага вперед\n\n'
                                    '\tЕсли никто, то все двигаются столько раз вперед, сколько их карту выбрали '
                                    'другие игроки (_то есть тот, чью карту выбрали 2 человека, '
                                    'идет на 2 шага вперед_)\n\n'
                                    '\tЕсли только часть игроков угадала карту ведущего, то все, кто угадал ее, '
                                    'двигаются на 3 вперед _(включая ведущего)_, также все игроки двигаются вперед '
                                    'на столько шагов, сколько человек угадало их карту _(включая ведущего)_\n\n'
                                    'Игра заканчивается при достижении финального поля '
                                    '(по умолчанию 30, но его можно изменить (см. /help))\n\n'
                                    '_(небольшой совет: чтобы было интересно играть загадывайте более расплывчатые '
                                    'ассоциации, чтобы ваши карты угадали только часть игроков, так вы получите '
                                    'больше мест и больше удовольствия!)_\n\n'
                                    '*Вот и все правила! Приятной игры.*',
                                    parse_mode='Markdown')


async def host_game(update, context):
    # check if message is sent in group chat
    if update.message['chat']['type'] == 'private':
        await update.message.reply_text('напишите эту команду в общий чат где вы хотите провести игру')
        return

    # check if user doesn't host another game
    username = f'[{update.message.from_user.first_name}](tg://user?id={update.message.from_user.id})'
    if get_game_by_host(update.message.from_user):
        await update.message.reply_text(f'{username} вы уже начали играть', parse_mode='Markdown')
        return

    max_place = -1
    if context.args:
        try:
            max_place = int(context.args[0])
            if max_place <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(f'{username}, формат команды /host:\n '
                                            f'  /host - создает игру с финальным полем 30\n'
                                            f'  /host число создает игру с указанным финальным полем',
                                            parse_mode='Markdown')
            return

    game = Imaginarium(update.message['chat']['id'], update.message.from_user)
    games.append(game)
    # add host to all players (otherwise he just hosts the game)
    game.add_player(game.host)
    player = game.get_player_by_user(game.host)

    if max_place != -1:
        game.max_place = max_place

    await context.bot.send_message(chat_id=game.main_chat_id,
                                   text=f'{player.name} начинает игру в Имаждинариум\n'
                                        f'нажмите "присоединиться", чтобы играть!\n\n'
                                        f'🔴* ОБЯЗАТЕЛЬНО НАЧНИТЕ ДИАЛОГ С БОТОМ {context.bot.name} '
                                        f'(нажать start в лс с ним), '
                                        f'чтобы он смог прислать вам ваши карты*🔴',
                                   reply_markup=
                                   InlineKeyboardMarkup([
                                       [InlineKeyboardButton('присоединиться',
                                                             callback_data=
                                                             f'join {update.message["from"]["id"]}')]]),
                                   parse_mode='Markdown')


async def delete_game(update, context):
    # check if user hosts a game
    game = get_game_by_host(update.message.from_user)
    if not game:
        username = f'[{update.message.from_user.first_name}](tg://user?id={update.message.from_user.id})'
        await update.message.reply_text(f'{username} вы не начинали игру', parse_mode='Markdown')
        return

    await context.bot.send_message(chat_id=game.main_chat_id,
                                   text=f'игра, хостом которой являлся {game.get_player_by_user(game.host).name},'
                                        f' была им удалена')
    games.pop(games.index(game))
    # delete used images
    game.delete_used_images()

    username = f'[{update.message.from_user.first_name}](tg://user?id={update.message.from_user.id})'
    await update.message.reply_text(f'{username} ваша игра удалена', parse_mode='Markdown')


async def start_game(update, context):
    game = get_game_by_host(update.message.from_user)
    # start game if exists
    if game:
        game.start()
    await context.bot.send_message(chat_id=game.main_chat_id,
                                   text=f'{game.get_player_by_user(game.host).name} начал игру. '
                                        f'\nПрисоединиться уже не получится')
    # start playing
    await turn_start(update, context, game)


async def turn_start(update, context, game):
    # send all players their cards
    for player in game.players:
        try:
            await context.bot.send_photo(chat_id=player.user.id, caption='Вот ваши карты',
                                         photo=open(game.get_player_cards_image(player), 'rb'))
        except telegram.error.Forbidden:
            # if bot can't send messages to user
            username = f'[{update.message.from_user.first_name}](tg://user?id={update.message.from_user.id})'
            await context.bot.send_message(chat_id=game.main_chat_id, text=f'{player.name} не написал боту! '
                                                                           f'Бот не может прислать карты, '
                                                                           f'{username}'
                                                                           f'пожалуйста, напишите боту 🙏 '
                                                                           f'({context.bot.name})',
                                           parse_mode='Markdown')
            await context.bot.send_message(chat_id=game.main_chat_id, text=f'{game.get_player_by_user(game.host).name} '
                                                                           f'([{game.host.first_name}]'
                                                                           f'(tg://user?id={game.host.id})), '
                                                                           f'начните игру заново, '
                                                                           f'когда все напишут боту! (/start_game)',
                                           parse_mode='Markdown')
            game.game_on = False
            return

    await context.bot.send_message(chat_id=game.main_chat_id, text=f'Ведущий - *{game.current_player.name}*',
                                   parse_mode='Markdown')

    # request an image and description from current player (using command)
    curr_pl = game.current_player
    await context.bot.send_message(text='Ваша очередь ходить. Выберите картинку и напишите ассоциацию к ней\n'
                                        'Формат сообщения: /t 2 жаркий денёк\n'
                                        'Так вы выберете картинку под номером 2 с ассоциацией "жаркий денёк"',
                                   chat_id=curr_pl.user.id)


async def choose_first_card(update, context):
    # return if chat is not private
    if update.message.chat.type != 'private':
        await update.message.reply_text('Напишите боту в личные сообщения')
        return

    # return if player doesn't play a game right now
    player = update.message.from_user
    game = list(filter(lambda x: player in [j.user for j in x.players], games))
    if not game:
        await update.message.reply_text('Вы не играете ни в какую игру')
        return

    # return if player is not a current player
    if game[0].current_player.user != player:
        await update.message.reply_text('Сейчас не ваш ход')
        return

    game = game[0]
    player = game.get_player_by_user(player)

    if player.chosen_card:
        await update.message.reply_text('Вы уже выбрали карту')
        return

    try:
        print(update.message.text.split())
        resp = player.pick_card(int(update.message.text.split()[1]))

        # inform the player if command format is wrong
        if resp.get('error', ''):
            await update.message.reply_text(resp['error'])
            return

        await update.message.reply_text('Карта выбрана')
        # send image description to main chat of the game
        await context.bot.send_message(chat_id=game.main_chat_id,
                                       text=f'выбранная ассоциация: \n'
                                            f'  *{" ".join(update.message.text.split()[2:])}*\n\n'
                                            f'Проверьте личные сообщения с ботом чтобы выбрать карту',
                                       parse_mode='Markdown')

        # send a message to each player (apart from current) asking to choose appropriate card
        # when player presses a button with number (to pick a card) we will check if all players picked card
        # if not: we send a message to main chat informing everyone about who didn't choose card yet
        # else: we shuffle cards, show them and ask everybody to vote (with same algorithm)
        for i in game.players:
            if i.user != player.user:
                await context.bot.send_message(chat_id=i.user.id,
                                               text=f'выберите номер карты подходящей под ассоциацию - '
                                                    f'*{" ".join(update.message.text.split()[2:])}*\n'
                                                    '_Номер карты можно посмотреть над самой картой '
                                                    'на картинке отправленной вам_',
                                               reply_markup=InlineKeyboardMarkup(
                                                   [[InlineKeyboardButton(f'{ind + 1}',
                                                                          callback_data=f'choose {ind + 1}')
                                                     for ind, pl in enumerate(i.cards)]]),
                                               parse_mode='Markdown')

    except Exception:
        await update.message.reply_text('Неверный формат!\n'
                                        'Формат команды: /t номер_карты ассоциация\n'
                                        'чтобы выбрать карту (с этим номером) и с указанной ассоциацией')
        return


async def quit_game(update, context):
    game = list(filter(lambda x: update.message.from_user in [j.user for j in x.players], games))
    if not game:
        username = f'[{update.message.from_user.first_name}](tg://user?id={update.message.from_user.id})'
        await update.message.reply_text(f'{username} в данный момент вы не играете', parse_mode='Markdown')

    game = game[0]
    player = game.get_player_by_user(update.message.from_user)

    # if player is last player
    if len(game.players) == 1:
        await update.message.reply_text(f'Из игры {player.name} вышел последний игрок, она была удалена')
        games.pop(games.index(game))
        game.delete_used_images()

    # if player is host
    elif update.message.from_user == game.host:
        game.host = game.players[game.players.index(player) - 1].user

        username = f'[{game.host.first_name}](tg://user?id={game.host.id})'
        await update.message.reply_text(f'{player.name} вышел из игры! Он был хостом. \n'
                                        f'Новый хост - {username} '
                                        f'(роль хоста дает право завершить '
                                        f'игру заранее и не накладывает никаких обязанностей, не бойтесь)',
                                        parse_mode='Markdown')
        game.players.pop(game.players.index(player))
        game.queue.pop(game.queue.index(player))
        game.local_cards += player.cards

        # if game hasn't started create new join button
        if not game.game_on:
            await new_join_message(update, context, game)

    # if player is not last and not host
    else:
        await update.message.reply_text(f'{player.name} выходит из игры! Карты игрока ушли в раздачу')
        game.players.pop(game.players.index(player))
        game.queue.pop(game.queue.index(player))
        game.local_cards += player.cards


async def kick_player(update, context):
    game = list(filter(lambda x: update.message.from_user in [i.user for i in x.players], games))

    # check if player is in game
    username = f'[{update.message.from_user.first_name}](tg://user?id={update.message.from_user.id})'
    if not game:
        await update.message.reply_text(f'{username}, вы не в игре.', parse_mode='Markdown')
        return
    game = game[0]

    # get list of mentions by user
    ents = list(filter(lambda x: x.type in (telegram.MessageEntity.TEXT_MENTION, telegram.MessageEntity.MENTION),
                       update.message.entities))

    if not ents:
        await update.message.reply_text(f'{username}, формат команды - "/kick упоминание пользователя" '
                                        f'_(чтобы упомянуть пользователя напишите @ и в выпавшем '
                                        f'меню выберите нужного пользователя)_', parse_mode='Markdown')
        return
    if ents[0].type == telegram.MessageEntity.TEXT_MENTION:
        user = ents[0].user
        if user not in [i.user for i in game.players]:
            await update.message.reply_text(f'{username}, пользователя "{user.first_name}" нет в вашей игре',
                                            parse_mode='Markdown')
            return

        player_to_kick = game.get_player_by_user(user)
    else:
        kick_username = update.message.text[ents[0].offset:ents[0].offset + ents[0].length]
        print(kick_username)
        player_to_kick = list(filter(lambda x: x.user.username == kick_username[1:], game.players))
        if not player_to_kick:
            await update.message.reply_text(f'{username}, пользователя "{kick_username}" нет в вашей игре',
                                            parse_mode='Markdown')
            return
        player_to_kick = player_to_kick[0]

    # manage player to kick
    player_to_kick.kick_votes += 1
    votes_enough_to_kick = math.ceil((len(game.players) - 1) * 0.5)

    # if enough votes: kick player and replace host if needed, else write how much votes are left to kick
    if player_to_kick.kick_votes >= votes_enough_to_kick:
        await context.bot.send_message(chat_id=game.main_chat_id, text=f'игрока {player_to_kick.name} '
                                                                       f'выпнули из игры по важной причине')
        # kick
        game.players.pop(game.players.index(player_to_kick))
        if player_to_kick.user == game.host:
            new_host = game.players[-1]
            game.host = new_host.user
            await context.bot.send_message(chat_id=game.main_chat_id, text=f'игрок {player_to_kick.name} '
                                                                           f'был хостом, новый хост - '
                                                                           f'{new_host.name}, (хост может удалить '
                                                                           f'игру, все остальное как обычно)')
            # if game hasn't started create new join button
            if not game.game_on:
                await new_join_message(update, context, game)
    else:
        await update.message.reply_text(f'Выгнать игрока "{player_to_kick.name}" из игры '
                                        f'{game.get_player_by_user(game.host).name}: '
                                        f'{player_to_kick.kick_votes}/{votes_enough_to_kick} голосов',
                                        parse_mode='Markdown')


async def new_join_message(update, context, game):
    game: Imaginarium
    await context.bot.send_message(chat_id=game.main_chat_id, text=f'Новый хост - '
                                                                   f'{game.get_player_by_user(game.host).name}, '
                                                                   f'нажмите *"присоединиться"*, чтобы зайти в игру',
                                   reply_markup=InlineKeyboardMarkup(
                                       [[InlineKeyboardButton('присоединиться', callback_data=f'join {game.host.id}')]]
                                   ),
                                   parse_mode='Markdown')


async def set_max_place(update, context):
    try:
        if not context.args:
            raise ValueError

        max_place = int(context.args[0])

        if max_place <= 0:
            raise ValueError

        game = list(filter(lambda x: update.message.from_user == x.host, games))[0]
        game.max_place = max_place
    except ValueError:
        await update.message.reply_text('Аргумент функции /set_max_place - число > 0')
        return
    except IndexError:
        await update.message.reply_text('Вы не являетесь хостом игры, либо игры не существует')
        return
    else:
        await update.message.reply_text(f'Финальное поле игры {game.get_player_by_user(game.host).name} '
                                        f'изменено на {max_place}')
        return


def main():
    # Создаём объект Application.
    # Вместо слова "TOKEN" надо разместить полученный от @BotFather токен
    application = Application.builder().token(BOT_TOKEN).build()

    # callback for buttons
    callback_handler = CallbackQueryHandler(callback_solver)
    application.add_handler(callback_handler)

    # test
    application.add_handler(CommandHandler('test', test))

    # commands
    application.add_handler(CommandHandler('help', help_bot))
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('rules', help_game))

    application.add_handler(CommandHandler('host', host_game))
    application.add_handler(CommandHandler('set_max_place', set_max_place))
    application.add_handler(CommandHandler('delete', delete_game))
    application.add_handler(CommandHandler('start_game', start_game))
    application.add_handler(CommandHandler('t', choose_first_card))
    application.add_handler(CommandHandler('quit', quit_game))
    application.add_handler(CommandHandler('kick', kick_player))

    # Запускаем приложение.
    application.run_polling()


if __name__ == '__main__':
    main()
