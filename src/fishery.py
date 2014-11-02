'''
Created on Oct 31, 2014

@author: vince kane
'''

from random import random
from random import randint
from random import shuffle
from math import exp

"""
Ocean parameters
"""
TheOcean = None
Initial_Population = 1000
ocean_dim = 50

patch_resource = 4
patch_regrow_rate = 0.05  #also used as diffusion rate

FEMALE = 0
MALE = 1

"""
Fish parameters
"""
FRY_SIZE = 0.001
LONGEVITY = 3650  #longevity, days
MATURE_AGE = 365   #age of maturity, days
MATURE_SIZE = 1.0  #how big at MATURE_AGE
SPAWN_SEASON = 14  # how many days does spawning last?
BROOD = 1 # number of spawn produced by pregnancy
MALE_FACTOR = 0.25 #20 male fish results in 99% probablity of pregnancy
CONSUMPTION_RATE = 0.05 # fraction of body mass fish can eat in a setting
MOVE_COST = 1/(5*ocean_dim) # fish can traverse the ocean for 5 days without eating before dying


class Fish(object):
    
    ID = 0
    
    def __init__(self, patch_location):
        self.age = 0
        self.size = FRY_SIZE
        self.gender = FEMALE if random()<0.5 else MALE
        self.health = 1
        self.patch = patch_location
        self.fertile = False
        self.spawning = False
        self.ID = Fish.ID
        Fish.ID += 1
        
    def grow(self):
        if self.age < MATURE_AGE or (self.age > MATURE_AGE and self.health >= 1):
            old_size = self.size
            self.size = MATURE_SIZE*(1 - exp(-3*self.age/MATURE_AGE))  # 3 time constants = ~0.95 of full growth
            self.health -= 2*(self.size - old_size)/(self.size + old_size)
        
    def move(self):
        patches = TheOcean.getNeighborsOf(self.patch)
        patches.append(self.patch)
        attractors = {}
        #calculate food attractors
        food_factor = (1 - self.health) if self.health < 1.0 else 0
        for patch in patches:
            attractors[patch] = food_factor*patch.resource/self.patch.resource
        if self.spawning:
            spawn_attractors = {}
            count = 0
            for patch in patches:
                if self.gender==MALE:
                    spawn_attractor = TheOcean.countMatureFemaleFishAt(patch)
                else:
                    spawn_attractor = TheOcean.countMatureMaleFishAt(patch)
                spawn_attractors[patch] = spawn_attractor
                count += spawn_attractor
            for patch in patches:
                if count >0:
                    attractors[patch] += spawn_attractors[patch]/count  #normalize
                else:
                    attractors[patch] += random()
            
        patches = sorted(patches, key = lambda patch : -attractors[patch])
        if patches[0] != self.patch:
            self.moveTo(patches[0])
    
    def moveTo(self, patch):
        TheOcean.removeFish(self)
        self.patch = patch
        TheOcean.addFish(self)
        self.health -= MOVE_COST #assume patches are adjacent
        self.moves_this_step += 1
        
    def canMove(self):
        return self.moves_this_step < 5
    
    def spawn(self):
        if self.fertile and self.spawning:
            x_mat = TheOcean.countMatureMaleFishAt(self.patch)
            p = 1 - exp(-x_mat*MALE_FACTOR)
            if random()<p:
                for i in range(BROOD):
                    TheOcean.addFish(Fish(self.patch))  # spawn a new fish
                self.spawning = False
    
    def eat(self):
        amount = CONSUMPTION_RATE*self.size
        self.patch.lose(amount)
        self.health += CONSUMPTION_RATE
                
    def step(self, spawning):
        self.age += 1
        self.moves_this_step = 0
        self.health -= MOVE_COST # takes energy to stay in place, too
        if not self.fertile:  #a faster check than the next, saves a few instructions per fish step
            if self.age >= MATURE_AGE and self.gender == FEMALE:
                self.fertile = True
        if spawning==0:
            self.spawning = True  # turn on at the beginning of spawn season
        elif spawning>SPAWN_SEASON:
            self.spawning = False # turn off at the end of spawn season
        
        self.grow()
        while(self.health < 1 and self.canMove()):
            while(self.patch.resource > CONSUMPTION_RATE*self.size and self.health < 1.0):
                self.eat()
            if self.health < 1:
                self.move()
        if (self.spawning and self.canMove()):
            self.move()
        self.spawn()
        
        if self.age > LONGEVITY or self.health < 0.01:  # fish dies
            TheOcean.removeFish(self)
            
                
class Patch(object):
    
    def __init__(self, x, y):
        self.resource = patch_resource
        self.x = x
        self.y = y
        
    def regrow(self):
        if self.resource > 0: # resource can't go negative
            self.resource += patch_regrow_rate*self.resource*(1 - self.resource/patch_resource)  #logistic equation
        else:
            self.resource = 0
    
    def diffuse(self, neighbors):
        amount = patch_regrow_rate*self.resource/8 # amount that diffuses each direction
        self.resource *= (1-patch_regrow_rate) # subtract total amount that diffuses
        for neighbor in neighbors:
            neighbor.resource += amount
            
    def lose(self, amount):
        self.resource -= amount
    
class Ocean(object):

    def __init__(self):
        self.ticks = -1
        self.spawning = -1
        self.fishes_at = {}
        self.patches = {}
        for x in range(ocean_dim):
            for y in range(ocean_dim):
                patch = Patch(x,y)
                self.patches[(x,y)] = patch
                self.fishes_at[patch] = [] #initialize empty array of fishes
              
        # initialize a population of fish  
        for i in range(Initial_Population):
            new_fish = Fish(None)
            x = randint(0, ocean_dim-1)
            y = randint(0, ocean_dim-1)
            new_fish.patch = self.patches[(x,y)]
            new_fish.age = randint(0,LONGEVITY)
            new_fish.size = MATURE_SIZE*(1 - exp(-3*new_fish.age/MATURE_AGE))
            self.addFish(new_fish)
        
    def addFish(self, new_fish):            
        self.fishes_at[new_fish.patch].append(new_fish)
        if new_fish.ID >= Initial_Population:
            pass
        
    def step(self):
        self.ticks += 1
        # first, regrow patches and diffuse resource
        patches = list(self.patches.values())
        shuffle(patches)
        for patch in patches:
            patch.regrow()
            patch.diffuse(self.getNeighborsOf(patch))
        
        if self.ticks%365 <= SPAWN_SEASON:
            self.spawning += 1
        else:
            self.spawning = -1
        # cycle through fish, patch-wise   
        shuffle(patches)
        for patch in patches:
            shuffle(self.fishes_at[patch])
            for fish in self.fishes_at[patch]:
                fish.step(self.spawning)
            
    def getNeighborsOf(self, patch):
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if not (dx==0 and dy==0):
                    x = (patch.x+dx)%ocean_dim
                    y = (patch.y+dy)%ocean_dim
                    neighbors.append(self.patches[(x,y)])
        shuffle(neighbors)
        return neighbors
    
    def countPopulation(self):
        count_abs = 0 #absolute count of fish
        for patch in self.patches.values():
            count_abs += len(self.fishes_at[patch])
        return count_abs
            
    def countMatureMaleFishAt(self, patch):
        count = 0
        for fish in self.fishes_at[patch]:
            if fish.age >= MATURE_AGE and fish.gender==MALE:
                count += 1
        return count
    
    def countMatureFemaleFishAt(self, patch):
        count = 0
        for fish in self.fishes_at[patch]:
            if fish.age >= MATURE_AGE and fish.gender==FEMALE:
                count += 1
        return count
    
    def countMatureFishAt(self, patch):
        count = 0
        for fish in self.fishes_at[patch]:
            if fish.age >= MATURE_AGE:
                count += 1
        return count
    
    def countFishAt(self, patch):
        return len(self.fishes_at[patch])
    
    def removeFish(self, fish):
        self.fishes_at[fish.patch].remove(fish)

if __name__ == '__main__':
    TheOcean = Ocean()
    for step in range(5*365):
        if step%7==0:
            print("week %i:"%int(step/7))
            print("\tpopulation: \t%i"%TheOcean.countPopulation())
        TheOcean.step()
            