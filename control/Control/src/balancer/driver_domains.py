from schedule import schedule_builder
import conf_schedule

class Entry(object):
    def __init__(self, start, end, profile_index, domain_size):
        # When is this entry scheudles
        self.schedule_for = start
        
        # Start and end time of the entry
        self.start = start
        self.end = end
        
        # Workload profile
        self.profile_index = profile_index
        
        # Domain size         
        self.domain_size = domain_size
        
        # Reference to the model domain
        self.domain = None
        

class Driver(object):
    def __init__(self, pump, scoreboard, provision):
        # Scoreboard
        self.scoreboard = scoreboard
        
        # Message pump
        self.pump = pump
        
        # Reference to the IaaS helpers
        self.provision = provision
        
        # Heap organized queue
        self.queue = []
        
        
    def start(self):
        # Load schedule with the schedule builder
        loaded = schedule_builder.load_schedule(conf_schedule.SCHEDULE_ID)
        
        # Create queue based on schedule
        abs_time = self.pump.sim_time()
        for sentry in loaded.entries:
            # Skip static entries with predefined domain name
            if sentry.domain_name is not None:
                print 'skipping schedule entry: %s' % sentry.domain_name
                continue
            
            # Start tame based on current simulation time
            start = abs_time + sentry.offset 
            
            # End time based on start time, ramp-up and ramp-down
            end = start + sentry.duration + sentry.rampUp + sentry.rampDown
            
            ientry = Entry(start, end, sentry.workload_profile_index, sentry.domain_size)
            self.queue.append(ientry)
        
        # Sort queue
        self.queue.sort(key=lambda q: q.schedule_for)
        
        
        self.launch = 0
        # Schedule message pump if entries exist
        if self.queue:
            self.pump.callLater(self.queue[0].schedule_for - abs_time, self.run)
        
        
    def run(self) :
        # Get next entry
        current = self.queue.pop(0)
        
        # Get a new domain
        if current.domain is None:
            print 'Handout domain'
            
            # Handout
            current.domain, _ = self.provision.handout(current.profile_index, current.domain_size)
            
            # Update start time (entry gets rescheduled)
            current.schedule_for = current.end
            
            self.launch += 1
            print 'Launches %i' % self.launch
            
            # Re-add entry to queue
            self.queue.append(current)
            
            # Sort queue based on scheudled time
            self.queue.sort(key=lambda q: q.schedule_for)
            
        # Return a domain
        else: 
            print 'Handin domain %s' % current.domain.name
            self.provision.handin(current.domain.name) 

        # If more entries to schedule
        if self.queue:
            wait = self.queue[0].schedule_for - self.pump.sim_time()
            self.pump.callLater(wait, self.run)
        else:
            print 'End of injector queue reached!'
            print 'Driver domains is shutting down simulation...'
            self.scoreboard.close() 
            self.pump.stop()
    
