import math

import pygame

pygame.init()
default_background = pygame.transform.scale(pygame.image.load('data/back2.jpg'), (2560, 1600))

surface = pygame.surface.Surface((2560, 1440))
# default card size
card_w, card_h = 360, 540
x_gap, y_gap = 100, 120


font = pygame.font.SysFont('arial', 30, True)


def player_cards_img(player_id, cards_names):
    font_pl_cards = pygame.font.SysFont('arial', 90, True)

    surface.blit(default_background, (0, 0))

    # columns and rows
    col_count = min(3, len(cards_names))
    rows_count = math.ceil(len(cards_names) / col_count)

    # size of card
    x_size, y_size = card_w, card_h

    for ind, i in enumerate(cards_names):
        a = pygame.transform.scale(pygame.image.load(f'data/all_cards/{i}'), (x_size, y_size))

        # img coords
        x, y = (x_gap + (ind % col_count) * (x_size + x_gap),
                y_gap + (ind // col_count) * (y_size + y_gap))

        # card number for player
        text = font_pl_cards.render(str(ind + 1), False, 'white')
        surface.blit(a, (x, y))
        surface.blit(text, (x + x_size // 2, y - 100))

    print(surface, col_count * (x_gap + x_size) + x_gap, rows_count * (y_gap + y_size) + y_gap)
    filename = f'data/players/player_{player_id}.png'
    pygame.image.save(surface.subsurface(0, 0, col_count * (x_gap + x_size) + x_gap,
                                         rows_count * (y_gap + y_size) + y_gap),
                      filename)
    return filename


def players_chosen_cards_img(players, chat_id, vote_line):
    surface.blit(default_background, (0, 0))

    # cards that each player voted for
    players_votes = [vote_line[i.vote_index] for i in players if i.vote_index != -1]

    # params
    col_count = min(5, len(vote_line))
    str_count = math.ceil(len(vote_line) / col_count)

    y_size = min(card_h, (surface.get_height() - (str_count + 1) * y_gap) // str_count)
    x_size = int(card_w / card_h * y_size)

    for ind, i in enumerate(players):
        # player card surface
        a = pygame.transform.scale(pygame.image.load(f'data/all_cards/{i.chosen_card}'), (x_size, y_size))
        # coords on general surface
        x, y = (x_gap + (ind % col_count) * (x_size + x_gap),
                y_gap + (ind // col_count) * (y_size + 90))

        # player name text
        font_card_owners = pygame.font.SysFont('arial', 90, True)
        text = font_card_owners.render(f'({players_votes.count(i.chosen_card)}) {i.name}', False,
                                       'white' if i.vote_index != -1 else 'red')

        # scale text (same with image width)
        x_t1, y_t1 = x_size - 10, (x_size - 10) / text.get_width() * text.get_height()
        x_t2, y_t2 = x_gap / text.get_height() * text.get_width(), x_gap
        text = pygame.transform.scale(text, (x_t1, y_t1) if y_t1 <= x_gap else (x_t2, y_t2))

        surface.blit(a, (x, y))
        surface.blit(text, (x + 10, y - text.get_height() - 5))

    filename = f'data/players/chcards_{chat_id}.png'
    pygame.image.save(surface.subsurface(0, 0, col_count * (x_gap + x_size) + x_gap,
                                         str_count * (y_size + y_gap) + y_gap),
                      filename)
    return filename


def vote_line_img(vote_line, chat_id):
    surface.blit(default_background, (0, 0))

    # size
    col_count = min(5, len(vote_line))
    str_count = math.ceil(len(vote_line) / col_count)

    y_size = min(card_h, (surface.get_height() - (str_count + 1) * y_gap) // str_count)
    x_size = int(card_w / card_h * y_size)

    # images grid
    for ind, i in enumerate(vote_line):
        a = pygame.transform.scale(pygame.image.load(f'data/all_cards/{i}'), (x_size, y_size))
        x, y = (x_gap + (ind % col_count) * (x_size + x_gap),
                y_gap + (ind // col_count) * (y_size + y_gap))

        vote_font = pygame.font.SysFont('arial', 60, True)
        text = vote_font.render(str(ind + 1), False, 'white')

        # resize text so it fits the gap
        x_ts, y_ts = text.get_width() / text.get_height() * x_gap, x_gap
        text = pygame.transform.scale(text, (x_ts, y_ts))

        surface.blit(a, (x, y))
        surface.blit(text, (x + x_size // 2, y - 120))

    filename = f'data/players/vote_chat_{chat_id}.png'
    pygame.image.save(surface.subsurface(0, 0, col_count * (x_size + x_gap) + x_gap,
                                         str_count * (y_size + y_gap) + y_gap),
                      filename)
    return filename
