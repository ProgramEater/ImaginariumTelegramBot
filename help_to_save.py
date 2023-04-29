import pygame
import sys


if __name__ == '__main__':
    pygame.init()

    screen = pygame.display.set_mode((1500, 800))
    image = pygame.image.load('temp/Imaginarium Ariadna.jpg')
    image = pygame.transform.scale(image, (image.get_width() * 0.5, image.get_height() * 0.5))
    screen.blit(image, (0, 0))

    x_img, y_img = 0, 0
    x_1, y_1 = 0, 0
    rect = pygame.rect.Rect(0, 0, 0, 0)

    clock = pygame.time.Clock()

    run = True
    index = 210
    while run:
        screen.fill('black')
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                print(index)
                pygame.quit()
                sys.exit()
            mouse = pygame.mouse.get_pressed()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if pygame.mouse.get_pressed()[0]:
                    x_1, y_1 = pygame.mouse.get_pos()
                else:
                    rect.x, rect.y = pygame.mouse.get_pos()

            if event.type == pygame.MOUSEBUTTONUP:
                if rect.w != 0 and rect.h != 0:
                    print(x_img, y_img, rect)
                    pygame.image.save(image.subsurface(rect.x - x_img, rect.y - y_img, rect.w, rect.h),
                                      f'temp/cards/{index}.png')
                    index += 1
                    rect = pygame.rect.Rect(0, 0, 0, 0)

            if mouse[0]:
                pos = pygame.mouse.get_pos()
                x_img += pos[0] - x_1
                y_img += pos[1] - y_1
                x_1, y_1 = pos
            if mouse[2]:
                pos = pygame.mouse.get_pos()
                rect.w = abs(rect.x - pos[0])
                rect.h = abs(rect.y - pos[1])

        screen.blit(image, (x_img, y_img))
        pygame.draw.rect(screen, 'blue', rect, width=1)
        pygame.display.flip()
