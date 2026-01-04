import pygame
import math
import random
import sys

pygame.init()

# Screen and map sizes
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
LEVEL_WIDTH, LEVEL_HEIGHT = 2000, 2000

SCREEN = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Lost in the Void")
CLOCK = pygame.time.Clock()

# Colors
BLACK = (0, 0, 0)
PLAYER_COLOR = (200, 200, 255)
FADE_SPEED = 3

# Settings
RAY_COUNT = 60
RAY_STEP = 4

# DIFFICULTY SETTINGS
difficulties = {
    "easy": {"clap_cooldown": 200, "enemy_speed": 1.5},
    "normal": {"clap_cooldown": 300, "enemy_speed": 2.5},
    "hard": {"clap_cooldown": 400, "enemy_speed": 3.5}
}

difficulty = "normal"
clap_cooldown_max = 300
enemy_base_speed = 2.5


class Camera:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.offset = pygame.Vector2(0, 0)

    def update(self, target_rect):
        self.offset.x = target_rect.centerx - SCREEN_WIDTH // 2
        self.offset.y = target_rect.centery - SCREEN_HEIGHT // 2
        self.offset.x = max(0, min(self.offset.x, self.width - SCREEN_WIDTH))
        self.offset.y = max(0, min(self.offset.y, self.height - SCREEN_HEIGHT))

    def apply(self, rect_or_pos):
        if isinstance(rect_or_pos, pygame.Rect):
            return rect_or_pos.move(-self.offset.x, -self.offset.y)
        else:
            return rect_or_pos[0] - self.offset.x, rect_or_pos[1] - self.offset.y


class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 10, 10)
        self.speed = 3
        self.step_timer = 0

    def move(self, walls):
        keys = pygame.key.get_pressed()
        dx, dy = 0, 0
        moving = False

        if keys[pygame.K_w]: dy = -self.speed; moving = True
        if keys[pygame.K_s]: dy = self.speed; moving = True
        if keys[pygame.K_a]: dx = -self.speed; moving = True
        if keys[pygame.K_d]: dx = self.speed; moving = True

        self.rect.x += dx
        for wall in walls:
            if self.rect.colliderect(wall.rect):
                if dx > 0: self.rect.right = wall.rect.left
                if dx < 0: self.rect.left = wall.rect.right

        self.rect.y += dy
        for wall in walls:
            if self.rect.colliderect(wall.rect):
                if dy > 0: self.rect.bottom = wall.rect.top
                if dy < 0: self.rect.top = wall.rect.bottom

        if moving:
            self.step_timer += 1
            if self.step_timer > 20:
                self.step_timer = 0
                return "step"
        return None

    def draw(self, surface, camera):
        pos = camera.apply(self.rect.center)
        pygame.draw.circle(surface, PLAYER_COLOR, (int(pos[0]), int(pos[1])), 5)


class Wall:
    def __init__(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)


class Enemy:
    def __init__(self, x, y, speed):
        self.rect = pygame.Rect(x, y, 14, 14)
        self.target = None
        self.speed = speed
        self.visible_timer = 0

    def update(self):
        if self.target:
            tx, ty = self.target
            cx, cy = self.rect.center
            angle = math.atan2(ty - cy, tx - cx)
            self.rect.x += math.cos(angle) * self.speed
            self.rect.y += math.sin(angle) * self.speed
            if math.hypot(tx - cx, ty - cy) < 5:
                self.target = None
        else:
            self.rect.x += random.choice([-1, 0, 1])
            self.rect.y += random.choice([-1, 0, 1])
        if self.visible_timer > 0:
            self.visible_timer -= 5

    def hear_sound(self, source_pos):
        self.target = source_pos
        self.visible_timer = 255

    def draw(self, surface, camera):
        if self.visible_timer > 0:
            color = (self.visible_timer, 0, 0)
            pygame.draw.rect(surface, color, camera.apply(self.rect))


class Blip:
    def __init__(self, x, y, life=255):
        self.x = x
        self.y = y
        self.life = life

    def update(self):
        self.life -= FADE_SPEED
        return self.life > 0

    def draw(self, surface, camera):
        pos = camera.apply((self.x, self.y))
        color = (0, self.life, max(0, self.life - 100))
        pygame.draw.circle(surface, color, (int(pos[0]), int(pos[1])), 2)

class Note:
    def __init__(self, x, y, text):
        self.rect = pygame.Rect(x, y, 30, 30)
        self.text = text
        self.read = False

    def draw(self, surface, camera):
        pass
    def check_read(self, player):
        if self.rect.colliderect(player.rect):
            self.read = True
            return self.text
        return None

class FakeEnemy:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.life = random.randint(100, 200)

    def update(self):
        self.life -= 1

    def draw(self, surface, camera):
        pos = camera.apply((self.x, self.y))
        color = (min(255, self.life * 2), 0, min(255, self.life * 2))
        pygame.draw.circle(surface, color, (int(pos[0]), int(pos[1])), 10)

    def dead(self):
        return self.life <= 0

class Pulse:
    def __init__(self, x, y, max_radius, power):
        self.x = x
        self.y = y
        self.radius = 10
        self.max_radius = max_radius
        self.power = power
        self.active = True

    def update(self, walls, blips, enemies):
        self.radius += 6
        for enemy in enemies:
            dist = math.hypot(enemy.rect.centerx - self.x, enemy.rect.centery - self.y)
            if abs(dist - self.radius) < 10:
                enemy.hear_sound((self.x, self.y))

        if self.radius < self.max_radius:
            angle_step = (2 * math.pi) / RAY_COUNT
            for i in range(RAY_COUNT):
                angle = i * angle_step
                px = self.x + math.cos(angle) * self.radius
                py = self.y + math.sin(angle) * self.radius
                if 0 <= px < LEVEL_WIDTH and 0 <= py < LEVEL_HEIGHT:
                    for wall in walls:
                        if wall.rect.collidepoint(px, py):
                            blips.append(Blip(px, py))
                            break
        else:
            self.active = False


class ExitPoint:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 20, 20)

    def draw(self, surface, camera):
        pygame.draw.rect(surface, (0, 180, 255), camera.apply(self.rect))


# Level
def create_level():
    walls = [
        Wall(0, 0, LEVEL_WIDTH, 10),
        Wall(0, LEVEL_HEIGHT - 10, LEVEL_WIDTH, 10),
        Wall(0, 0, 10, LEVEL_HEIGHT),
        Wall(LEVEL_WIDTH - 10, 0, 10, LEVEL_HEIGHT)
    ]
    for _ in range(100):
        w = random.randint(100, 200)
        h = random.randint(100, 200)
        x = random.randint(50, LEVEL_WIDTH - w - 50)
        y = random.randint(50, LEVEL_HEIGHT - h - 50)
        walls.append(Wall(x, y, w, h))
    return walls


# Whisper (phrases)
def get_random_whisper_line():
    whispers = [
        "Someone is nearby...",
        "Are you sure you're alone?",
        "Silence is deceptive.",
        "They hear you.",
        "Don't make noise.",
        "They're already close..."
    ]
    return random.choice(whispers)


# Main menu
def show_menu():
    global difficulty, clap_cooldown_max, enemy_base_speed

    font = pygame.font.SysFont("Courier", 32)
    small_font = pygame.font.SysFont("Courier", 20)

    selected = 0
    options = list(difficulties.keys())

    while True:
        SCREEN.fill(BLACK)
        title = font.render("Lost in the Void", True, (238, 32, 77))
        SCREEN.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 100))

        for i, option in enumerate(options):
            color = (100, 255, 100) if i == selected else (100, 100, 100)
            text = font.render(option.capitalize(), True, color)
            SCREEN.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, 200 + i * 40))

        info = small_font.render("Use UP/DOWN to select, ENTER to start", True, (228, 240, 152))
        SCREEN.blit(info, (SCREEN_WIDTH // 2 - info.get_width() // 2, 400))
        info = small_font.render("Use WASD keys to play", True, (228, 240, 152))
        SCREEN.blit(info, (SCREEN_WIDTH // 2 - info.get_width() // 2, 440))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selected = (selected - 1) % len(options)
                if event.key == pygame.K_DOWN:
                    selected = (selected + 1) % len(options)
                if event.key == pygame.K_RETURN:
                    difficulty = options[selected]
                    clap_cooldown_max = difficulties[difficulty]["clap_cooldown"]
                    enemy_base_speed = difficulties[difficulty]["enemy_speed"]
                    return

        CLOCK.tick(30)


# Main game
def main():
    player = Player(100, 100)
    camera = Camera(LEVEL_WIDTH, LEVEL_HEIGHT)
    walls = create_level()
    exit_point = ExitPoint(LEVEL_WIDTH - 100, LEVEL_HEIGHT - 100)
    enemies = [Enemy(random.randint(200, LEVEL_WIDTH - 200), random.randint(200, LEVEL_HEIGHT - 200), enemy_base_speed) for _ in range(5)]

    pulses = []
    blips = []
    fake_enemies = []

    notes = [
        Note(400, 700, "Someone here... left this."),
        Note(1000, 1100, "Are you sure you're alone?"),
        Note(1800, 1800, "Don't clap twice - they are listening.")
    ]

    sanity = 100
    sanity_timer = 0
    clap_cooldown = 0

    game_over = False
    level_complete = False

    read_note = None
    read_note_timer = 0

    whisper_text = ""
    whisper_timer = 0

    font = pygame.font.SysFont("Courier", 20)

    while True:
        SCREEN.fill(BLACK)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        keys = pygame.key.get_pressed()

        if not game_over and not level_complete:
            action = player.move(walls)

            if action == "step":
                pulses.append(Pulse(player.rect.centerx, player.rect.centery, 100, 2))
                sanity -= 0.5
                sanity_timer = 0

            if keys[pygame.K_SPACE] and clap_cooldown == 0:
                pulses.append(Pulse(player.rect.centerx, player.rect.centery, 600, 1))
                clap_cooldown = clap_cooldown_max
                sanity -= 1
                sanity_timer = 0

            if clap_cooldown > 0:
                clap_cooldown -= 1

            # Silence (reduction of sanity)
            sanity_timer += 1
            if sanity_timer >= 600:
                sanity -= 0.2
                sanity_timer = 0

            sanity = max(0, min(100, sanity))

            # Enemies
            for enemy in enemies:
                enemy.update()
                if player.rect.colliderect(enemy.rect):
                    game_over = True

            # Impulses
            for pulse in pulses[:]:
                pulse.update(walls, blips, enemies)
                if not pulse.active:
                    pulses.remove(pulse)
                else:
                    draw_pos = camera.apply((pulse.x, pulse.y))
                    pygame.draw.circle(SCREEN, (40, 100, 40), draw_pos, int(pulse.radius), 1)

            # Blips
            for blip in blips[:]:
                blip.draw(SCREEN, camera)
                if not blip.update():
                    blips.remove(blip)

            # Update camera
            camera.update(player.rect)

            # Fake (hallucinations)
            if sanity < 30 and random.random() < 0.01:
                fx = player.rect.x + random.randint(-300, 300)
                fy = player.rect.y + random.randint(-300, 300)
                fake_enemies.append(FakeEnemy(fx, fy))

            for fe in fake_enemies[:]:
                fe.draw(SCREEN, camera)
                fe.update()
                if fe.dead():
                    fake_enemies.remove(fe)

            # Player and enemies
            player.draw(SCREEN, camera)
            for enemy in enemies:
                enemy.draw(SCREEN, camera)

            for note in notes:
                note.draw(SCREEN, camera)
                text = note.check_read(player)
                if text and not note.read:
                    read_note = text
                    read_note_timer = 300

            # End of level
            exit_point.draw(SCREEN, camera)
            if player.rect.colliderect(exit_point.rect):
                level_complete = True

            # UI HUD

            # Sanity scale
            pygame.draw.rect(SCREEN, (50, 50, 50), (10, 10, 200, 10))
            sane_color = (0, 120, 255) if sanity > 30 else (255, 100, 100)
            pygame.draw.rect(SCREEN, sane_color, (10, 10, int((sanity / 100) * 200), 10))

            # Cotton cooldown
            cd = 0 if clap_cooldown == 0 else clap_cooldown // 60
            info = font.render(f"SPACE = Clap | Cooldown: {cd}", True, (120, 255, 120))
            SCREEN.blit(info, (10, 25))

            # Displaying a note
            if read_note_timer > 0 and read_note:
                txt = font.render(f"\"{read_note}\"", True, (180, 180, 180))
                SCREEN.blit(txt, (SCREEN_WIDTH // 2 - txt.get_width() // 2, SCREEN_HEIGHT - 40))
                read_note_timer -= 1

            # Whispers
            whisper_timer -= 1
            if whisper_timer <= 0 and sanity < 60:
                whisper_text = get_random_whisper_line()
                whisper_timer = random.randint(300, 600)

            if whisper_text:
                whisper_surf = font.render(whisper_text, True, (224, 255, 255))
                SCREEN.blit(whisper_surf, (20, SCREEN_HEIGHT - 20))

            # Visual consequences of madness
            if sanity < 25:
                SCREEN.scroll(random.choice([-1, 0, 1]), random.choice([-1, 0, 1]))
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
                overlay.set_alpha(20)
                overlay.fill((random.randint(0, 40), 0, random.randint(0, 40)))
                SCREEN.blit(overlay, (0, 0))

            if sanity <= 0:
                game_over = True

        elif game_over:
            msg = pygame.font.SysFont("Courier", 50).render("YOU LOST YOURSELF", True, (255, 0, 0))
            SCREEN.blit(msg, (SCREEN_WIDTH // 2 - msg.get_width() // 2, SCREEN_HEIGHT // 2))

        elif level_complete:
            msg = pygame.font.SysFont("Courier", 40).render("You survived.", True, (0, 255, 200))
            SCREEN.blit(msg, (SCREEN_WIDTH // 2 - msg.get_width() // 2, SCREEN_HEIGHT // 2))

        pygame.display.flip()
        CLOCK.tick(60)

if __name__ == "__main__":
    show_menu()
    main()