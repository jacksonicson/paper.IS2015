from collector import ttypes
from workload import timeutil as tutil, wtimes_meta as wmeta
import configuration
import conf_nodes
import conf_load
import model
import sys
import os

##########################
# CONFIGURATION         ##
BASE_LOAD = 0  # Base load of the server (e.g. by hypervisor)
MIGRATION_SOURCE = 20  # additional load on migration source node
MIGRATION_TARGET = 20  # additional load on migration target node
MAX_TIME = tutil.hour(42)  # Random time threshold to exit simualtion in case of an error
##########################

class Driver:
    
    # The default settings are estimations of the real world infrastructure
    def __init__(self, scoreboard, pump, model, metric_handler, terminates_simulation, report_rate=None):
        # Reference to scoreboard
        self.scoreboard = scoreboard 
        
        # Reference to the message pump
        self.pump = pump

        # Reference to the data model which stores the current infrastructure status
        # Time series are attached to the model        
        self.model = model
        
        # This driver terminates simulation
        self.terminates_simulation = terminates_simulation
        
        # Callback handler to deliver time series readings
        self.metric_handler = metric_handler
        
        # If no report rate is given use 3 seconds in non-debug mode and 300 in debug mode
        if report_rate is None: 
            if configuration.DEBUG:
                report_rate = 300
            else:
                report_rate = 3
        
        # Set report rate
        self.report_rate = float(report_rate)
     
    
    def start(self):
        # Schedule message pump
        self.pump.callLater(0, self.run)
        self.count = 0
     
    def __notify(self, timestamp, name, sensor, value):
        '''
        Passes a simulated sensor reading to the metric_handler
        '''
        # Create a new notification object
        data = ttypes.NotificationData()
        data.id = ttypes.Identifier()  
        data.id.hostname = name
        data.id.sensor = sensor
        data.id.timestamp = timestamp
        
        # Put a reading in the notification
        data.reading = ttypes.MetricReading()
        data.reading.value = value
        data.reading.labels = []
        
        # Pass the notification to the metric handler
        self.metric_handler.receive([data, ])
     
     
    def __calc_index(self, dom_time, domain):
        # Index for simulation time
        tindex = int(dom_time / domain.ts_freq)
        
        # Check if index exceeds the time series length
        tindices_available = len(domain.ts)
        
        if tindex >= tindices_available:
            # If this driver terminates the simulation
            if self.terminates_simulation:
                print 'End of domain load profile reached!'
                print 'Driver load is shutting down simulation... time index = %f, number of calls = %i, time = %i' % (tindex, self.count, self.pump.sim_time())
                self.scoreboard.close() 
                self.pump.stop()
                return None
                
            else: # This driver doesn't terminate the simulation
                tindex %= tindices_available
                
        elif dom_time > MAX_TIME:
            print 'Max time reached'
            print 'Driver load is shutting down simulation... time index = %f, number of calls = %i, time = %i' % (tindex, self.count, self.pump.sim_time())
            self.scoreboard.close()
            self.pump.stop()
            return None
         
        return tindex
     
    
    def __get_load(self, tindex, domain):
        # Get current load from time series
        load = domain.ts[tindex]
        
        # Scale it accordint to real world measurements based on user count
        load = domain.domain_configuration.get_domain_spec().cpu_corr(load)
        
        return load
     
     
    def __dom_load(self, dom_time, domain):
        # Setup
        if dom_time < conf_load.SETUP:
            if dom_time < tutil.minu(1):
                return 100
            elif dom_time < tutil.minu(1.3):
                return 10
            elif dom_time < tutil.minu(2):
                return 50
            elif dom_time < tutil.minu(2.5):
                return 0
            elif dom_time < tutil.minu(3.5):
                return 75
            return 0
        
        # Correct time for setup
        # dom_time -= conf_load.SETUP
        
        # Ramp up
        if dom_time < conf_load.RAMP_UP_DOWN:
            load = self.__get_load(0, domain)
            return (float(load) / float(conf_load.RAMP_UP_DOWN)) * float(dom_time)
        
        
        # Correct time for ramp up
        dom_time -= conf_load.RAMP_UP_DOWN
        
        # Default load
        tindex = self.__calc_index(dom_time, domain)
        if tindex is None: return None
        load = self.__get_load(tindex, domain)
        return load
    
     
    def run(self):
        # Update slot count in scoreboard
        self.scoreboard.increment_slot_count()
        
        # Status logging
        self.count += 1
        if self.count % 100 == 0:
            sys.stdout.write('[pid %i]' % os.getpid())
        
        # Current simulation time
        sim_time = self.pump.sim_time()

        # For all nodes update their domains and aggregate the load for the node
        for host in self.model.get_hosts(model.types.NODE):
            # Reset aggregated node load
            aggregated_load = 0
            
            # Go over all domains and update their load by their TS
            for domain in host.domains.values():
                # Calculate domain time
                dom_time = sim_time - domain.creation_time
                
                # Get domain load
                load = self.__dom_load(dom_time, domain)
                if load is None:
                    return
                 
                # Notify load to the load metric_handler (like Sonar would do)
                self.__notify(sim_time, domain.name, 'psutilcpu', load)
                
                # Update aggregated cpu load
                self.scoreboard.add_cpu_load(load)
                
                # Load aggregation for the node
                node_load = conf_nodes.to_node_load(load, domain.domain_configuration.size)
                aggregated_load += node_load
                

            # Add hypervisor load to the aggregated load
            # For the SSAPv this causes service level violations
            aggregated_load += BASE_LOAD
            
            
            # Add Migration overheads
            if host.active_migrations_out: 
                aggregated_load += host.active_migrations_out * MIGRATION_SOURCE
            if host.active_migrations_in:
                aggregated_load += host.active_migrations_in * MIGRATION_TARGET 
            
            
            # Notify aggregated load for the server (like Sonar would do) (cap @ 100)
            self.__notify(sim_time, host.name, 'psutilcpu', min(aggregated_load, 100))
            
            # Update overload counter
            if aggregated_load > 100:
                self.scoreboard.add_cpu_violations(1)
                
            # log the current host-specific load with its time
            self.scoreboard.add_load(host.name, sim_time, aggregated_load, len(host.domains) > 0)
            
        
        # Schedule next call for run
        self.pump.callLater(self.report_rate, self.run)
            
