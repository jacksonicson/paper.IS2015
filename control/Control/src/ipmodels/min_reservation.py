'''
Implementation of the SSAPv used to calculate the allocation and 
server count based on a dynamic scenario schedule.
'''

from filelock.fl import FileLock
from schedule import schedule_builder
from workload import load
import clparams
import conf_domainsize
import conf_nodes
import conf_schedule
import configuration
import math

class Result(object):
    def __init__(self, lb_max_srv, lb_avg_srv, lb_demand_max_srv, lb_demand_avg_srv):
        self.lb_avg_srv = lb_avg_srv
        self.lb_max_srv = lb_max_srv
        self.lb_demand_avg_srv = lb_demand_avg_srv
        self.lb_demand_max_srv = lb_demand_max_srv
      
    def __str__(self):
        result = 'Lower bounds RESERVATION: max srv: %i \t avg srv: %i \t Lower bounds DEMAND: max srv: %i \t avg srv: %i' % (
                                                                                                                              self.lb_max_srv, self.lb_avg_srv, 
                                                                                                                              self.lb_demand_max_srvm, self.lb_demand_avg_srv)
        return result
        
    def write(self):
        # Build result table 
        names = 'STRATEGY_PLACEMENT \t STRATEGY_REALLOCATION \t max. servers \t avg. srv. count'
        res_reservation = 'LowerBound \t None \t %f \t %f' % (self.lb_max_srv, self.lb_avg_srv)
        res_demand = 'LowerBoundDemand \t None \t %f \t %f' % (self.lb_demand_max_srv, self.lb_demand_avg_srv)
        
        # Build header and values for this experiment
        conf_head, conf_values = clparams.build_result_log_title()
        names = '%s \t %s' % ('\t'.join(conf_head), names)
        res_reservation = '%s \t %s' % ('\t'.join(conf_values), res_reservation)
        res_demand = '%s \t %s' % ('\t'.join(conf_values), res_demand)
        
        # Append results to file
        filename = configuration.path(clparams.CL_RESULT_FILE, 'csv')
        with FileLock(filename):
            # Add header only if file is new
            try:
                # Check if file already exists
                with open(filename):
                    pass
            except IOError:
                # Create a new file and append header row
                f = open(filename, 'w')
                f.write(names)
                f.write('\n')
                f.close()
            
            # Append row information 
            with open(filename, 'a') as f:
                f.write(res_reservation)
                f.write('\n')
                f.write(res_demand)
                f.write('\n')


def __calculate_demand_based_lower_bounds(capacity_cpu, capacity_mem, events):
    # Stack is used to keep track of active VMs
    active_stack = []
     
    # Demand duration list
    demand_duration_list = []
     
    # Go through all events and calculate lower bound values
    last_event_offset = 0
    
    # Go through all events and calculate lower bound values
    for event in events:
        # Update active VM stack
        if event.is_start:
            active_stack.append(event.entry)
        else:
            active_stack.remove(event.entry)
            
        # Calculate total infrastructure demand
        sum_cpu = 0
        sum_mem = 0
        for entry in active_stack:
            # calculate current offset
            delta_time = event.offset - entry.offset 
            delta_index = delta_time / entry.freq
            
            # Include 10 minutes of load
            delta_index_past = max(delta_index - 10, 0)
            
            # Measurements
            loads = entry.ts[delta_index_past:delta_index]
            
            # Get minimum load
            if len(loads) < 2:
                load = 0; 
            else:
                load = min(*loads)
                
            size = conf_domainsize.get_domain_spec(entry.domain_size)
            sum_cpu += conf_nodes.to_node_load(load, entry.domain_size)
            sum_mem += size.total_memory()
           
        # Calculate server demands 
        lb_cpu = math.ceil(sum_cpu / float(conf_nodes.UTIL))
        lb_mem = math.ceil(sum_mem / float(capacity_mem))
        
        # Take bigger server demand
        lb = max(lb_cpu, lb_mem)
        
        # Update delta event duration calculation
        duration = event.offset - last_event_offset
        last_event_offset = event.offset
        
        # Add server demand to list
        demand_duration_list.append((lb, duration))
        
    # Calculate overall lower bound on server demand over all event slots
    lb_dem_total = max([e[0] for e in demand_duration_list])
    lb_dem_avg = sum([e[0] * e[1] for e in demand_duration_list]) / sum([e[1] for e in demand_duration_list])
    
    return lb_dem_total, lb_dem_avg


def __calculate_reservation_based_lower_bounds(capacity_cpu, capacity_mem, events):
    # Stack is used to keep track of active VMs
    active_stack = []
     
    # Demand duration list
    demand_duration_list = []
     
    # Go through all events and calculate lower bound values
    last_event_offset = 0
    for event in events:
        # Update active VM stack
        if event.is_start:
            active_stack.append(event.entry)
        else:
            active_stack.remove(event.entry)
            
        
        # Calculate total infrastructure demand
        demand_cpu_cores = 0
        demand_mem = 0
        for entry in active_stack: 
            size = conf_domainsize.get_domain_spec(entry.domain_size)
            demand_cpu_cores += size.total_cpu_cores()
            demand_mem += size.total_memory()

        # Calculate server demands          
        server_demand_cpu = math.ceil(demand_cpu_cores / capacity_cpu)
        server_demand_mem = math.ceil(demand_mem / capacity_mem)

        # Take bigger server demand (mem or cpu)
        server_demand = max(server_demand_cpu, server_demand_mem)
        
        # Update delta event duration calculation
        event_duration= event.offset - last_event_offset
        last_event_offset = event.offset
        
        # Add server demand to list 
        demand_duration_list.append((server_demand, event_duration))
        
    # Calculate overall lower bound on server demand over all event slots 
    lb_res_total = max([e[0] for e in demand_duration_list])
    lb_res_avg = sum([e[0] * e[1] for e in demand_duration_list]) / sum([e[1] for e in demand_duration_list])
    return lb_res_total, lb_res_avg


def solve(capacity_cpu, capacity_mem, schedule):
    # VM arrivals and departures are events
    class Event(object):
        def __init__(self, is_start, offset, entry):
            self.is_start = is_start
            self.offset = offset
            self.entry = entry
    
    # Transform schedule into an event stream
    events = []
    for entry in schedule.entries:
        start = entry.offset 
        end = entry.offset + entry.duration + entry.rampUp + entry.rampDown
        events.append(Event(True, start, entry))
        events.append(Event(False, end, entry))

    # Sort all events by offset
    events.sort(key=lambda event: event.offset)
    
    lb_max_server_reservation, lb_avg_server_reservation = __calculate_reservation_based_lower_bounds(capacity_cpu, capacity_mem, events)
    lb_max_server_demand, lb_avg_server_demand = __calculate_demand_based_lower_bounds(capacity_cpu, capacity_mem, events) 
    
    return Result(lb_max_server_reservation, lb_avg_server_reservation, lb_max_server_demand, lb_avg_server_demand)
    
    

def run():
    # Load domain schedule
    print 'Loading schedule...'
    schedule = schedule_builder.load_schedule(conf_schedule.SCHEDULE_ID)
    
    # Get CPU demand trace for each VM
    for entry in schedule.entries:
        index = entry.workload_profile_index
        freq, ts = load.get_cpu_trace(index, entry.domain_size)
        
        # Attach load to schedule entry
        entry.freq = freq
        entry.ts = ts

    # Solve domain schedule
    print 'solving...'        
    result = solve(conf_nodes.NODE_CPU_CORES, conf_nodes.NODE_MEM, schedule)
    
    if result:
        # Print results
        print 'Schedule length: %i' % (len(schedule.entries))
        return result
    else:
        print 'Infeasible model for SCHEDULE_ID: %i' % conf_schedule.SCHEDULE_ID
        return None


if __name__ == '__main__':
    if configuration.PRODUCTION != False:
        print 'Configuration is set to PRODUCTION MODE'
        print 'Change configuration.PRODUCTION = False for simulations'
    else:
        # Incrementally increase node count to speed up calculations
        print 'Calculating lower bounds for schedule: %i' % (conf_schedule.SCHEDULE_ID)
        result = run()
        
        # Write result to a file as it is not None any more
        try:
            result.write()
        except:
            print 'ERROR: Error while writing reslt to file' 
        
        print 'Finished schedule: %i' % conf_schedule.SCHEDULE_ID
    
    

