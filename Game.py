from random import randint, shuffle
import os
from image_generator import vote_line_img, player_cards_img, players_chosen_cards_img

# names of all available cards
cards_names = list(os.walk('data/all_cards', True))[0][2]


class Player:
    def __init__(self, user, cards, parent):
        # parent game
        self.parent: Imaginarium = parent

        # player user (update.message.author)
        self.user = user
        self.name = self.user.first_name + ' ' + (self.user.last_name if self.user.last_name is not None else '')
        # list of his current cards
        self.cards = cards
        # place on the map
        self.place = 1
        # current chosen card
        self.chosen_card = ''

        # index of voted card
        self.vote_index = -1

        # votes for kicking the player from game
        self.kick_votes = 0

    def pick_card(self, number):
        if not 0 <= number - 1 < len(self.cards) + int(bool(self.chosen_card)):
            return {'error': f'нет карты с номером {number}'}

        # if we had chosen card we add that back to all cards
        if self.chosen_card:
            self.cards.append(self.chosen_card)

        self.chosen_card = self.cards.pop(number - 1)

        return dict()

    def vote_for_card(self, number):
        if self.chosen_card == self.parent.vote_line[number - 1]:
            return {'error': 'вы не можете голосовать за свою карту'}

        self.vote_index = number - 1
        return dict()


class Imaginarium:
    def __init__(self, main_chat_id, host):
        self.main_chat_id = main_chat_id

        self.max_place = 30
        # --------------------------------------------------------------------------------------------------------------

        # host of the game (update.message.from_user)   :telegram.User
        self.host = host

        # names of local available cards
        self.local_cards = cards_names.copy()
        # names of cards that were played (if there's not enough cards we will shuffle them and add to local cards)
        self.burnt_cards = list()

        # list of players and their cards   player_id: [cards]
        self.players = []

        # player_username whose turn is at the moment
        self.current_player: Player = Player
        # an order of players' moves
        self.queue = []

        # line of images for voting
        self.vote_line = []
        # id of message with vote buttons
        # needed to prevent players from clicking old inactive votes
        self.vote_message_id = -1

        # if game is active - True else False
        self.game_on = False

    def add_player(self, player):
        # player: telegram.User
        if not self.game_on:
            self.players.append(Player(player,
                                       [self.local_cards.pop(randint(0, len(self.local_cards) - 1)) for i in range(6)],
                                       self))

    def delete_player(self, player):
        self.queue.pop()

    def start(self):
        self.game_on = True

        self.queue = self.players.copy()
        shuffle(self.queue)

        self.current_player = self.queue[0]

    def make_vote_line(self):
        # if someone didn't pick a card
        if [i.chosen_card for i in self.players].count('') > 0:
            # if only 1 player didn't
            if [i.chosen_card for i in self.players].count('') == 1:
                last_player = list(filter(lambda x: not x.chosen_card and x != self.current_player, self.players))[0]
                return {'error': f'Игрок {last_player.name} - единственный, кто не выбрал карту...'}
            else:
                return {'error': 'ignore'}

        self.vote_line = [i.chosen_card for i in self.players]
        shuffle(self.vote_line)
        return {'image': vote_line_img(self.vote_line, self.main_chat_id)}

    def conclusion(self):
        # all players excluding current player
        normal_players = [i for i in self.players if i != self.current_player]

        # if all vote indexes are not -1 (apart from 1 which is current player who doesn't vote): we are good,
        # else we return
        if [i.vote_index for i in normal_players].count(-1) > 0:
            if [i.vote_index for i in normal_players].count(-1) == 1:
                last_player = list(filter(lambda x: x.vote_index == -1 and x != self.current_player, normal_players))[0]
                return {'error': f'Игрок {last_player.name} - до сих пор не проголосовал... (Он последний вообще-то!)'}
            return {'error': ''}

        # if everybody guessed right card they move 3 forward (apart from current player)
        if all([self.current_player.chosen_card == self.vote_line[i.vote_index] for i in normal_players]):
            for i in normal_players:
                i.place += 3

        # if nobody guessed right card they move as much forward as much players picked their card
        elif all([self.current_player.chosen_card != self.vote_line[i.vote_index] for i in normal_players]):
            # name of cards players voted for
            players_votes = [self.vote_line[i.vote_index] for i in normal_players]

            for i in normal_players:
                i.place += players_votes.count(i.chosen_card)

        # if somebody (but not everybody) guessed right card
        else:
            # name of cards player voted for
            players_votes = [self.vote_line[i.vote_index] for i in normal_players]

            # in self.players because current player also gets 3 moves forward and 1 for each person who picked his card
            for i in self.players:
                i.place += players_votes.count(i.chosen_card)
                if self.current_player.chosen_card == self.vote_line[i.vote_index]:
                    i.place += 3

        # response
        resp = dict()

        # make an image (whose card was each card)
        resp['img'] = players_chosen_cards_img(self.players, self.main_chat_id, self.vote_line)

        # pick next current player
        self.current_player = self.queue[(self.queue.index(self.current_player) + 1) % len(self.queue)]

        # all the cards that were voted for go to burnt cards
        self.burnt_cards += self.vote_line
        self.vote_line.clear()
        self.vote_message_id = -1

        # make all changing values default again and give all players one new card (with index 0)
        for i in self.players:
            # if somebody wanted to kick player but there's conclusion: we reset kick votes to 0
            i.kick_votes = 0

            i.chosen_card = ''
            i.vote_index = -1
            # if there's not enough cards to give 1 card to each player:
            # we shuffle burnt cards and put them in local cards
            if len(self.local_cards) < len(self.players):
                shuffle(self.burnt_cards)
                self.local_cards += self.burnt_cards
                self.burnt_cards.clear()
                resp['no cards'] = True
            i.cards.append(self.local_cards.pop(0))

            if i.place >= self.max_place:
                resp['win'] = resp.get('win', []) + [i]

        resp['success'] = "\n".join(sorted([f"*{pl.name}* на поле *{pl.place}*" for pl in self.players],
                                           key=lambda x: int(x.split()[-1][1:-1]), reverse=True))

        return resp

    def get_player_cards_image(self, player):
        try:
            print(self.players[0].user, player)
            return player_cards_img(player.user.id, list(filter(lambda x: x == player, self.players))[0].cards)
        except IndexError:
            return 'error'

    def get_player_by_user(self, user):
        try:
            return list(filter(lambda x: user == x.user, self.players))[0]
        except IndexError:
            return None
