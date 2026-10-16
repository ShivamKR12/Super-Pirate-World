from pytmx.util_pygame import load_pygame
from os.path import join
from math import sin
from random import randint, choice, uniform
import pygame, sys
from pygame.math import Vector2 as vector
from os import walk
from pygame.time import get_ticks

pygame.init()


class Data:
	def __init__(self, ui):
		self.ui = ui
		self._coins = 0
		self._health = 5
		self.ui.create_hearts(self._health)

		self.unlocked_level = 0
		self.current_level = 0

	@property
	def coins(self):
		return self._coins

	@coins.setter
	def coins(self, value):
		self._coins = value
		if self.coins >= 100:
			self.coins -= 100
			self.health += 1
		self.ui.show_coins(self.coins)

	@property
	def health(self):
		return self._health

	@health.setter
	def health(self, value):
		self._health = value
		self.ui.create_hearts(value)
		
font = pygame.font.Font(None,30)

def debug(info,y = 10, x = 10):
	display_surface = pygame.display.get_surface()
	debug_surf = font.render(str(info),True,'White')
	debug_rect = debug_surf.get_rect(topleft = (x,y))
	pygame.draw.rect(display_surface,'Black',debug_rect)
	display_surface.blit(debug_surf,debug_rect)

from settings import * 
from random import choice
from timer import Timer # type: ignore

class Tooth(pygame.sprite.Sprite):
	def __init__(self, pos, frames, groups, collision_sprites):
		super().__init__(groups)
		self.frames, self.frame_index = frames, 0
		self.image = self.frames[self.frame_index]
		self.rect = self.image.get_frect(topleft = pos)
		self.z = Z_LAYERS['main']

		self.direction = choice((-1,1))
		self.collision_rects = [sprite.rect for sprite in collision_sprites]
		self.speed = 200

		self.hit_timer = Timer(250)

	def reverse(self):
		if not self.hit_timer.active:
			self.direction *= -1
			self.hit_timer.activate()

	def update(self, dt):
		self.hit_timer.update()

		# animate
		self.frame_index += ANIMATION_SPEED * dt
		self.image = self.frames[int(self.frame_index % len(self.frames))]
		self.image = pygame.transform.flip(self.image, True, False) if self.direction < 0 else self.image

		# move 
		self.rect.x += self.direction * self.speed * dt

		# reverse direction 
		floor_rect_right = pygame.FRect(self.rect.bottomright, (1,1))
		floor_rect_left = pygame.FRect(self.rect.bottomleft, (-1,1))
		wall_rect = pygame.FRect(self.rect.topleft + vector(-1,0), (self.rect.width + 2, 1))

		if floor_rect_right.collidelist(self.collision_rects) < 0 and self.direction > 0 or\
		   floor_rect_left.collidelist(self.collision_rects) < 0 and self.direction < 0 or \
		   wall_rect.collidelist(self.collision_rects) != -1:
			self.direction *= -1

class Shell(pygame.sprite.Sprite):
	def __init__(self, pos, frames, groups, reverse, player, create_pearl):
		super().__init__(groups)

		if reverse:
			self.frames = {}
			for key, surfs in frames.items():
				self.frames[key] = [pygame.transform.flip(surf, True, False) for surf in surfs]
			self.bullet_direction = -1
		else:
			self.frames = frames 
			self.bullet_direction = 1

		self.frame_index = 0
		self.state = 'idle'
		self.image = self.frames[self.state][self.frame_index]
		self.rect = self.image.get_frect(topleft = pos)
		self.old_rect = self.rect.copy()
		self.z = Z_LAYERS['main']
		self.player = player
		self.shoot_timer = Timer(3000)
		self.has_fired = False
		self.create_pearl = create_pearl

	def state_management(self):
		player_pos, shell_pos = vector(self.player.hitbox_rect.center), vector(self.rect.center)
		player_near = shell_pos.distance_to(player_pos) < 500
		player_front = shell_pos.x < player_pos.x if self.bullet_direction > 0 else shell_pos.x > player_pos.x
		player_level = abs(shell_pos.y - player_pos.y) < 30

		if player_near and player_front and player_level and not self.shoot_timer.active:
			self.state = 'fire'
			self.frame_index = 0
			self.shoot_timer.activate()

	def update(self, dt):
		self.shoot_timer.update()
		self.state_management()

		# animation / attack 
		self.frame_index += ANIMATION_SPEED * dt
		if self.frame_index < len(self.frames[self.state]):
			self.image = self.frames[self.state][int(self.frame_index)]

			# fire 
			if self.state == 'fire' and int(self.frame_index) == 3 and not self.has_fired:
				self.create_pearl(self.rect.center, self.bullet_direction)
				self.has_fired = True 

		else:
			self.frame_index = 0
			if self.state == 'fire':
				self.state = 'idle'
				self.has_fired = False

class Pearl(pygame.sprite.Sprite):
	def __init__(self, pos, groups, surf, direction, speed):
		self.pearl = True
		super().__init__(groups)
		self.image = surf
		self.rect = self.image.get_frect(center = pos + vector(50 * direction,0))
		self.direction = direction
		self.speed = speed
		self.z = Z_LAYERS['main']
		self.timers = {'lifetime': Timer(5000), 'reverse': Timer(250)}
		self.timers['lifetime'].activate()

	def reverse(self):
		if not self.timers['reverse'].active:
			self.direction *= -1 
			self.timers['reverse'].activate()

	def update(self, dt):
		for timer in self.timers.values():
			timer.update()

		self.rect.x += self.direction * self.speed * dt
		if not self.timers['lifetime'].active:
			self.kill()

class WorldSprites(pygame.sprite.Group):
	def __init__(self, data):
		super().__init__()
		self.display_surface = pygame.display.get_surface()
		self.data = data
		self.offset = vector()

	def draw(self, target_pos):
		self.offset.x = -(target_pos[0] - WINDOW_WIDTH / 2)
		self.offset.y = -(target_pos[1] - WINDOW_HEIGHT / 2)

		# background
		for sprite in sorted(self, key = lambda sprite: sprite.z):
			if sprite.z < Z_LAYERS['main']:
				if sprite.z == Z_LAYERS['path']:
					if sprite.level <= self.data.unlocked_level:
						self.display_surface.blit(sprite.image, sprite.rect.topleft + self.offset)
				else:
					self.display_surface.blit(sprite.image, sprite.rect.topleft + self.offset)
		# main
		for sprite in sorted(self, key = lambda sprite: sprite.rect.centery):
			if sprite.z == Z_LAYERS['main']:
				if hasattr(sprite, 'icon'):
					self.display_surface.blit(sprite.image, sprite.rect.topleft + self.offset + vector(0,-28))
				else:
					self.display_surface.blit(sprite.image, sprite.rect.topleft + self.offset)

class AllSprites(pygame.sprite.Group):
	def __init__(self, width, height, clouds, horizon_line, bg_tile = None, top_limit = 0):
		super().__init__()
		self.display_surface = pygame.display.get_surface()
		self.offset = vector()
		self.width, self.height = width * TILE_SIZE, height * TILE_SIZE
		self.borders = {
			'left': 0,
			'right': -self.width + WINDOW_WIDTH,
			'bottom': -self.height + WINDOW_HEIGHT,
			'top': top_limit}
		self.sky = not bg_tile
		self.horizon_line = horizon_line

		if bg_tile:
			for col in range(width):
				for row in range(-int(top_limit / TILE_SIZE) - 1, height):
					x, y = col * TILE_SIZE, row * TILE_SIZE
					Sprite((x,y), bg_tile, self, -1)
		else: # sky
			self.large_cloud = clouds['large']
			self.small_clouds = clouds['small']
			self.cloud_direction = -1

			# large cloud 
			self.large_cloud_speed = 50
			self.large_cloud_x = 0
			self.large_cloud_tiles = int(self.width / self.large_cloud.get_width()) + 2
			self.large_cloud_width, self.large_cloud_height = self.large_cloud.get_size()

			# small clouds 
			self.cloud_timer = Timer(2500, self.create_cloud, True)
			self.cloud_timer.activate()
			for cloud in range(20):
				pos = (randint(0,self.width), randint(self.borders['top'], self.horizon_line))
				surf = choice(self.small_clouds)
				Cloud(pos, surf, self)

	def camera_constraint(self):
		self.offset.x = self.offset.x if self.offset.x < self.borders['left'] else self.borders['left']
		self.offset.x = self.offset.x if self.offset.x > self.borders['right'] else self.borders['right'] 
		self.offset.y = self.offset.y if self.offset.y > self.borders['bottom'] else self.borders['bottom']
		self.offset.y = self.offset.y if self.offset.y < self.borders['top'] else self.borders['top']

	def draw_sky(self):
		self.display_surface.fill('#ddc6a1')
		horizon_pos = self.horizon_line + self.offset.y

		sea_rect = pygame.FRect(0,horizon_pos,WINDOW_WIDTH,WINDOW_HEIGHT - horizon_pos)
		pygame.draw.rect(self.display_surface, '#92a9ce', sea_rect)

		# horizon line
		pygame.draw.line(self.display_surface, '#f5f1de', (0,horizon_pos), (WINDOW_WIDTH, horizon_pos), 4)

	def draw_large_cloud(self, dt):
		self.large_cloud_x += self.cloud_direction * self.large_cloud_speed * dt
		if self.large_cloud_x <= -self.large_cloud_width:
			self.large_cloud_x = 0
		for cloud in range(self.large_cloud_tiles):
			left = self.large_cloud_x + self.large_cloud_width * cloud + self.offset.x
			top = self.horizon_line - self.large_cloud_height + self.offset.y
			self.display_surface.blit(self.large_cloud, (left,top))

	def create_cloud(self):
		pos = (randint(self.width + 500, self.width + 600), randint(self.borders['top'], self.horizon_line))
		surf = choice(self.small_clouds)
		Cloud(pos, surf, self)

	def draw(self, target_pos, dt):
		self.offset.x = -(target_pos[0] - WINDOW_WIDTH / 2)
		self.offset.y = -(target_pos[1] - WINDOW_HEIGHT / 2)
		self.camera_constraint()

		if self.sky:
			self.cloud_timer.update()
			self.draw_sky()
			self.draw_large_cloud(dt)

		for sprite in sorted(self, key = lambda sprite: sprite.z):
			offset_pos = sprite.rect.topleft + self.offset
			self.display_surface.blit(sprite.image, offset_pos)

class Level:
	def __init__(self, tmx_map, level_frames, audio_files, data, switch_stage):
		self.display_surface = pygame.display.get_surface()
		self.data = data
		self.switch_stage = switch_stage

		# level data 
		self.level_width = tmx_map.width * TILE_SIZE
		self.level_bottom = tmx_map.height * TILE_SIZE
		tmx_level_properties = tmx_map.get_layer_by_name('Data')[0].properties
		self.level_unlock = tmx_level_properties['level_unlock']
		if tmx_level_properties['bg']:
			bg_tile = level_frames['bg_tiles'][tmx_level_properties['bg']]
		else:
			bg_tile = None

		# groups 
		self.all_sprites = AllSprites(
			width = tmx_map.width, 
			height = tmx_map.height,
			bg_tile = bg_tile, 
			top_limit = tmx_level_properties['top_limit'], 
			clouds = {'large': level_frames['cloud_large'], 'small': level_frames['cloud_small']},
			horizon_line = tmx_level_properties['horizon_line'])
		self.collision_sprites = pygame.sprite.Group()
		self.semi_collision_sprites = pygame.sprite.Group()
		self.damage_sprites = pygame.sprite.Group()
		self.tooth_sprites = pygame.sprite.Group()
		self.pearl_sprites = pygame.sprite.Group()
		self.item_sprites = pygame.sprite.Group()

		self.setup(tmx_map, level_frames, audio_files)

		# frames 
		self.pearl_surf = level_frames['pearl']
		self.particle_frames = level_frames['particle']

		# audio
		self.coin_sound = audio_files['coin']
		self.coin_sound.set_volume(0.4)
		self.damage_sound = audio_files['damage']
		self.damage_sound.set_volume(0.5)
		self.pearl_sound = audio_files['pearl']

	def setup(self, tmx_map, level_frames, audio_files):
		# tiles 
		for layer in ['BG', 'Terrain', 'FG', 'Platforms']:
			for x, y, surf in tmx_map.get_layer_by_name(layer).tiles():
				groups = [self.all_sprites]
				if layer == 'Terrain': groups.append(self.collision_sprites)
				if layer == 'Platforms': groups.append(self.semi_collision_sprites)
				match layer:
					case 'BG': z = Z_LAYERS['bg tiles']
					case 'FG': z = Z_LAYERS['bg tiles']
					case _: z = Z_LAYERS['main']

				Sprite((x * TILE_SIZE,y * TILE_SIZE), surf, groups, z)

		# bg details
		for obj in tmx_map.get_layer_by_name('BG details'):
			if obj.name == 'static':
				Sprite((obj.x, obj.y), obj.image, self.all_sprites, z = Z_LAYERS['bg tiles'])
			else:
				AnimatedSprite((obj.x, obj.y), level_frames[obj.name], self.all_sprites, Z_LAYERS['bg tiles'])
				if obj.name == 'candle':
					AnimatedSprite((obj.x, obj.y) + vector(-20,-20), level_frames['candle_light'], self.all_sprites, Z_LAYERS['bg tiles'])
		
		# objects 
		for obj in tmx_map.get_layer_by_name('Objects'):
			if obj.name == 'player':
				self.player = Player(
					pos = (obj.x, obj.y), 
					groups = self.all_sprites, 
					collision_sprites = self.collision_sprites, 
					semi_collision_sprites = self.semi_collision_sprites,
					frames = level_frames['player'], 
					data = self.data, 
					attack_sound = audio_files['attack'],
					jump_sound = audio_files['jump'])
			else:
				if obj.name in ('barrel', 'crate'):
					Sprite((obj.x, obj.y), obj.image, (self.all_sprites, self.collision_sprites))
				else:
					# frames 
					frames = level_frames[obj.name] if not 'palm' in obj.name else level_frames['palms'][obj.name]
					if obj.name == 'floor_spike' and obj.properties['inverted']:
						frames = [pygame.transform.flip(frame, False, True) for frame in frames]

					# groups 
					groups = [self.all_sprites]
					if obj.name in('palm_small', 'palm_large'): groups.append(self.semi_collision_sprites)
					if obj.name in ('saw', 'floor_spike'): groups.append(self.damage_sprites)

					# z index
					z = Z_LAYERS['main'] if not 'bg' in obj.name else Z_LAYERS['bg details']

					# animation speed
					animation_speed = ANIMATION_SPEED if not 'palm' in obj.name else ANIMATION_SPEED + uniform(-1,1)
					AnimatedSprite((obj.x, obj.y), frames, groups, z, animation_speed)
			if obj.name == 'flag':
				self.level_finish_rect = pygame.FRect((obj.x, obj.y), (obj.width, obj.height))

		# moving objects 
		for obj in tmx_map.get_layer_by_name('Moving Objects'):
			if obj.name == 'spike':
				Spike(
					pos = (obj.x + obj.width / 2, obj.y + obj.height / 2),
					surf = level_frames['spike'],
					radius = obj.properties['radius'],
					speed = obj.properties['speed'],
					start_angle = obj.properties['start_angle'],
					end_angle = obj.properties['end_angle'],
					groups = (self.all_sprites, self.damage_sprites))
				for radius in range(0, obj.properties['radius'], 20):
					Spike(
						pos = (obj.x + obj.width / 2, obj.y + obj.height / 2),
						surf = level_frames['spike_chain'],
						radius = radius,
						speed = obj.properties['speed'],
						start_angle = obj.properties['start_angle'],
						end_angle = obj.properties['end_angle'],
						groups = self.all_sprites,
						z = Z_LAYERS['bg details'])

			else:
				frames = level_frames[obj.name]
				groups = (self.all_sprites, self.semi_collision_sprites) if obj.properties['platform'] else (self.all_sprites, self.damage_sprites)
				if obj.width > obj.height: # horizontal
					move_dir = 'x'
					start_pos = (obj.x, obj.y + obj.height / 2)
					end_pos = (obj.x + obj.width,obj.y + obj.height / 2)
				else: # vertical 
					move_dir = 'y'
					start_pos = (obj.x + obj.width / 2, obj.y)
					end_pos = (obj.x + obj.width / 2,obj.y + obj.height)
				speed = obj.properties['speed']
				MovingSprite(frames, groups, start_pos, end_pos, move_dir, speed, obj.properties['flip'])

				if obj.name == 'saw':
					if move_dir == 'x':
						y = start_pos[1] - level_frames['saw_chain'].get_height() / 2
						left, right = int(start_pos[0]), int(end_pos[0])
						for x in range(left, right, 20):
							Sprite((x,y), level_frames['saw_chain'], self.all_sprites, Z_LAYERS['bg details'])
					else:
						x = start_pos[0] - level_frames['saw_chain'].get_width() / 2
						top, bottom = int(start_pos[1]), int(end_pos[1])
						for y in range(top, bottom, 20):
							Sprite((x,y), level_frames['saw_chain'], self.all_sprites, Z_LAYERS['bg details'])

		# enemies 
		for obj in tmx_map.get_layer_by_name('Enemies'):
			if obj.name == 'tooth':
				Tooth((obj.x, obj.y), level_frames['tooth'], (self.all_sprites, self.damage_sprites, self.tooth_sprites), self.collision_sprites)
			if obj.name == 'shell':
				Shell(
					pos = (obj.x, obj.y), 
					frames = level_frames['shell'], 
					groups = (self.all_sprites, self.collision_sprites), 
					reverse = obj.properties['reverse'], 
					player = self.player, 
					create_pearl = self.create_pearl)

		# items 
		for obj in tmx_map.get_layer_by_name('Items'):
			Item(obj.name, (obj.x + TILE_SIZE / 2, obj.y + TILE_SIZE / 2), level_frames['items'][obj.name], (self.all_sprites, self.item_sprites), self.data)

		# water 
		for obj in tmx_map.get_layer_by_name('Water'):
			rows = int(obj.height / TILE_SIZE) 
			cols = int(obj.width / TILE_SIZE) 
			for row in range(rows):
				for col in range(cols):
					x = obj.x + col * TILE_SIZE
					y = obj.y + row * TILE_SIZE
					if row == 0:
						AnimatedSprite((x,y), level_frames['water_top'], self.all_sprites, Z_LAYERS['water'])
					else:
						Sprite((x,y), level_frames['water_body'], self.all_sprites, Z_LAYERS['water'])

	def create_pearl(self, pos, direction):
		Pearl(pos, (self.all_sprites, self.damage_sprites, self.pearl_sprites), self.pearl_surf, direction, 150)
		self.pearl_sound.play()

	def pearl_collision(self):
		for sprite in self.collision_sprites:
			sprite = pygame.sprite.spritecollide(sprite, self.pearl_sprites, True)
			if sprite:
				ParticleEffectSprite((sprite[0].rect.center), self.particle_frames, self.all_sprites)

	def hit_collision(self):
		for sprite in self.damage_sprites:
			if sprite.rect.colliderect(self.player.hitbox_rect):
				self.player.get_damage()
				self.damage_sound.play()
				if hasattr(sprite, 'pearl'):
					sprite.kill()
					ParticleEffectSprite((sprite.rect.center), self.particle_frames, self.all_sprites)

	def item_collision(self):
		if self.item_sprites:
			item_sprites = pygame.sprite.spritecollide(self.player, self.item_sprites, True)
			if item_sprites:
				item_sprites[0].activate()
				ParticleEffectSprite((item_sprites[0].rect.center), self.particle_frames, self.all_sprites)
				self.coin_sound.play()

	def attack_collision(self):
		for target in self.pearl_sprites.sprites() + self.tooth_sprites.sprites():
			facing_target = self.player.rect.centerx < target.rect.centerx and self.player.facing_right or \
							self.player.rect.centerx > target.rect.centerx and not self.player.facing_right
			if target.rect.colliderect(self.player.rect) and self.player.attacking and facing_target:
				target.reverse()

	def check_constraint(self):
		# left right
		if self.player.hitbox_rect.left <= 0:
			self.player.hitbox_rect.left = 0
		if self.player.hitbox_rect.right >= self.level_width:
			self.player.hitbox_rect.right = self.level_width

		# bottom border 
		if self.player.hitbox_rect.bottom > self.level_bottom:
			self.switch_stage('overworld', -1)

		# success 
		if self.player.hitbox_rect.colliderect(self.level_finish_rect):
			self.switch_stage('overworld', self.level_unlock)

	def run(self, dt):
		self.display_surface.fill('black')
		
		self.all_sprites.update(dt)
		self.pearl_collision()
		self.hit_collision()
		self.item_collision()
		self.attack_collision()
		self.check_constraint()
		
		self.all_sprites.draw(self.player.hitbox_rect.center, dt)
		
class Game:
	def __init__(self):
		pygame.init()
		self.display_surface = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
		pygame.display.set_caption('Super Pirate World')
		self.clock = pygame.time.Clock()
		self.import_assets()

		self.ui = UI(self.font, self.ui_frames)
		self.data = Data(self.ui)
		self.tmx_maps = {
			0: load_pygame(join('..', 'data', 'levels', 'omni.tmx')),
			1: load_pygame(join('..', 'data', 'levels', '1.tmx')),
			2: load_pygame(join('..', 'data', 'levels', '2.tmx')),
			3: load_pygame(join('..', 'data', 'levels', '3.tmx')),
			4: load_pygame(join('..', 'data', 'levels', '4.tmx')),
			5: load_pygame(join('..', 'data', 'levels', '5.tmx')),
			}
		self.tmx_overworld = load_pygame(join('..', 'data', 'overworld', 'overworld.tmx'))
		self.current_stage = Level(self.tmx_maps[self.data.current_level], self.level_frames, self.audio_files, self.data, self.switch_stage)
		self.bg_music.play(-1)

	def switch_stage(self, target, unlock = 0):
		if target == 'level':
			self.current_stage = Level(self.tmx_maps[self.data.current_level], self.level_frames, self.audio_files, self.data, self.switch_stage)
			
		else: # overworld 
			if unlock > 0:
				self.data.unlocked_level = 6
			else:
				self.data.health -= 1
			self.current_stage = Overworld(self.tmx_overworld, self.data, self.overworld_frames, self.switch_stage)

	def import_assets(self):
		self.level_frames = {
			'flag': import_folder('..', 'graphics', 'level', 'flag'),
			'saw': import_folder('..', 'graphics', 'enemies', 'saw', 'animation'),
			'floor_spike': import_folder('..', 'graphics','enemies', 'floor_spikes'),
			'palms': import_sub_folders('..', 'graphics', 'level', 'palms'),
			'candle': import_folder('..', 'graphics','level', 'candle'),
			'window': import_folder('..', 'graphics','level', 'window'),
			'big_chain': import_folder('..', 'graphics','level', 'big_chains'),
			'small_chain': import_folder('..', 'graphics','level', 'small_chains'),
			'candle_light': import_folder('..', 'graphics','level', 'candle light'),
			'player': import_sub_folders('..', 'graphics','player'),
			'saw': import_folder('..', 'graphics', 'enemies', 'saw', 'animation'),
			'saw_chain': import_image('..',  'graphics', 'enemies', 'saw', 'saw_chain'),
			'helicopter': import_folder('..', 'graphics', 'level', 'helicopter'),
			'boat': import_folder('..',  'graphics', 'objects', 'boat'),
			'spike': import_image('..',  'graphics', 'enemies', 'spike_ball', 'Spiked Ball'),
			'spike_chain': import_image('..',  'graphics', 'enemies', 'spike_ball', 'spiked_chain'),
			'tooth': import_folder('..', 'graphics','enemies', 'tooth', 'run'),
			'shell': import_sub_folders('..', 'graphics','enemies', 'shell'),
			'pearl': import_image('..',  'graphics', 'enemies', 'bullets', 'pearl'),
			'items': import_sub_folders('..', 'graphics', 'items'),
			'particle': import_folder('..', 'graphics', 'effects', 'particle'),
			'water_top': import_folder('..', 'graphics', 'level', 'water', 'top'),
			'water_body': import_image('..', 'graphics', 'level', 'water', 'body'),
			'bg_tiles': import_folder_dict('..', 'graphics', 'level', 'bg', 'tiles'),
			'cloud_small': import_folder('..', 'graphics','level', 'clouds', 'small'),
			'cloud_large': import_image('..', 'graphics','level', 'clouds', 'large_cloud'),
		}
		self.font = pygame.font.Font(join('..', 'graphics', 'ui', 'runescape_uf.ttf'), 40)
		self.ui_frames = {
			'heart': import_folder('..', 'graphics', 'ui', 'heart'), 
			'coin':import_image('..', 'graphics', 'ui', 'coin')
		}
		self.overworld_frames = {
			'palms': import_folder('..', 'graphics', 'overworld', 'palm'),
			'water': import_folder('..', 'graphics', 'overworld', 'water'),
			'path': import_folder_dict('..', 'graphics', 'overworld', 'path'),
			'icon': import_sub_folders('..', 'graphics', 'overworld', 'icon'),
		}

		self.audio_files = {
			'coin': pygame.mixer.Sound(join('..', 'audio', 'coin.wav')),
			'attack': pygame.mixer.Sound(join('..', 'audio', 'attack.wav')),
			'jump': pygame.mixer.Sound(join('..', 'audio', 'jump.wav')), 
			'damage': pygame.mixer.Sound(join('..', 'audio', 'damage.wav')),
			'pearl': pygame.mixer.Sound(join('..', 'audio', 'pearl.wav')),
		}
		self.bg_music = pygame.mixer.Sound(join('..', 'audio', 'starlight_city.mp3'))
		self.bg_music.set_volume(0.5)

	def check_game_over(self):
		if self.data.health <= 0:
			pygame.quit()
			sys.exit()

	def run(self):
		while True:
			dt = self.clock.tick() / 1000
			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					pygame.quit()
					sys.exit()

			self.check_game_over()
			self.current_stage.run(dt)
			self.ui.update(dt)
			
			pygame.display.update()

class Overworld:
	def __init__(self, tmx_map, data, overworld_frames, switch_stage):
		self.display_surface = pygame.display.get_surface()
		self.data = data 
		self.switch_stage = switch_stage

		# groups 
		self.all_sprites = WorldSprites(data)
		self.node_sprites = pygame.sprite.Group()

		self.setup(tmx_map, overworld_frames)

		self.current_node = [node for node in self.node_sprites if node.level == 0][0]

		self.path_frames = overworld_frames['path']
		self.create_path_sprites()

	def setup(self, tmx_map, overworld_frames):
		# tiles 
		for layer in ['main', 'top']:
			for x, y, surf in tmx_map.get_layer_by_name(layer).tiles():
				Sprite((x * TILE_SIZE,y * TILE_SIZE), surf, self.all_sprites, Z_LAYERS['bg tiles'])

		# water 
		for col in range(tmx_map.width):
			for row in range(tmx_map.height):
				AnimatedSprite((col * TILE_SIZE,row * TILE_SIZE), overworld_frames['water'], self.all_sprites, Z_LAYERS['bg'])

		# objects 
		for obj in tmx_map.get_layer_by_name('Objects'):
			if obj.name == 'palm':
				AnimatedSprite((obj.x, obj.y), overworld_frames['palms'], self.all_sprites, Z_LAYERS['main'], randint(4,6))
			else:
				z = Z_LAYERS[f'{'bg details' if obj.name == 'grass' else 'bg tiles'}']
				Sprite((obj.x, obj.y), obj.image, self.all_sprites, z)

		# paths
		self.paths = {}
		for obj in tmx_map.get_layer_by_name('Paths'):
			pos = [(int(p.x + TILE_SIZE / 2),int( p.y + TILE_SIZE / 2)) for p in obj.points]
			start = obj.properties['start'] 
			end  = obj.properties['end'] 
			self.paths[end] = {'pos': pos, 'start': start}

		# nodes & player 
		for obj in tmx_map.get_layer_by_name('Nodes'):

			# player
			if obj.name == 'Node' and obj.properties['stage'] == self.data.current_level:
				self.icon = Icon((obj.x + TILE_SIZE / 2, obj.y + TILE_SIZE / 2), self.all_sprites, overworld_frames['icon'])

			# nodes 
			if obj.name == 'Node':
				available_paths = {k:v for k,v in obj.properties.items() if k in ('left', 'right', 'up', 'down')}
				Node(
					pos = (obj.x, obj.y), 
					surf = overworld_frames['path']['node'], 
					groups = (self.all_sprites, self.node_sprites),
					level = obj.properties['stage'],
					data = self.data,
					paths = available_paths)

	def create_path_sprites(self):

		# get tiles from path 
		nodes = {node.level: vector(node.grid_pos) for node in self.node_sprites}
		path_tiles = {}

		for path_id, data in self.paths.items():
			path = data['pos']
			start_node, end_node = nodes[data['start']], nodes[path_id]
			path_tiles[path_id] = [start_node]

			for index, points in enumerate(path):
				if index < len(path) - 1:
					start, end = vector(points), vector(path[index + 1])
					path_dir = (end - start) / TILE_SIZE
					start_tile = vector(int(start[0]/ TILE_SIZE), int(start[1]/ TILE_SIZE))

					if path_dir.y:
						dir_y = 1 if path_dir.y > 0 else -1
						for y in range(dir_y, int(path_dir.y) + dir_y, dir_y):
							path_tiles[path_id].append(start_tile + vector(0,y))

					if path_dir.x:
						dir_x = 1 if path_dir.x > 0 else -1
						for x in range(dir_x, int(path_dir.x) + dir_x, dir_x):
							path_tiles[path_id].append(start_tile + vector(x,0))

			path_tiles[path_id].append(end_node)

		# create sprites 
		for key, path in path_tiles.items():
			for index, tile in enumerate(path):
				if index > 0 and index < len(path) - 1:
					prev_tile = path[index - 1] - tile
					next_tile = path[index + 1] - tile

					if prev_tile.x == next_tile.x:
						surf = self.path_frames['vertical']
					elif prev_tile.y == next_tile.y:
						surf = self.path_frames['horizontal']
					else:
						if prev_tile.x == -1 and next_tile.y == -1 or prev_tile.y == -1 and next_tile.x == -1:
							surf = self.path_frames['tl']
						elif prev_tile.x == 1 and next_tile.y == 1 or prev_tile.y == 1 and next_tile.x == 1:
							surf = self.path_frames['br']
						elif prev_tile.x == -1 and next_tile.y == 1 or prev_tile.y == 1 and next_tile.x == -1:
							surf = self.path_frames['bl']
						elif prev_tile.x == 1 and next_tile.y == -1 or prev_tile.y == -1 and next_tile.x == 1:
							surf = self.path_frames['tr']
						else:
							surf = self.path_frames['horizontal']

					PathSprite(
						pos = (tile.x * TILE_SIZE, tile.y * TILE_SIZE), 
						surf = surf, 
						groups = self.all_sprites, 
						level = key)

	def input(self):
		keys = pygame.key.get_pressed()
		if self.current_node and not self.icon.path:
			if keys[pygame.K_DOWN] and self.current_node.can_move('down'):
				self.move('down')
			if keys[pygame.K_LEFT] and self.current_node.can_move('left'):
				self.move('left')
			if keys[pygame.K_RIGHT] and self.current_node.can_move('right'):
				self.move('right')
			if keys[pygame.K_UP] and self.current_node.can_move('up'):
				self.move('up')
			if keys[pygame.K_RETURN]:
				self.data.current_level = self.current_node.level
				self.switch_stage('level')

	def move(self, direction):
		path_key = int(self.current_node.paths[direction][0])
		path_reverse = True if self.current_node.paths[direction][-1] == 'r' else False
		path = self.paths[path_key]['pos'][:] if not path_reverse else self.paths[path_key]['pos'][::-1]
		self.icon.start_move(path)

	def get_current_node(self):
		nodes = pygame.sprite.spritecollide(self.icon, self.node_sprites, False)
		if nodes:
			self.current_node = nodes[0]

	def run(self, dt):
		self.input()
		self.get_current_node()
		self.all_sprites.update(dt)
		self.all_sprites.draw(self.icon.rect.center)

class Player(pygame.sprite.Sprite):
	def __init__(self, pos, groups, collision_sprites, semi_collision_sprites, frames, data, attack_sound, jump_sound):
		# general setup
		super().__init__(groups)
		self.z = Z_LAYERS['main']
		self.data = data
		
		# image 
		self.frames, self.frame_index = frames, 0
		self.state, self.facing_right = 'idle', True
		self.image = self.frames[self.state][self.frame_index]
		
		# rects
		self.rect = self.image.get_frect(topleft = pos)
		self.hitbox_rect = self.rect.inflate(-76, -36)
		self.old_rect = self.hitbox_rect.copy()

		# movement 
		self.direction = vector()
		self.speed = 200
		self.gravity = 1300
		self.jump = False
		self.jump_height = 900
		self.attacking = False

		# collision 
		self.collision_sprites = collision_sprites
		self.semi_collision_sprites = semi_collision_sprites
		self.on_surface = {'floor': False, 'left': False, 'right': False}
		self.platform = None

		# timer
		self.timers = {
			'wall jump': Timer(400),
			'wall slide block': Timer(250),
			'platform skip': Timer(100),
			'attack block': Timer(500),
			'hit': Timer(400)
		}

		# audio 
		self.attack_sound = attack_sound
		self.jump_sound = jump_sound

	def input(self):
		keys = pygame.key.get_pressed()
		input_vector = vector(0,0)
		if not self.timers['wall jump'].active:
			
			if keys[pygame.K_RIGHT]:
				input_vector.x += 1
				self.facing_right = True
			
			if keys[pygame.K_LEFT]:
				input_vector.x -= 1
				self.facing_right = False
			
			if keys[pygame.K_DOWN]:
				self.timers['platform skip'].activate()

			if keys[pygame.K_x]:
				self.attack()

			self.direction.x = input_vector.normalize().x if input_vector else input_vector.x

		if keys[pygame.K_SPACE]:
			self.jump = True		

	def attack(self):
		if not self.timers['attack block'].active:
			self.attacking = True
			self.frame_index = 0
			self.timers['attack block'].activate()
			self.attack_sound.play()

	def move(self, dt):
		# horizontal 
		self.hitbox_rect.x += self.direction.x * self.speed * dt
		self.collision('horizontal')
		
		# vertical 
		if not self.on_surface['floor'] and any((self.on_surface['left'], self.on_surface['right'])) and not self.timers['wall slide block'].active:
			self.direction.y = 0
			self.hitbox_rect.y += self.gravity / 10 * dt
		else:
			self.direction.y += self.gravity / 2 * dt
			self.hitbox_rect.y += self.direction.y * dt
			self.direction.y += self.gravity / 2 * dt

		if self.jump:
			if self.on_surface['floor']:
				self.direction.y = -self.jump_height
				self.timers['wall slide block'].activate()
				self.hitbox_rect.bottom -= 1
				self.jump_sound.play()
			elif any((self.on_surface['left'], self.on_surface['right'])) and not self.timers['wall slide block'].active:
				self.timers['wall jump'].activate()
				self.direction.y = -self.jump_height
				self.direction.x = 1 if self.on_surface['left'] else -1
				self.jump_sound.play()
			self.jump = False
		
		self.collision('vertical')
		self.semi_collision()
		self.rect.center = self.hitbox_rect.center

	def platform_move(self, dt):
		if self.platform:
			self.hitbox_rect.topleft += self.platform.direction * self.platform.speed * dt

	def check_contact(self):
		floor_rect = pygame.Rect(self.hitbox_rect.bottomleft,(self.hitbox_rect.width,2))
		right_rect = pygame.Rect(self.hitbox_rect.topright + vector(0,self.hitbox_rect.height / 4),(2,self.hitbox_rect.height / 2))
		left_rect  = pygame.Rect(self.hitbox_rect.topleft + vector(-2,self.hitbox_rect.height / 4), (2,self.hitbox_rect.height / 2))
		collide_rects = [sprite.rect for sprite in self.collision_sprites]
		semi_collide_rect = [sprite.rect for sprite in self.semi_collision_sprites]

		# collisions 
		self.on_surface['floor'] = True if floor_rect.collidelist(collide_rects) >= 0 or floor_rect.collidelist(semi_collide_rect) >= 0 and self.direction.y >= 0 else False
		self.on_surface['right'] = True if right_rect.collidelist(collide_rects) >= 0 else False
		self.on_surface['left']  = True if left_rect.collidelist(collide_rects)  >= 0 else False

		self.platform = None
		sprites =  self.collision_sprites.sprites() + self.semi_collision_sprites.sprites()
		for sprite in [sprite for sprite in sprites if hasattr(sprite, 'moving')]:
			if sprite.rect.colliderect(floor_rect):
				self.platform = sprite

	def collision(self, axis):
		for sprite in self.collision_sprites:
			if sprite.rect.colliderect(self.hitbox_rect):
				if axis == 'horizontal':
					# left
					if self.hitbox_rect.left <= sprite.rect.right and int(self.old_rect.left) >= int(sprite.old_rect.right):
						self.hitbox_rect.left = sprite.rect.right

					# right
					if self.hitbox_rect.right >= sprite.rect.left and int(self.old_rect.right) <= int(sprite.old_rect.left):
						self.hitbox_rect.right = sprite.rect.left
				else: # vertical
					# top
					if self.hitbox_rect.top <= sprite.rect.bottom and int(self.old_rect.top) >= int(sprite.old_rect.bottom):
						self.hitbox_rect.top = sprite.rect.bottom
						if hasattr(sprite, 'moving'):
							self.hitbox_rect.top += 6

					# bottom
					if self.hitbox_rect.bottom >= sprite.rect.top and int(self.old_rect.bottom) <= int(sprite.old_rect.top):
						self.hitbox_rect.bottom = sprite.rect.top
					self.direction.y = 0

	def semi_collision(self):
		if not self.timers['platform skip'].active:
			for sprite in self.semi_collision_sprites:
				if sprite.rect.colliderect(self.hitbox_rect):
					if self.hitbox_rect.bottom >= sprite.rect.top and int(self.old_rect.bottom) <= sprite.old_rect.top:
						self.hitbox_rect.bottom = sprite.rect.top
						if self.direction.y > 0:
							self.direction.y = 0

	def update_timers(self):
		for timer in self.timers.values():
			timer.update()

	def animate(self, dt):
		self.frame_index += ANIMATION_SPEED * dt
		if self.state == 'attack' and self.frame_index >= len(self.frames[self.state]):
			self.state = 'idle'
		self.image = self.frames[self.state][int(self.frame_index % len(self.frames[self.state]))]
		self.image = self.image if self.facing_right else pygame.transform.flip(self.image, True, False)

		if self.attacking and self.frame_index > len(self.frames[self.state]):
			self.attacking = False

	def get_state(self):
		if self.on_surface['floor']:
			if self.attacking:
				self.state = 'attack'
			else:
				self.state = 'idle' if self.direction.x == 0 else 'run'
		else:
			if self.attacking:
				self.state = 'air_attack'
			else:
				if any((self.on_surface['left'], self.on_surface['right'])):
					self.state = 'wall'
				else:
					self.state = 'jump' if self.direction.y < 0 else 'fall'

	def get_damage(self):
		if not self.timers['hit'].active:
			self.data.health -= 1
			self.timers['hit'].activate()

	def flicker(self):
		if self.timers['hit'].active and sin(pygame.time.get_ticks() * 100) >= 0:
			white_mask = pygame.mask.from_surface(self.image)
			white_surf = white_mask.to_surface()
			white_surf.set_colorkey('black')
			self.image = white_surf

	def update(self, dt):
		self.old_rect = self.hitbox_rect.copy()
		self.update_timers()
		
		self.input()
		self.move(dt)
		self.platform_move(dt)
		self.check_contact()

		self.get_state()
		self.animate(dt)
		self.flicker()
		
import pygame, sys
from pygame.math import Vector2 as vector

WINDOW_WIDTH, WINDOW_HEIGHT = 1280, 720
TILE_SIZE = 64
ANIMATION_SPEED = 6

# layers 
Z_LAYERS = {
	'bg': 0,
	'clouds': 1,
	'bg tiles': 2,
	'path': 3,
	'bg details': 4,
	'main': 5,
	'water': 6,
	'fg': 7
}

from settings import * 
from math import sin, cos, radians
from random import randint

class Sprite(pygame.sprite.Sprite):
	def __init__(self, pos, surf = pygame.Surface((TILE_SIZE,TILE_SIZE)), groups = None, z = Z_LAYERS['main']):
		super().__init__(groups)
		self.image = surf
		self.rect = self.image.get_frect(topleft = pos)
		self.old_rect = self.rect.copy()
		self.z = z

class AnimatedSprite(Sprite):
	def __init__(self, pos, frames, groups, z = Z_LAYERS['main'], animation_speed = ANIMATION_SPEED):
		self.frames, self.frame_index = frames, 0
		super().__init__(pos, self.frames[self.frame_index], groups, z)
		self.animation_speed = animation_speed

	def animate(self, dt):
		self.frame_index += self.animation_speed * dt
		self.image = self.frames[int(self.frame_index % len(self.frames))]

	def update(self, dt):
		self.animate(dt)

class Item(AnimatedSprite):
	def __init__(self, item_type, pos, frames, groups, data):
		super().__init__(pos, frames, groups)
		self.rect.center = pos
		self.item_type = item_type
		self.data = data

	def activate(self):
		if self.item_type == 'gold':
			self.data.coins += 5
		if self.item_type == 'silver':
			self.data.coins += 1
		if self.item_type == 'diamond':
			self.data.coins += 20
		if self.item_type == 'skull':
			self.data.coins += 50
		if self.item_type == 'potion':
			self.data.health += 1

class ParticleEffectSprite(AnimatedSprite):
	def __init__(self, pos, frames, groups):
		super().__init__(pos, frames, groups)
		self.rect.center = pos
		self.z = Z_LAYERS['fg']

	def animate(self, dt):
		self.frame_index += self.animation_speed * dt
		if self.frame_index < len(self.frames):
			self.image = self.frames[int(self.frame_index)]
		else:
			self.kill()

class MovingSprite(AnimatedSprite):
	def __init__(self, frames, groups, start_pos, end_pos, move_dir, speed, flip = False):
		super().__init__(start_pos, frames, groups)
		if move_dir == 'x':
			self.rect.midleft = start_pos
		else:
			self.rect.midtop = start_pos

		self.start_pos = start_pos
		self.end_pos = end_pos

		# movement
		self.moving = True
		self.speed = speed
		self.direction = vector(1,0) if move_dir == 'x' else vector(0,1)
		self.move_dir = move_dir

		self.flip = flip
		self.reverse = {'x': False, 'y': False}

	def check_border(self):
		if self.move_dir == 'x':
			if self.rect.right >= self.end_pos[0] and self.direction.x == 1:
				self.direction.x = -1
				self.rect.right = self.end_pos[0]
			if self.rect.left <= self.start_pos[0] and self.direction.x == -1:
				self.direction.x = 1
				self.rect.left = self.start_pos[0]
			self.reverse['x'] = True if self.direction.x < 0 else False
		else:
			if self.rect.bottom >= self.end_pos[1] and self.direction.y == 1:
				self.direction.y = -1
				self.rect.bottom = self.end_pos[1]
			if self.rect.top <= self.start_pos[1] and self.direction.y == -1:
				self.direction.y = 1
				self.rect.top = self.start_pos[1]
			self.reverse['y'] = True if self.direction.y > 0 else False

	def update(self, dt):
		self.old_rect = self.rect.copy()
		self.rect.topleft += self.direction * self.speed * dt
		self.check_border()

		self.animate(dt)
		if self.flip:
			self.image = pygame.transform.flip(self.image, self.reverse['x'], self.reverse['y'])

class Spike(Sprite):
	def __init__(self, pos, surf, groups, radius, speed, start_angle, end_angle, z = Z_LAYERS['main']):
		self.center = pos 
		self.radius = radius
		self.speed = speed
		self.start_angle = start_angle
		self.end_angle = end_angle
		self.angle = self.start_angle
		self.direction = 1
		self.full_circle = True if self.end_angle == -1 else False

		# trigonometry
		y = self.center[1] + sin(radians(self.angle)) * self.radius
		x = self.center[0] + cos(radians(self.angle)) * self.radius

		super().__init__((x,y), surf, groups, z)

	def update(self, dt):
		self.angle += self.direction * self.speed * dt

		if not self.full_circle:
			if self.angle >= self.end_angle:
				self.direction = -1
			if self.angle < self.start_angle:
				self.direction = 1


		y = self.center[1] + sin(radians(self.angle)) * self.radius
		x = self.center[0] + cos(radians(self.angle)) * self.radius
		self.rect.center = (x,y)

class Cloud(Sprite):
	def __init__(self, pos, surf, groups, z = Z_LAYERS['clouds']):
		super().__init__(pos, surf, groups, z)
		self.speed = randint(50,120)
		self.direction = -1
		self.rect.midbottom = pos

	def update(self, dt):
		self.rect.x += self.direction * self.speed * dt

		if self.rect.right <= 0:
			self.kill()

class Node(pygame.sprite.Sprite):
	def __init__(self, pos, surf, groups, level, data, paths):
		super().__init__(groups)
		self.image = surf
		self.rect = self.image.get_frect(center = (pos[0] + TILE_SIZE / 2, pos[1] + TILE_SIZE / 2))
		self.z = Z_LAYERS['path']
		self.level = level
		self.data = data
		self.paths = paths
		self.grid_pos = (int(pos[0] / TILE_SIZE), int(pos[1] / TILE_SIZE))

	def can_move(self, direction):
		if direction in list(self.paths.keys()) and int(self.paths[direction][0][0]) <= self.data.unlocked_level:
			return True

class Icon(pygame.sprite.Sprite):
	def __init__(self, pos, groups, frames):
		super().__init__(groups)
		self.icon = True
		self.path = None
		self.direction = vector()
		self.speed = 400

		# image 
		self.frames, self.frame_index = frames, 0
		self.state = 'idle'
		self.image = self.frames[self.state][self.frame_index]
		self.z = Z_LAYERS['main']

		# rect
		self.rect = self.image.get_frect(center = pos)

	def start_move(self, path):
		self.rect.center = path[0]
		self.path = path[1:]
		self.find_path()

	def find_path(self):
		if self.path:
			if self.rect.centerx == self.path[0][0]: # vertical
				self.direction = vector(0, 1 if self.path[0][1] > self.rect.centery else - 1)
			else: # horizontal
				self.direction = vector(1 if self.path[0][0] > self.rect.centerx else - 1, 0)
		else:
			self.direction = vector()

	def point_collision(self):
		if self.direction.y == 1 and self.rect.centery >= self.path[0][1] or \
		   self.direction.y == -1 and self.rect.centery <= self.path[0][1]:
			self.rect.centery = self.path[0][1]
			del self.path[0]
			self.find_path()

		if self.direction.x == 1 and self.rect.centerx >= self.path[0][0] or \
		   self.direction.x == -1 and self.rect.centerx <= self.path[0][0]:
			self.rect.centerx = self.path[0][0]
			del self.path[0]
			self.find_path()

	def animate(self, dt):
		self.frame_index += ANIMATION_SPEED * dt
		self.image = self.frames[self.state][int(self.frame_index % len(self.frames[self.state]))]

	def get_state(self):
		self.state = 'idle'
		if self.direction == vector(1,0):  self.state = 'right'
		if self.direction == vector(-1,0): self.state = 'left'
		if self.direction == vector(0,1):  self.state = 'down'
		if self.direction == vector(0,-1): self.state = 'up'

	def update(self, dt):
		if self.path:
			self.point_collision()
			self.rect.center += self.direction * self.speed * dt
		self.get_state()
		self.animate(dt)

class PathSprite(Sprite):
	def __init__(self, pos, surf, groups, level):
		super().__init__(pos, surf, groups, Z_LAYERS['path'])
		self.level = level
		

def import_image(*path, alpha = True, format = 'png'):
	full_path = join(*path) + f'.{format}'
	return pygame.image.load(full_path).convert_alpha() if alpha else pygame.image.load(full_path).convert()

def import_folder(*path):
	frames = []
	for folder_path, subfolders, image_names in walk(join(*path)):
		for image_name in sorted(image_names, key = lambda name: int(name.split('.')[0])):
			full_path = join(folder_path, image_name)
			frames.append(pygame.image.load(full_path).convert_alpha())
	return frames 

def import_folder_dict(*path):
	frame_dict = {}
	for folder_path, _, image_names in walk(join(*path)):
		for image_name in image_names:
			full_path = join(folder_path, image_name)
			surface = pygame.image.load(full_path).convert_alpha()
			frame_dict[image_name.split('.')[0]] = surface
	return frame_dict

def import_sub_folders(*path):
	frame_dict = {}
	for _, sub_folders, __ in walk(join(*path)): 
		if sub_folders:
			for sub_folder in sub_folders:
				frame_dict[sub_folder] = import_folder(*path, sub_folder)
	return frame_dict

class Timer:
	def __init__(self, duration, func = None, repeat = False):
		self.duration = duration
		self.func = func
		self.start_time = 0
		self.active = False
		self.repeat = repeat

	def activate(self):
		self.active = True
		self.start_time = get_ticks()

	def deactivate(self):
		self.active = False
		self.start_time = 0
		if self.repeat:
			self.activate()

	def update(self):
		current_time = get_ticks()
		if current_time - self.start_time >= self.duration:
			if self.func and self.start_time != 0:
				self.func()
			self.deactivate()

class UI:
	def __init__(self, font, frames):
		self.display_surface = pygame.display.get_surface()
		self.sprites = pygame.sprite.Group()
		self.font = font

		# health / hearts 
		self.heart_frames = frames['heart']
		self.heart_surf_width = self.heart_frames[0].get_width()
		self.heart_padding = 6

		# coins 
		self.coin_amount = 0
		self.coin_timer = Timer(1000)
		self.coin_surf = frames['coin']

	def create_hearts(self, amount):
		for sprite in self.sprites:
			sprite.kill()
		for heart in range(amount):
			x = 10 + heart * (self.heart_surf_width + self.heart_padding)
			y = 10
			Heart((x,y), self.heart_frames, self.sprites)

	def display_text(self):
		if self.coin_timer.active:
			text_surf = self.font.render(str(self.coin_amount), False, '#33323d')
			text_rect = text_surf.get_frect(topleft = (16,34))
			self.display_surface.blit(text_surf, text_rect)

			coin_rect = self.coin_surf.get_frect(center = text_rect.bottomleft).move(0,-6)
			self.display_surface.blit(self.coin_surf, coin_rect)

	def show_coins(self, amount):
		self.coin_amount = amount
		self.coin_timer.activate()

	def update(self, dt):
		self.coin_timer.update()
		self.sprites.update(dt)
		self.sprites.draw(self.display_surface)
		self.display_text()

class Heart(AnimatedSprite):
	def __init__(self, pos, frames, groups):
		super().__init__(pos, frames, groups)
		self.active = False

	def animate(self, dt):
		self.frame_index += ANIMATION_SPEED * dt
		if self.frame_index < len(self.frames):
			self.image = self.frames[int(self.frame_index)]
		else:
			self.active = False
			self.frame_index = 0

	def update(self, dt):
		if self.active:
			self.animate(dt)
		else:
			if randint(0,2000) == 1:
				self.active = True

if __name__ == '__main__':
	game = Game()
	game.run()
	
