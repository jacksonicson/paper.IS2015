from workload import load, wtimes_meta
from workload.timeutil import minu, hour
import bisect
import cdf_random
import clparams
import conf_domains
import conf_domainsize
import conf_load
import configuration
import heapq
import itertools
import json
import numpy as np
import random
import sys

# Constants
SCH_RAMP_UP = minu(10)  # Ramp up duration of the experiment
SCH_RAMP_DOWN = minu(10)  # Ramp down duration of the experiment
ID_START_STATIC = 10000
ID_START_DYNAMIC_PRODUCTION = 20000
ID_START_DYNAMIC_SENSITIVITY = 30000
EXPERIMENT_DURATION = hour(6)  # 6 hours steady-state duration of a static experiment

'''
Difference between Lifetime and Duration:
 
- Lifetime = How long is a VM running it includes ramp-up, ramp-down, and duration
- Lifetime = ramp-up + duration + ramp-down
- Duration = length of the steady-state load generation
'''

'''
Domain sizes:

Domain size describes the domain set index that will be used while running the schedule. The set
information will ***only be used to calculate the number of domain types***. Domain sizes are not
stored in the schedule!
'''

# Override configuration by command line parameters
clparams.load_parameters(sys.modules[__name__])

class Entry(object):
    def __init__(self):
        # Target VM factory to generate targets
        self.targetFactory = 'specj'
        
        # Start offset 
        self.offset = 0
        
        # Execution duration
        self.duration = 0
        
        # Ramp up and ramp down time
        self.rampUp = SCH_RAMP_UP
        self.rampDown = SCH_RAMP_DOWN
        
        # Domain size
        self.domain_size = 0
               
        # Workload profile identifier
        self.workload_profile_index = 0
        
        # Offset within the workload profile 
        self.workload_profile_offset = 0
        
        # Domain name
        self.domain_name = None
        
    def load(self, json):
        self.targetFactory = json['targetFactory']
        self.offset = json['offset'] 
        self.domain_size = int(json['domainSize'])
        self.duration = json['duration'] 
        self.rampUp = json['rampUp'] 
        self.rampDown = json['rampDown'] 
        self.workload_profile_index = json['workloadProfileIndex'] 
        self.workload_profile_offset = json['workloadProfileOffset']
        
        # Load domain name if it exists
        if 'domainName' in json:
            self.domain_name = json['domainName']
#        
        
    def getJSON(self):
        json = {}
        json['targetFactory'] = self.targetFactory
        json['offset'] = self.offset
        json['domainSize'] = self.domain_size
        json['duration'] = self.duration
        json['rampUp'] = self.rampUp
        json['rampDown'] = self.rampDown
        json['workloadProfileIndex'] = self.workload_profile_index
        json['workloadProfileName'] = load.get_user_profile_name(self.workload_profile_index, self.domain_size)
        json['workloadProfileOffset'] = self.workload_profile_offset
        
        # Write domain name 
        if self.domain_name is not None: 
            json['domainName'] = self.domain_name
        
        return json
        
    def __str__(self):
        return '%i' % self.offset


class Schedule(object):
    def __init__(self, schedule_id, parallelity=None, initial_entries=None,
                 domain_size_set=None, schedule_file=None):
        # Schedule ID is always required
        self.schedule_id = schedule_id
        
        # Initial entries
        if not initial_entries:
            self.entries = []
        else:
            self.entries = initial_entries
        
        if schedule_file is None:
            # Maximum parallelity allowed by this schedule 
            self.parallelity = parallelity
            
            # Domain size set
            self.domain_size_set = domain_size_set
        else:
            self.__load(schedule_file)
        
    
    def add(self, offset, domain_size, duration, workload_profile_index, workload_profile_offset,
            domain_name=None, ramp_up=SCH_RAMP_UP):
        new_entry = Entry()
        new_entry.offset = offset
        new_entry.domain_size = domain_size
        new_entry.duration = duration
        new_entry.workload_profile_index = workload_profile_index
        new_entry.workload_profile_offset = workload_profile_offset
        new_entry.domain_name = domain_name
        new_entry.rampUp = ramp_up
        
        if self.__validate_entry(new_entry):
            self.entries.append(new_entry)
            return True
        
        return False 
       
    def __validate_entry(self, new_entry):
        stack = self.get_parallelity(new_entry)
        return stack <= self.parallelity
       
    def get_end_time(self):
        max_end = 0
        for entry in self.entries:
            max_end = max(max_end, entry.offset + entry.duration)
        return max_end
        
    def interleave(self, driver_count):
        '''
        Split this schedule into multiple schedules to be conduncted on 
        different drivers in parallel 
        '''
        
        # Sort entries by offset
        self.entries.sort(key=lambda e: e.offset)
        
        # Interleave schedule on all drivers
        entry_sublists = [[] for _ in xrange(driver_count)]
        for i, entry in enumerate(self.entries):
            entry_sublists[i % driver_count].append(entry)
        
        # Calculate delays for each schedule individually
        schedules = []
        for sublist in entry_sublists:
            schedule = Schedule(self.schedule_id, self.parallelity, sublist, self.domain_size_set)
            schedules.append(schedule)
                
        # Return schedules
        return schedules
    
    def save(self, driver_count, schedule_file):
        # Serializable object
        data = {
                'schedule_id' : self.schedule_id,
                'domain_size_set' : self.domain_size_set,
                'schedules' : []
                }
        
        # Interleave schedule
        schedules = self.interleave(driver_count)
        
        # Build JSON string representation of each schedule
        for schedule in schedules:
            # Get JSON of each entry
            tsched = []
            for entry in schedule.entries:
                tsched.append(entry.getJSON())
                
            # Convert entries to JSON string
            data['schedules'].append(tsched)
            
        # Save schedules to a file
        fh = open(schedule_file, 'w')
        fh.write(json.dumps(data))
        fh.close()
        

    def __load(self, schedule_file):
        # Load file contents
        fh = open(schedule_file, 'r')
        config = fh.readline()
        fh.close()
        
        # JSON transform
        config = json.loads(config)
        
        # Get settings
        self.schedule_id = config['schedule_id']
        self.domain_size_set = config['domain_size_set']
        
        # Get schedules
        for schedule in config['schedules']:
            for entry in schedule:
                new_entry = Entry()
                new_entry.load(entry)
                self.entries.append(new_entry)
                
            # Sort entries by offset
            self.entries.sort(key=lambda e: e.offset)    
        
    def validate_production(self):
        # Heap that holds start and stop events            
        active_heap = []
        
        # Add existing entries (consider some safety buffer too)
        for entry in self.entries:
            heapq.heappush(active_heap, (entry.offset - minu(1), True, entry))
            heapq.heappush(active_heap, (entry.offset - + entry.duration + entry.rampUp + entry.rampDown + minu(1), False, entry))
        
        # Simulate active server count by a stack
        stack = []
        max_stack = 0
        while active_heap:
            ad = heapq.heappop(active_heap)
            if ad[1]: stack.append(ad[2])
            else: del stack[stack.index(ad[2])]
            max_stack = max(len(stack), max_stack)
            
            
            
        # Return max stack depth
        return max_stack
        
    def get_parallelity(self, entry=None):
        # Heap that holds start and stop events            
        active_heap = []
        
        if entry is not None: 
            # Add new entry to the heap with some safety buffer
            heapq.heappush(active_heap, (entry.offset - minu(1), True))
            heapq.heappush(active_heap, (entry.offset + entry.duration + entry.rampDown + entry.rampUp + minu(1), False))
        
        # Add existing entries
        for entry in self.entries:
            heapq.heappush(active_heap, (entry.offset - minu(1), True))
            heapq.heappush(active_heap, (entry.offset + entry.duration + entry.rampUp + entry.rampDown + minu(1), False))
        
        # Simulate active server count by a stack
        stack = 0
        max_stack = 0
        while active_heap:
            ad = heapq.heappop(active_heap)
            if ad[1]: stack += 1
            else: stack -= 1
            max_stack = max(stack, max_stack)
            
        # Return max stack depth
        return max_stack
    

    def plot_gantt_chart(self, schedule_id, out=None, suffix='png'):
        '''
        Plot this schedule in a gantt chart to visualize it
        '''
        
        import matplotlib.pyplot as plt
        
        # Setup figure
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.set_xlabel('Time in Seconds')
        ax.set_ylabel('Virtual Machine')
        
        # Create offset and width information for boxes (= entries)
        offsets = []
        widths = []
        bottoms = [] 
        for i , entry in enumerate(self.entries):
            
            offsets.append(entry.offset)
            widths.append(entry.rampUp)
            
            offsets.append(entry.offset + entry.rampUp)
            widths.append(entry.duration)
            
            offsets.append(entry.offset + entry.duration + entry.rampUp)
            widths.append(entry.rampDown)
            
            bottoms.append(i)
            bottoms.append(i)
            bottoms.append(i) 
        
        # Plot boxes
        ax.barh(bottoms, widths, height=1, color=('gray', 'black', 'gray'), edgecolor='white', left=offsets)
        if out is None:
            plt.show()
        else:
            plt.savefig(configuration.path('gantt_%i' % schedule_id, suffix))


    def get_domain_size_set(self):
        return self.domain_size_set


class ScheduleBuilder():
    pass

class StaticScheduleBuilder(ScheduleBuilder):
    '''
    Builds a new Schedule class with entries
    '''
    
    def __init__(self, launches):
        self.launches = launches
        
    def build(self, schedule_id):
        # Create a new schedule
        schedule = Schedule(schedule_id, 500, None, 0)
        
        for workload_index in xrange(self.launches): 
            # Try adding entry to schedule
            start_time = workload_index * minu(1)
            workload_offset = 0
            ramp_up = (self.launches - workload_index) * minu(1) + SCH_RAMP_UP
            
            duration = EXPERIMENT_DURATION
            success = schedule.add(start_time, conf_domainsize.DEFAULT, duration,
                                   workload_index, workload_offset,
                                   conf_domains.initial_domains[workload_index].name,
                                   ramp_up)
            if not success:
                print 'ERROR: Could not add static schedule entry'
    
        # Return schedule
        return schedule
    

class DynamicScheduleBuilder(ScheduleBuilder):
    '''
    Builds a new Schedule class with entries
    '''
    INTER_ARRIVAL_S1 = 0
    INTER_ARRIVAL_S5 = 1
    
    LIFETIME_UNPOPULAR = 0
    LIFETIME_S1 = 1
    LIFETIME_MIX = 2
    
    def __init__(self,
                 max_duration,
                 max_parallelity,
                 launches,
                 domain_size,
                 inter_arrival,
                 lifetime,
                 scale_arrival,
                 scale_duration):
        
        # Lifetime minimum is enforced
        self.lifetime_min = True
        
        # Domain launches
        self.launches = launches
        
        # Maximum number of VMs that are allowed to run in parallel
        self.max_parallelity = max_parallelity
        
        # Maximum duration
        self.max_duration = max_duration
        
        # Scaling
        self.scale_arrival = scale_arrival
        self.scale_duration = scale_duration
        
        # Configure VM sizes (ensure correct parameter setting)
        self.conf_domain_size = domain_size
        
        # Configuration for domain inter arrival time
        self.inter_arrival_cdf = inter_arrival
        if self.inter_arrival_cdf == DynamicScheduleBuilder.INTER_ARRIVAL_S1:
            self.inter_arrival = cdf_random.CDFRandomNumber('cdf_interval_arrivals_s1')
        elif self.inter_arrival_cdf == DynamicScheduleBuilder.INTER_ARRIVAL_S5:    
            self.inter_arrival = cdf_random.CDFRandomNumber('cdf_interval_arrivals_s5')
        
        # Configuration for domain lifetime
        self.random_lifetime_cdf = lifetime
        self.random_lifetime = []
        if self.random_lifetime_cdf == DynamicScheduleBuilder.LIFETIME_UNPOPULAR:
            self.random_lifetime.append((1, cdf_random.CDFRandomNumber('cdf_popular_unpopular_instance_lifetime_unpopular')))
        if self.random_lifetime_cdf == DynamicScheduleBuilder.LIFETIME_S1:
            self.random_lifetime.append((1, cdf_random.CDFRandomNumber('cdf_instance_lifetime_s1')))
        elif self.random_lifetime_cdf == DynamicScheduleBuilder.LIFETIME_MIX:
            self.random_lifetime.append((0.2, cdf_random.CDFRandomNumber('cdf_popular_unpopular_instance_lifetime_unpopular')))
            self.random_lifetime.append((0.6, cdf_random.CDFRandomNumber('cdf_popular_unpopular_instance_lifetime_all')))
            self.random_lifetime.append((0.2, cdf_random.CDFRandomNumber('cdf_popular_unpopular_instance_lifetime_popular')))
    
    
    def __workoad(self, size, duration):
        # Uniform distribution for random workload 
        available = load.count()
        return random.randint(0, available - 1)


    def __domain_size(self):
        # Pick a size by their probabilites
        rand = random.random()
        curr_probability = 0
        for i, domain_size in enumerate(conf_domainsize.size_set[self.conf_domain_size]):
            curr_probability += domain_size.probability()
            if rand <= curr_probability:
                return i
    
    
    def __inter_arrival(self, entry_index):
        # First entry always starts at time 0 
        if entry_index == 0:
            return 0
        
        # Use random number generator with CDF from Peng et al.
        delta = self.inter_arrival.get_random()
        return minu(delta)
    
    
    def __lifetime(self):
        # Use uniform distribution to determine CDF to use
        rand = random.random()
        
        # Select CDF by rand
        sum_prob = 0
        for prob, cdf in self.random_lifetime:
            sum_prob += prob
            if rand <= sum_prob:
                delta = cdf.get_random()
                delta = minu(delta)
                return delta
    
    
    def build(self, schedule_id):
        # Available domain launch counter
        self.available_launches = [conf_domains.AVAILABLE_DOMAINS for _ in xrange(len(conf_domainsize.size_set[self.conf_domain_size]))]
        
        # Create a new schedule
        schedule = Schedule(schedule_id, self.max_parallelity, None, self.conf_domain_size)
        
        # Count number of added domains
        count_domains_added = 0
        
        # Hold offset of last added domain (inter-arrival time calculation)
        last_domain_offset = 0
                
        # Create domains until required number of domains is in schedule
        while count_domains_added < self.launches:
            # Next domain size
            domain_size = self.__domain_size()
            
            # Are there endomains of this size available
            if self.available_launches[domain_size] <= 0:
                print 'WARN: insufficient domains for size %i' % domain_size 
                continue
            
            # Determine duration and offset for this domain 
            lifetime = self.__lifetime()
            lifetime /= self.scale_duration
            
            if lifetime > self.max_duration:
                continue
            
            if self.lifetime_min and lifetime < (SCH_RAMP_DOWN + SCH_RAMP_UP + minu(2)):
                continue
            else:
                self.lifetime_min = max(lifetime, SCH_RAMP_DOWN + SCH_RAMP_UP + minu(2))
            
            offset = self.__inter_arrival(count_domains_added)
            offset /= self.scale_arrival

            # Determine profile index and profile offset 
            workload_profile_index = self.__workoad(domain_size, lifetime)
            workload_profile_offset = 0

            # Total duration
            duration = lifetime - SCH_RAMP_DOWN - SCH_RAMP_UP
            duration = max(duration, 0)

            # Try adding entry to schedule
            success = schedule.add(last_domain_offset + offset, domain_size, duration,
                                   workload_profile_index, workload_profile_offset)
            
            # If adding entry was successful
            if success:
                # Update internal counters
                count_domains_added += 1
                last_domain_offset += offset

        # Check duration
        
        time_hours = (schedule.get_end_time())
        if time_hours > self.max_duration:
            sys.stdout.write('.')
            return None
    
        # Check parallelity
        parallelity = schedule.get_parallelity()
        if parallelity > self.max_parallelity:
            sys.stdout.write('.')
            return None
    
        # Return schedule
        return schedule


class DynamicFactorialScheduleBuilder(DynamicScheduleBuilder):
    '''
    Builds a new Schedule class with entries
    '''
    
    def __init__(self,
                 max_parallelity,
                 launches,
                 domain_size,
                 inter_arrival,
                 lifetime,
                 scale_arrival,
                 scale_duration):
        
        # Do not enforce minimum lifetime
        self.lifetime_min = False
        
        # Do not limit max duration
        self.max_duration = sys.maxint
        
        # Maximum number of VMs that are allowed to run in parallel
        self.max_parallelity = max_parallelity
        
        # Scaling
        self.scale_arrival = scale_arrival
        self.scale_duration = scale_duration
        
        # Amount of domains to start
        self.launches = launches
        
        # Configure domain sizes (ensure correct parameter setting)
        self.conf_domain_size = domain_size
        
        # Configuration for domain inter arrival time
        self.inter_arrival = cdf_random.CDFRandomNumber(inter_arrival)
        
        # Configuration for domain lifetime
        self.random_lifetime_cdf = lifetime
        self.random_lifetime = []
        self.random_lifetime.append((1, cdf_random.CDFRandomNumber(lifetime)))


def load_schedule(schedule_id):
    # New schedule
    schedule = Schedule(schedule_id,
                        schedule_file='schedules/schedule_%i.json' % schedule_id)
    return schedule


def load_entries(schedule_id):
    # Schedule file
    schedule_file = 'schedules/schedule_%i.json' % schedule_id
    
    # Load file contents
    fh = open(schedule_file, 'r')
    config = fh.readline()
    fh.close()
    
    # JSON transform
    config = json.loads(config)
    
    # List with JSON entries
    schedules = []
    for schedule in config['schedules']:
        schedules.append(json.dumps(schedule)) 
    
    # Return schedule configurations
    return schedules


def plot_CDF(schedule_ids, subplot, metric_function):
    import matplotlib.pyplot as plt
    
    # Holds names of all plots for legend 
    plot_names = []
    
    # Add a CDF plot for each schedule
    for schedule_id in schedule_ids:
        # Load schedule from file
        schedule = load_schedule(schedule_id)
        
        # Extract data from schedule entries
        xvalues = metric_function(schedule.entries)
        
        # Sort values 
        xvalues.sort() 
        
        # Calculate probablity for each x value
        yvalues = []
        for x in xvalues: 
            index = bisect.bisect_right(xvalues, x)
            y = float(index) / float(len(xvalues))
            yvalues.append(y) 
        
        # add the appropriate legend for later use in the plot
        try:
            plot_names.append('schedule_id = %s' % schedule_id)
            subplot.set_xscale('log')
            subplot.plot(xvalues, yvalues)
        except:
            # Cannot plot because xvalues might be <= 0
            pass
        
    # Add legend to plot
    # plt.legend(plot_names)
    return plt
   
def export_schedules(schedule_ids, file):
    # Holds all rows with data
    rows = []
    
    # Aggregate data over all schedules
    for schedule_id in schedule_ids:
        schedule = load_schedule(schedule_id)
        for vm_index, entry in enumerate(schedule.entries): 
            rows.append((schedule_id, vm_index, entry.offset, entry.rampUp, entry.duration, entry.rampDown))
            
    # Export data into csv file
    with open(file, 'w') as csv:
        csv.write('schedule \t vm \t offset \t rampup \t duration \t rampdown \n') 
        for row in rows: 
            csv.write('%s \n' % ('\t'.join([str(s) for s in row])))
        

    
def plot_schedules(schedule_ids, cdf_only=True, out=False, suffix='png'):
    import matplotlib.pyplot as plt
    
    # Plot a gantt chart for each schedule
    if not cdf_only: 
        for schedule_id in schedule_ids:
            schedule = load_schedule(schedule_id)
            schedule.plot_gantt_chart(schedule_id, out, suffix)

    # Setup plot figure
    fig = plt.figure()
    subplot = fig.add_subplot(111)
    subplot.set_ylabel('CDF')
    subplot.set_xlabel('Instance Lifetime (min)')
    
    # Extracts lifetimes for each entry
    lifetimes = lambda x: [(int(entry.rampUp + entry.duration + entry.rampDown) / 60) for entry in x]
    
    # Plot CDF and show the plot
    plt = plot_CDF(schedule_ids, subplot, lifetimes)
    if out is None:
        plt.show()
    else:
        plt.savefig(configuration.path('CDF_lifetimes', suffix)) 

    # Plot CDFs of arrival rates
    fig = plt.figure()
    subplot = fig.add_subplot(111)
    subplot.set_ylabel('CDF')
    subplot.set_xlabel('Arrival rate (min)')
    
    # Extracts arrival times for each entry
    arrivalrates = lambda x: [int((x[i].offset - x[i - 1].offset) / 60) for i in xrange(1, len(x), 1)]
    
    # Plot CDFs and show the plot 
    plt = plot_CDF(schedule_ids, subplot, arrivalrates)
    if out == False:
        plt.show()
    else:
        plt.savefig(configuration.path('CDF_arrivals', suffix))  

def build_and_save(schedule_id, builder):
    # Build schedule
    schedule = builder.build(schedule_id)
    if not schedule:
        return None
    
    # Save schedule
    schedule.save(2, './schedules/schedule_%i.json' % schedule_id)
    return schedule


def build_schedules(offset, increment, amount, builders):
    # Schedules
    schedules = []
    
    # For each builder create 5 schedules
    for builder in builders:
        for i in xrange(amount):
            schedule = None
            while schedule is None:
                schedule = build_and_save(offset + i, builder)
            print 'Parallelity: %i' % schedule.get_parallelity()
            schedules.append(schedule)
        offset += increment
        
    # Print
    return schedules

class ScheduleConfigurationsStatic(object):
    def build_schedules(self):
        '''
        Generates a single schedule that starts all VMs and terminates all VMs
        at the same time after the experiment. This schedule resembles static scenarios. 
        '''
        
        builders = []
        builders.append(StaticScheduleBuilder(conf_domains.INITIAL_DOMAINS))
        
        # Build schedules 
        build_schedules(ID_START_STATIC, 0, 1, builders)
    
    def get_all_schedule_ids(self):
        # IDs of all schedules
        ids = [ID_START_STATIC]
        return ids
        
    def plot_schedules(self):    
        # Plot schedules
        plot_schedules(self.get_all_schedule_ids(), False, False)
        

class ScheduleConfigurationsProduction(object):
    # How many schedules to create
    NUMBER_OF_SCHEDULES_TO_BUILD = 5
    BUILDER_INCREMENT = 100
    
    def __init__(self):
        # Create schedule builders with different configurations
        self.builders = []
        duration = hour(12)
        max_parallelity = 12
        launches = 30
        scale = 40
        self.builders.append(DynamicScheduleBuilder(
                                                max_duration=duration,
                                                max_parallelity=max_parallelity,
                                                launches=launches,
                                                scale_arrival=scale,
                                                scale_duration=scale,
                                                domain_size=conf_domainsize.SET_MKII,
                                                
                                                inter_arrival=DynamicScheduleBuilder.INTER_ARRIVAL_S1,
                                                lifetime=DynamicScheduleBuilder.LIFETIME_UNPOPULAR))
        
        self.builders.append(DynamicScheduleBuilder(
                                                max_duration=duration,
                                                max_parallelity=max_parallelity,
                                                launches=launches,
                                                scale_arrival=scale,
                                                scale_duration=scale,
                                                domain_size=conf_domainsize.SET_MKII,
                                                
                                                inter_arrival=DynamicScheduleBuilder.INTER_ARRIVAL_S1,
                                                lifetime=DynamicScheduleBuilder.LIFETIME_S1))
        
        self.builders.append(DynamicScheduleBuilder(
                                                max_duration=duration,
                                                max_parallelity=max_parallelity,
                                                launches=launches,
                                                scale_arrival=scale,
                                                scale_duration=scale,
                                                domain_size=conf_domainsize.SET_MKII,
                                                
                                                inter_arrival=DynamicScheduleBuilder.INTER_ARRIVAL_S5,
                                                lifetime=DynamicScheduleBuilder.LIFETIME_UNPOPULAR))
        
        self.builders.append(DynamicScheduleBuilder(
                                                max_duration=duration,
                                                max_parallelity=max_parallelity,
                                                launches=launches,
                                                scale_arrival=scale,
                                                scale_duration=scale,
                                                
                                                domain_size=conf_domainsize.SET_MKII,
                                                inter_arrival=DynamicScheduleBuilder.INTER_ARRIVAL_S5,
                                                lifetime=DynamicScheduleBuilder.LIFETIME_S1))
    
    def build_schedules(self):
        '''
        These schedules are used for testing different placement strategies in combination
        with reallocation strategies in experiments and simulations
        
        Full Dynamic Bin Packing
        '''
            
        
        # Build schedules 
        build_schedules(ID_START_DYNAMIC_PRODUCTION,
                        ScheduleConfigurationsProduction.BUILDER_INCREMENT,
                        ScheduleConfigurationsProduction.NUMBER_OF_SCHEDULES_TO_BUILD,
                        self.builders)
        
    def get_all_schedule_ids(self):
        # IDs of all schedules
        ids = []
        
        # Data are hard coded here
        for i in xrange(len(self.builders)):
            for j in xrange(ScheduleConfigurationsProduction.NUMBER_OF_SCHEDULES_TO_BUILD):
                ids.append(ID_START_DYNAMIC_PRODUCTION + i * ScheduleConfigurationsProduction.BUILDER_INCREMENT + j)
                
        return ids
        
    def plot_schedules(self):    
        # Plot schedules
        plot_schedules(self.get_all_schedule_ids(), False, True)
        

class ScheduleConfigurationsSensitivity(object):
    # How many schedules to create
    NUMBER_OF_SCHEDULES_TO_BUILD = 5
    BUILDER_INCREMENT = 100

    def __init__(self):
        # Factors for creating a schedule (the same order as in DynamicScheduleBuilder constructor is required)
        self.factors = [
               ('launches', (30, 90)),
               ('inter_arrival', ('cdf_interval_arrivals_s4', 'cdf_interval_arrivals_s3')),
               ('lifetime', ('cdf_popular_unpopular_instance_lifetime_unpopular', 'cdf_popular_unpopular_instance_lifetime_popular')),
               ('domain_size', (conf_domainsize.SET_INTEGRAL, conf_domainsize.SET_FRACTIONAL)),
               ]
        
    def build_configurations(self):
        # Build binary matrix to generate all possible factor combinations
        t = list(itertools.product(*[range(len(self.factors[f][1])) for f in xrange(len(self.factors))]))
        t = np.transpose(np.array(t))
    
        # Create paramter lists
        configurations = []
    
        # Create schedule builders
        for col in xrange(len(t[0])):
            # Argument dictionary for this configuration
            params = {}
            
            # Build treatment params
            for row in xrange(len(t)):
                factor_name = self.factors[row][0]
                level_index = t[row][col]
                factor_value = self.factors[row][1][level_index]
                params[factor_name] = factor_value
                
            configurations.append(params)
    
        return configurations
    
    def build_schedule_builders(self, configurations):
        # List of schedule builders
        builders = []
        
        # Create a new builder for each configuration
        for configuration in configurations: 
            # Create new schedule builder based on the current configuration
            builder = DynamicFactorialScheduleBuilder(max_parallelity=sys.maxint, 
                                                      scale_arrival=1,
                                                       scale_duration=1, 
                                                      **configuration)
            builders.append(builder)
        
        return builders
    
    def write_configuration_csv(self, configurations):
        # All CSV content lines
        csv_lines = []
        
        # Create one line for each configuration
        for config in configurations:
            params = [] 
            for factor in self.factors:
                params.append(str(config[factor[0]]))
            line = '\t'.join(params)
            csv_lines.append(line)
        
        # Create CSV header
        csv_header = '\t'.join([factor[0] for factor in self.factors]) + '\n'
        csv_header = '%s \t %s' % ('schedule_id', csv_header)
        
        # Write CSV file
        f = open(configuration.path('schedule_configurations', 'csv'), 'w')
        f.write(csv_header)
        for i, line in enumerate(csv_lines):
            f.write('%i \t %s \n' % (self.__get_schedule_id(i, 0), line))
        f.close()
        
    def __get_schedule_id(self, index_configuration, schedule_number):
        return ID_START_DYNAMIC_SENSITIVITY + index_configuration * ScheduleConfigurationsSensitivity.BUILDER_INCREMENT + schedule_number
        
    def build_schedules(self):
        # Configuraions
        configurations = self.build_configurations()
        
        # Schedule builders
        builders = self.build_schedule_builders(configurations)
        
        # Build and save schedules        
        build_schedules(ID_START_DYNAMIC_SENSITIVITY,
                        ScheduleConfigurationsSensitivity.BUILDER_INCREMENT,
                        ScheduleConfigurationsSensitivity.NUMBER_OF_SCHEDULES_TO_BUILD,
                        builders)
        
        # Save configurations
        self.write_configuration_csv(configurations)
       
    def plot_schedules(self):
        plot_schedules(self.get_all_schedule_ids(), False, True)
        
    def get_all_schedule_ids(self):
        # Generate configurations
        configurations = self.build_configurations()
        
        # Ids of all schedules generated by this class
        ids = []
        
        for i, _ in enumerate(configurations):
            for j in xrange(ScheduleConfigurationsSensitivity.NUMBER_OF_SCHEDULES_TO_BUILD):
                ids.append(self.__get_schedule_id(i, j)) 
        
        return ids

def print_production_schedule_stats():
    config = ScheduleConfigurationsProduction()
    ids = config.get_all_schedule_ids()
    
    max_size_count = 0
    for schedule_id in ids:  
        schedule = load_schedule(schedule_id)
        size = {}
        for entry in schedule.entries:
            try:
                size[entry.domain_size] += 1
                max_size_count = max(max_size_count, size[entry.domain_size])
            except:
                size[entry.domain_size] = 1
        
        print '%i - %s' % (schedule_id, size)
        
    for schedule_id in ids:
        schedule = load_schedule(schedule_id) 
        print '%i - lifetime: %i (hours)' % (schedule_id, schedule.get_end_time() / 3600)
            
    print 'AVAILABLE_DOMAINS has to be set to greater than %i' % max_size_count
  

if __name__ == '__main__':
    mode = 4
    if mode == 0: # Build production and sensitivity schedules
        # Build schedules for production
        # config = ScheduleConfigurationsSensitivity()
        config = ScheduleConfigurationsProduction()
        #config = ScheduleConfigurationsStatic()
        
        config.build_schedules()
        config.plot_schedules()
        print_production_schedule_stats()
    elif mode == 1:# Build debug schedules
        # Build one schedule for debugging purpose
        while True:
            builder = DynamicScheduleBuilder(max_duration=hour(12),
                                            max_parallelity=20,
                                            launches=5,
                                            scale_arrival=20,
                                            scale_duration=20,
                                            
                                            workload_profile=0,
                                            domain_size=1,
                                            inter_arrival=1,
                                            lifetime=1)
            
            schedule = build_and_save(0, builder)
            if schedule is not None:
                print 'Domain size set to use: %i' % schedule.get_domain_size_set()
                break
            
        print load_entries(0) 
        plot_schedules([0, ], False, False)
    elif mode == 2: # Analyse production schedules for number of VMs for each size
        print_production_schedule_stats()
    elif mode == 3: # Print a schedule
        plot_schedules([20001], False, True, 'pdf')
    elif mode == 4: # Export schedule to CSV file
        export_schedules([20001], 'schedules.gcsv')
            
            
            
        


