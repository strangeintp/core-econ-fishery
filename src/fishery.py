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
Initial_Population = 5000
ocean_dim = 50

patch_resource = 1.0
patch_regrow_rate = 1.0
patch_diffusion_rate = 8.0/9.0 #spread evenly all directions

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
MALE_FACTOR = 0.05 
CONSUMPTION_RATE = 0.05 # fraction of body mass fish can eat in a setting


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
        if self.patch.resource > 0:
            norm = self.patch.resource
        else:
            norm = 1.0
        for patch in patches:
            if patch==self.patch:
                resource = self.patch.resource
            else:
                resource = patch.resource - CONSUMPTION_RATE
            attractors[patch] = food_factor*resource/norm
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
            pass
        
        max_patch = max(iter(attractors.keys()), key = (lambda patch: attractors[patch]))
        if max_patch != self.patch:
            self.moveTo(max_patch)
    
    def moveTo(self, patch):
        TheOcean.moveFishTo(self, patch)
        self.health -= CONSUMPTION_RATE #assume patches are adjacent
        self.moves_this_step += 1
        
    def canMove(self):
        return (self.moves_this_step < 5 and not self.moves_this_step == -1) # -1 for external forcing of no more moves
    
    def spawn(self):
        if self.fertile and self.spawning:
            x_mat = TheOcean.countMatureMaleFishAt(self.patch)
            p = 1 - exp(-x_mat*MALE_FACTOR)
            if random()<p:
                for i in range(BROOD):
                    TheOcean.addFish(Fish(self.patch))  # spawn a new fish
                self.spawning = False #birth only once per season
    
    def eat(self):
        amount = min(CONSUMPTION_RATE*self.size, self.patch.resource)
        self.patch.lose(amount)
        self.health += CONSUMPTION_RATE
                
    def step(self, spawning):
        self.age += 1
        self.moves_this_step = 0
        self.health -= CONSUMPTION_RATE # takes energy to stay in place, too
        if not self.fertile:  #a faster check than the next, saves a few instructions per fish step
            if self.age >= MATURE_AGE and self.gender == FEMALE:
                self.fertile = True
        if spawning==0 and self.age >= MATURE_AGE:
            self.spawning = True  # turn on at the beginning of spawn season
        elif spawning==-1:
            self.spawning = False # turn off at the end of spawn season
        
        self.grow()
        while(self.health < 1 and self.canMove()):
            while(self.patch.resource > 0 and self.health < 1.0):
                self.eat()
            if self.health < 1: # not enough food at current location
                oldpatch = self.patch
                self.move()
                if self.patch==oldpatch: 
                    self.moves_this_step = -1 # prevents infinite loop while spawning
        if (self.spawning and self.canMove()): # look nearby for mates
            self.move()
        self.spawn()
        
        if self.age > LONGEVITY or self.health < 0.01:  # fish dies
            TheOcean.removeDeadFish(self)
            
                
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
        """
        allows "dead" patches to regrow from nearby live patches
        """
        amount = patch_diffusion_rate*self.resource/8 # amount that diffuses each direction
        self.resource *= (1-patch_diffusion_rate) # subtract total amount that diffuses
        for neighbor in neighbors:
            neighbor.resource += amount
            
    def lose(self, amount):
        self.resource -= amount
        if self.resource <= 0:
            pass
    
class Ocean(object):

    def __init__(self):
        self.ticks = -1
        self.spawning = -1
        self.fishes_at = {}
        self.patches = {}
        self.population = 0
        self.fish_births = 0
        self.fish_deaths = 0
        self.total_resource = 0
        for x in range(ocean_dim):
            for y in range(ocean_dim):
                patch = Patch(x,y)
                self.patches[(x,y)] = patch
                self.fishes_at[patch] = [] #initialize empty array of fishes
                self.total_resource += patch.resource
              
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
        self.population += 1
        self.fish_births +=1
        
    def step(self):
        self.ticks += 1
        # first, regrow patches and diffuse resource
        self.total_resource = 0
        self.fish_moved = 0
        patches = list(self.patches.values())
        shuffle(patches)
        for patch in patches:
            patch.regrow()
            self.total_resource += patch.resource
            patch.diffuse(self.getNeighborsOf(patch))
            
        if self.total_resource < 0.1 * ocean_dim**2:
            pass # a breakpoint for debugging
        
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
    
    def removeDeadFish(self, fish):
        self.fishes_at[fish.patch].remove(fish)
        self.population -= 1
        self.fish_deaths += 1
        
    def moveFishTo(self, fish, destination):
        self.fishes_at[fish.patch].remove(fish)
        self.fishes_at[destination].append(fish)
        fish.patch = destination
        self.fish_moved += 1

if __name__ == '__main__':
    TheOcean = Ocean()
    births = TheOcean.fish_births
    deaths = TheOcean.fish_deaths
    pop_integrated = 0
    record_period = 30
    for step in range(20*365):
        TheOcean.step()
        pop_integrated += TheOcean.population
        if step%record_period==0:
            print("%i-day period '# %i:"%(record_period, int(step/record_period)))
            print("\tpopulation: \t%i"%TheOcean.population)
            new_births = TheOcean.fish_births - births
            births = TheOcean.fish_births
            new_deaths = TheOcean.fish_deaths - deaths
            deaths = TheOcean.fish_deaths
            print("\tbirths: \t%i"%new_births)
            print("\tdeaths: \t%i"%new_deaths)
            print("\tresource: \t%f"%TheOcean.total_resource)
            print("\tfish moved: \t%i"%TheOcean.fish_moved)          
            print("\taverage dpop/dt: \t%f"%((TheOcean.fish_births-TheOcean.fish_deaths)/(step+1)))
            print("\taverage population: \t%f"%((pop_integrated)/(step+1)))