import time

class Timer(object):
    def __init__(self):
        self.last_tick = time.time() 
        
    def reset(self):
        self.last_tick = time.time()
        
    def last_duration(self):
        return self.delta * 1000
        
    def tick(self):
        curr_time = time.time()
        self.delta = curr_time - self.last_tick
        self.last_tick = curr_time
        return self.delta * 1000
    

timers = []
initial_placement_duration = Timer()
timers.append(initial_placement_duration)

def reset():
    for timer in timers:
        timer.reset() 