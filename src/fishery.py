'''
Created on Oct 31, 2014

@author: vince kane
'''

from random import random
from random import randint
from random import shuffle
from random import gauss
from random import choice
from random import uniform
from math import exp
from math import log

def GenBoundedRandomNormal(meanVal,stdDev,lowerBound,upperBound):
    aRand = gauss(meanVal,stdDev) # could also use: normalvariate()but gauss () is slightly faster.
    while (aRand < lowerBound or aRand > upperBound):
        aRand = random.gauss(meanVal,stdDev)
    return aRand
"""
Ocean parameters
"""
TheOcean = None
Initial_Population = 60000
ocean_dim = 50

patch_resource = 50.0
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
MATURE_SIZE = 0.75  #what fraction of full size at maturity?
MATURE_TAU = MATURE_AGE/-log(1-MATURE_SIZE)  # results in size(age) = 1 - e^-(age/MATURE_AGE)
SPAWN_SEASON = 360  # how many days does spawning last?
SPAWN_BEHAVIOR = False # special behavior for spawning; not really needed for high quantities of fish
BROOD = 2 # number of spawn produced by pregnancy
P_SEASON = 0.99 # probability of brooding during spawn season assuming daily exposure to 50% male population ratio 
METABOLIC_RATE = 0.05 # fraction of body mass fish can eat in a setting; daily energy cost
MOVE_COST = 0.2/ocean_dim

MALE_FACTOR = 2 * (1 - (1-P_SEASON)**(1/SPAWN_SEASON))  # P_DAILY = MALE_FACTOR*MALE_RATIO  ==> produces P_SEASON birth probability @ male_ratio=1/2

def minimumResource(fish):
    return fish.size*METABOLIC_RATE  # assume fish can only extract so much from the environment, proportional to fish size

"""
Boat Parameters
"""
TRANSIENT_DELAY = 0  #moratorium to let initial population transients settle out
DISTANCE = ocean_dim
TECH_VARIANCE = 0
NUM_BOATS = 20
NET_SIZE = 0.8  # what's the smallest fish size the net can catch
HOLD_CAPACITY = 9.9*NET_SIZE
CAPTURE_EFFICIENCY = 0.25

SPAWN_PREVENTION_POLICY = False

patch00 = None

def distanceBetween(patch1, patch2):
    return ( (patch1.x - patch2.x)**2 + (patch1.y-patch2.y)**2)**0.5

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
            self.size = 1 - exp(-self.age/MATURE_TAU)  # reaches MATURE_SIZE at MATURE_AGE
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
                resource = patch.resource - METABOLIC_RATE
            attractors[patch] = food_factor*resource/norm
        if self.spawning and SPAWN_BEHAVIOR:
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
        else:
            self.moves_this_step = -1
    
    def moveTo(self, patch):
        TheOcean.moveFishTo(self, patch)
        self.health -= METABOLIC_RATE #assume patches are adjacent
        self.moves_this_step += 1
        
    def canMove(self):
        return (self.moves_this_step < max(ocean_dim*self.size,1) and not self.moves_this_step == -1) # -1 for external forcing of no more moves
    
    def spawn(self):
        if self.fertile and self.spawning:
            y_mat = TheOcean.getMatureMaleRatioAt(self.patch)
            p = MALE_FACTOR*y_mat
            if random()<p:
                for i in range(BROOD):
                    TheOcean.addFish(Fish(self.patch))  # spawn a new fish
                self.spawning = False #birth only once per season
    
    def eat(self):
        amount = min(METABOLIC_RATE*self.size, self.patch.resource)
        self.patch.lose(amount)
        self.health += METABOLIC_RATE
                
    def step(self, spawning):
        self.age += 1
        self.moves_this_step = 0
        self.health -= METABOLIC_RATE # takes energy to stay in place, too
        if not self.fertile:  #a faster check than the next, saves a few instructions per fish step
            if self.age >= MATURE_AGE and self.gender == FEMALE:
                self.fertile = True
                if spawning >= 0:
                    self.spawning = True
        if spawning==0 and self.age >= MATURE_AGE:
            self.spawning = True  # turn on at the beginning of spawn season
        elif spawning==-1:
            self.spawning = False # turn off at the end of spawn season
        
        self.grow()
        while(self.health < 1 and self.canMove()):
            while(self.patch.resource > minimumResource(self) and self.health < 1.0):
                self.eat()
            if self.health < 1: # not enough food at current location
                self.move()
        while (self.spawning and self.canMove()): # look nearby for mates
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
            new_fish.size = 1 - exp(-new_fish.age/MATURE_TAU)
            self.addFish(new_fish)
        
        self.boats = []    
        for i in range(NUM_BOATS):
            self.boats.append(Boat())
        
    def addFish(self, new_fish):            
        self.fishes_at[new_fish.patch].append(new_fish)
        self.population += 1
        self.fish_births +=1
        
    def step(self):
        self.ticks += 1
        # first, regrow patches and diffuse resource
        self.total_resource = 0
        self.fish_moved = 0
        self.fish_caught = 0
        if self.ticks%365 <= SPAWN_SEASON :
            self.spawning += 1
        else:
            self.spawning = -1
        
        #place boats
        if (self.spawning and SPAWN_PREVENTION_POLICY) or self.ticks <= TRANSIENT_DELAY:
            boats_on_water = []
        else:
            boats_on_water = self.boats[:]
            
        for boat in boats_on_water:
            (x,y) = (randint(0, ocean_dim-1), randint(0, ocean_dim-1))
            start = self.patches[(x,y)]
            boat.beginStep(start)

        # regrow resource    
        patches = list(self.patches.values())
        shuffle(patches)
        for patch in patches:
            patch.regrow()
            self.total_resource += patch.resource
            patch.diffuse(self.getNeighborsOf(patch))        
        
        # cycle through fish, patch-wise   
        shuffle(patches)
        for patch in patches:
            if boats_on_water:
                boat = choice(boats_on_water)
                if boat.update():
                    boats_on_water.remove(boat)  # boat has to go home because ran out of gas or hold full
            fishes = list(self.fishes_at[patch])  # make a list copy so iterable doesn't change when fish die in loop below
            shuffle(fishes)
            for fish in fishes:
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

    def getMatureMaleRatioAt(self, patch):
        mat_count = 0
        male_count = 0
        for fish in self.fishes_at[patch]:
            if fish.age >= MATURE_AGE:
                mat_count += 1
                if fish.gender == MALE:
                    male_count += 1
        return male_count/mat_count
    
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

    def countMaturePopulation(self):
        patches = list(self.patches.values())
        count = 0
        for patch in patches:
            count += sum([1 for fish in self.fishes_at[patch] if fish.age>=MATURE_AGE])
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
        
    def randomPatchNearMe(self, patch):
        dx = 0
        dy = 0
        while(dx==0 and dy==0):
            dx = randint(-1,1)
            dy = randint(-1,1)
        x = (patch.x+dx)%ocean_dim
        y = (patch.y+dy)%ocean_dim
        return self.patches[(x,y)]
    
    def removeCaughtFish(self, fish):
        self.removeDeadFish(fish)
        self.fish_caught += 1
        
class Boat(object):
    
    def __init__(self):
        if TECH_VARIANCE > 0:
            self.max_distance = DISTANCE*GenBoundedRandomNormal(1.0, TECH_VARIANCE, 0.2, 2.0) # how far can a boat travel in a day
            self.hold_capacity = HOLD_CAPACITY*GenBoundedRandomNormal(1.0, TECH_VARIANCE, 0.2, 2.0) # how many fish can it hold
            self.capture_efficiency = CAPTURE_EFFICIENCY*GenBoundedRandomNormal(0.5, TECH_VARIANCE*0.5, 0.1, 0.9) # what fraction can it catch in its patch
            self.detection_noise = uniform(0, TECH_VARIANCE) # how far can it be off in counting
        else:
            self.max_distance = DISTANCE
            self.hold_capacity = HOLD_CAPACITY
            self.capture_efficiency = CAPTURE_EFFICIENCY
            self.detection_noise = 0
        
    def beginStep(self, patch):
        self.distance = distanceBetween(patch00, patch)
        self.hold = 0
        self.patch = patch
        
    def update(self):
        # catch fish here
        self.haulCatch()
        if self.hold < self.hold_capacity and self.detectFishHere() == 0:
            destination = TheOcean.randomPatchNearMe(self.patch)
            self.distance += distanceBetween(self.patch, destination)
            self.patch = destination
            self.haulCatch()
        if self.distance >= self.max_distance or self.hold >= self.hold_capacity:
            return True
        return False
    
    def detectFishHere(self):
        count = TheOcean.countMatureFishAt(self.patch)
        return count*GenBoundedRandomNormal(1.0, self.detection_noise, 0, 2)

    def haulCatch(self):
        catch = [fish for fish in TheOcean.fishes_at[self.patch] if fish.size>NET_SIZE and random()<self.capture_efficiency ]
        shuffle(catch)
        for fish in catch:
            self.hold += fish.size
            TheOcean.removeCaughtFish(fish)
            if self.hold >= self.hold_capacity:
                break
                

if __name__ == '__main__':
    TheOcean = Ocean()
    patch00 = TheOcean.patches[(0,0)]
    births = TheOcean.fish_births
    deaths = TheOcean.fish_deaths
    pop_integrated = 0
    record_period = 30
    fish_caught = 0
    for step in range(20*365):
        TheOcean.step()
        fish_caught += TheOcean.fish_caught
        pop_integrated += TheOcean.population
        if step%record_period==(record_period-1):
            print("%i-day period '# %i:"%(record_period, int(step/record_period)))
            print("\tpopulation: \t%i"%TheOcean.population)
            print("\tmature population: \t%i"%TheOcean.countMaturePopulation())
            new_births = TheOcean.fish_births - births
            births = TheOcean.fish_births
            new_deaths = TheOcean.fish_deaths - deaths
            deaths = TheOcean.fish_deaths
            print("\tbirths: \t%i"%new_births)
            print("\tdeaths: \t%i"%new_deaths)
            print("\tresource: \t%f"%TheOcean.total_resource)
            print("\tfish moved: \t%i"%TheOcean.fish_moved)
            print("\tfish caught: \t%i"%fish_caught)
            fish_caught = 0          
            print("\taverage dpop/dt: \t%f"%((TheOcean.fish_births-TheOcean.fish_deaths)/(step+1)))
            print("\taverage population: \t%f"%((pop_integrated)/(step+1)))
            if TheOcean.population == 0:
                break
