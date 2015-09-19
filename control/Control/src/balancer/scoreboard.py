import numpy as np
import sys
import timer

# Recorded whenever the number of active servers changes
class ActiveServerInfo(object):
    def __init__(self, timestamp, servercount):
        self.timestamp = timestamp
        self.servercount = servercount

class MigrationInfo(object):
    def __init__(self, timestamp, migration_type):
        self.timestamp = timestamp
        self.migration_type = migration_type

class NodeLoadInfo(object):
    def __init__(self, timestamp, cpu_load, active):
        self.timestamp = timestamp
        self.cpu_load = cpu_load
        self.active = active

# Scoreboard is a singleton class which overrides the new operator
class Scoreboard(object):
    def __init__(self, pump):
        self.pump = pump
        
        # Is this scoreboard closed
        self.closed = False
        
        # Teimstamp of scoreboard start
        self.start_timestamp = 0
        self.stop_timestamp = 0
        
        # Initial placement duration
        timer.initial_placement_duration.reset()
        
        # Active server infos
        self.active_server_infos = []
        
        # Min max server counters
        self.min_servers = sys.maxint
        self.max_servers = 0
        
        # Current active server count
        self.current_server_count = 0
        
        # Simulated workload slot counts
        self.slot_count = 0
        
        # CPU violation counter
        self.cpu_violations = 0
        
        # CPU accumulated load counter
        self.cpu_accumulated = 0
        
        # Migrations
        self.migrations = []
        
        # Domain migration and swap counters
        self.migration_count = 0
        
        # Overload migration counter
        self.migration_overload = 0
        
        # Record server load for each server
        self.server_load = {}
        
        # Counts dynamic domain launched (excluding initial VMs)
        self.domain_launches = 0
        
        # Names for reporting
        self.names = ['Migrations',
                      'Overload Mig.',
                      'avg. srv. count',
                      'cpu violations',
                      'cpu accumulation',
                      'min. servers',
                      'max. servers',
                      'slot count',
                      'avg. srv. utilization',
                      'initial placement duration',
                      'runtime']

    def start(self):
        self.start_timestamp = self.pump.sim_time()
    
    def close(self):
        self.closed = True
        self.stop_timestamp = self.pump.sim_time()
    
    def set_initial_placement_duration(self):
        timer.initial_placement_duration.tick()
    
    def add_overload_migration(self):
        self.migration_overload += 1
    
    def add_migration_type(self, timestamp, migration_type):
        self.migration_count += 1
        self.migrations.append(MigrationInfo(timestamp, migration_type))
    
    def add_active_info(self, servercount, timestamp):
        if not self.closed:
            self.current_server_count = servercount
            self.active_server_infos.append(ActiveServerInfo(timestamp, servercount))
            self.min_servers = min(self.min_servers, servercount)
            self.max_servers = max(self.max_servers, servercount)

    def add_cpu_violations(self, violations):
        if not self.closed:
            self.cpu_violations += violations
    
    def increment_slot_count(self):
        if not self.closed: 
            self.slot_count += self.current_server_count
    
    def add_load(self, node, time, cpu_load, was_active):
        if node not in self.server_load:
            self.server_load[node] = []
            
        self.server_load[node].append(NodeLoadInfo(time, cpu_load, was_active))
    
    def analytics_average_server_utilization(self):
        # Map of average loads
        loads = {}
        
        total_time = 0
        total_load = 0
        
        # Calculate average load for each host
        for node in self.server_load.keys():
            
            last_active = self.server_load[node][0]
            weighted_load = 0
            weighted_time = 0
            max_load = 0
            
            for info in self.server_load[node]:
                if last_active.active: 
                    delta_time = info.timestamp - last_active.timestamp
                    weighted_time += delta_time
                    weighted_load += delta_time * last_active.cpu_load
                    max_load = max(max_load, last_active.cpu_load)
                last_active = info
                    
            if weighted_time > 0: 
                loads[node] = [weighted_load / weighted_time, max_load]
                                
                total_time += weighted_time
                total_load += weighted_load
            
        return (total_load / total_time), loads
        
        
    def add_domain_launch(self):
        self.domain_launches += 1
        
    def add_cpu_load(self, load):
        if not self.closed:
            self.cpu_accumulated += load

    def analytics_average_server_count(self):
        if not self.active_server_infos:
            return 0
        
        if len(self.active_server_infos) == 1:
            return self.active_server_infos[0].servercount
        
        # Time delta between first and last entry
        time = self.active_server_infos[-1].timestamp - self.active_server_infos[0].timestamp
    
        # Area under the plot 
        weighted_sum = 0
        
        # For all active server infos except the last one (N-1)
        for i in xrange(0, len(self.active_server_infos) - 1):
            # Active server count for this field
            t = (self.active_server_infos[i + 1].timestamp - self.active_server_infos[i].timestamp)
            s = self.active_server_infos[i].servercount 
            weighted_sum += s * t
    
        # Calculate mean
        avg = float(weighted_sum) / float(time)
        return avg
       
    def get_results(self):
        return (len(self.migrations), self.migration_overload, self.analytics_average_server_count(),
                self.cpu_violations, self.cpu_accumulated, self.min_servers, self.max_servers,
                self.slot_count, self.analytics_average_server_utilization()[0], timer.initial_placement_duration.last_duration(),
                (self.stop_timestamp - self.start_timestamp))
    
    def get_result_line(self):
        res = self.get_results()
        names = '\t'.join(self.names)
        res = '%f \t %f \t %f \t %f \t %i \t %i \t %i \t %i \t %f \t %i \t %i' % res
        return names, res
    
    def dump(self):
        # Print overall stats
        print 'Records %i' % len(self.active_server_infos)
        print 'Average server count %f' % self.analytics_average_server_count()
        print 'Dynamic domain launches %i' % self.domain_launches
        
        print
        print
        
        # Print aggregated results
        from texttable.texttable import Texttable as Tb
        table = Tb()
        table.set_deco(Tb.VLINES | Tb.HEADER)
        table.set_cols_width([7 for _ in xrange(len(self.names))])
        table.set_cols_align(['l' for _ in xrange(len(self.names))])
        table.set_chars(['-','|','+','='])
        table.add_rows([
                        self.names,
                        self.get_results()
                        ])
        print table.draw()
        
        print 
        print
        
        # Print average node loadd
        _, loads = self.analytics_average_server_utilization()
        
        table = Tb()
        table.set_deco(Tb.VLINES | Tb.HEADER)
        table.set_chars(['-','|','+','='])
        table.header(['Node', 'Avg. Load', 'Max. Load'])
        for node in loads.keys():
            row = [node,]
            row.extend(loads[node])
            table.add_row(row)
        print table.draw()
        
        
        
        
        
