from collections import namedtuple
from collector import ManagementService, ttypes
from thrift.protocol import TBinaryProtocol
from thrift.transport import TSocket, TTransport
from workload import util
import conf_nodes
import configuration
import json
import numpy as np
import sys
import time
import traceback

##########################
# # Configuration       ##
##########################
COLLECTOR_IP = 'monitor0.dfg'
MANAGEMENT_PORT = 7931
LOGGING_PORT = 7921
DEBUG = False
TRACE_EXTRACT = False
DRIVERS = 2
EXPERIMENT_DB = configuration.path('experiments', 'csv')

CONTROLLER_NODE = 'Andreas-PC'  
DRIVER_NODES = ['load0', 'load1']

# Times
RAW = '6/6/2014 23:58:00    6/7/2014 11:40:00'

# Timestamps of bugfixes
FIX_B1 = int(time.mktime(time.strptime('10/6/2013', '%m/%d/%Y')))    
##########################

# List of warnings that might render the run invalid
warns = []

# Extract timestamps from RAW
START, END = RAW.split('    ')

'''
Log warning
'''
def __warn(msg):
    warns.append(msg)
    
'''
Dump warnings
'''
def __dump_warns():
    if len(warns) > 0:
        print '## WARNINGS ##'
        print 'Analysis might be invalid due to following warnings:'
        for warn in warns:
            print ' * %s' % warn

'''
Dump the analytics script configuration
'''
def __dump_configuration():
    print '## CONFIGURATION ##'
    print "COLLECTOR_IP = '%s'" % (COLLECTOR_IP)
    print 'MANAGEMENT_PORT = %i' % (MANAGEMENT_PORT)
    print 'LOGGING_PORT = %i' % (LOGGING_PORT)
    print 'DEBUG = %s' % (DEBUG)
    print 'TRACE_EXTRACT = %s' % (TRACE_EXTRACT)
    print ''
    print "CONTROLLER_NODE = '%s'" % (CONTROLLER_NODE)
    print "DRIVER_NODES = %s" % DRIVER_NODES
    print ''
    print "START = '%s'" % START
    print "END = '%s'" % END
    print '## END CONFIGURATION ##'


'''
Convert a datetime from a string to a UNIX timestamp
'''
def __to_timestamp(date):
    res = time.strptime(date, '%m/%d/%Y %H:%M:%S')    
    return int(time.mktime(res))

'''
Dump all elements from a tuple as a CSV row
'''
def __dump_elements(elements, title=None, separator=', '):
    if title is not None:
        __dump_elements(title)
    
    result = ['%s' for _ in xrange(len(elements))]
    result = separator.join(result)
    print result % elements


'''
Disconnect from Sonar
'''
def __disconnect():
    transportManagement.close()


'''
Connect with Sonar 
'''
def __connect():
    # Create a socket and transport layer
    global transportManagement
    transportManagement = TSocket.TSocket(COLLECTOR_IP, MANAGEMENT_PORT)
    transportManagement = TTransport.TBufferedTransport(transportManagement)
    global managementClient
    managementClient = ManagementService.Client(TBinaryProtocol.TBinaryProtocol(transportManagement));
    
    # Open connection
    while True:
        try:
            transportManagement.open();
            break
        except Exception:
            print 'Retrying connection after 1 second...'
            time.sleep(1)
            
    return managementClient 

'''
Fetch a timeseries from Sonar
'''
def __fetch_timeseries(connection, host, sensor, timeframe, valid_empty=False):
    # Formulate query
    query = ttypes.TimeSeriesQuery()
    query.hostname = host
    query.startTime = timeframe[0]
    query.stopTime = timeframe[1]
    query.sensor = sensor
    
    # Run query
    result = connection.query(query)
    
    # Convert time series to arrays
    time, result = util.to_array_collector(result, timeframe)

    # For some very short lived VMs with almost zero demand during this short runtime the sampler
    # did skip all entries and nothing is reported. 
#    if not valid_empty: 
#        # Mean of all values gerater zero
#        assert len(result) > 0
#        
#        # Mean of all values gerater zero
#        assert np.mean(result) > 0
#        
#        # Time between the first and last entry greater 30 secs
#        assert (time[-1] - time[0]) > 10
        
    # Return time series and timestamps
    return result, time

'''
Get a time series slice with a given start and end time
'''
def __slice_timeseries(results, time, start, end):
    i_start, i_end = None, None
    for i, t in enumerate(time):
        if i_start is None and t >= start:
            i_start = i
            
        if i_start is not None and i_end is None and t > end:
            i_end = i
            break
        
    # Validation
    assert time[i_start] <= time[i_end]
    if i_start > 0: 
        assert time[i_start - 1] < start
        assert time[i_start] >= start 
    if i_end < len(time):
        assert time[i_end - 1] < end
        assert time[i_end] >= end
    
    return results[i_start:i_end], time[i_start:i_end]

'''
Reads the sync markers from the start_benchmark skript: 
- start driving load  (releasing load)
- end of startup sequence (after ramp-up)
'''
def __fetch_start_benchamrk_syncs(sonar, host, timeframe):
    # Query
    query = ttypes.LogsQuery()
    query.hostname = host
    query.sensor = 'behaviors'
    query.startTime = timeframe[0]
    query.stopTime = timeframe[1]
    
    # Fetch log messages
    logs = sonar.queryLogs(query)
    
    # Data to extract
    start_startup = None
    release_load = None
    end_startup = None
    
    # Iterate over all log messages
    for log in logs:
        if log.logLevel == 50010:
            # Rain driver launched 
            if log.logMessage == 'RAIN drivers launched':
                release_load = log.timestamp
                
            # Startup sequence finished
            elif log.logMessage == 'end of startup sequence':
                end_startup = log.timestamp
                
            # Start of startup sequence
            elif log.logMessage == 'start of startup sequence':
                start_startup = log.timestamp

    # All timestamps are required
    assert start_startup is not None
    assert release_load is not None
    assert end_startup is not None
    
    # Order in time of all timestamps has to be correct
    assert start_startup < end_startup
    assert start_startup <= release_load
    assert end_startup <= release_load
                
    # Return timestamps 
    return start_startup, release_load, end_startup

'''
The given start and stop time are only hints and the experiment was
somewhere between start and stop time. This function extracts the 
actual start and stop time of an experiment.  
'''
def __refine_markers():
    # Configure experiment
    start = __to_timestamp(START)
    stop = __to_timestamp(END)
    raw_frame = (start, stop)
    
    # Get sync markers from control (start of driving load)
    sync_markers = __fetch_start_benchamrk_syncs(connection, CONTROLLER_NODE, raw_frame)
    
    # Start time has to be before stop time
    assert start < stop
    
    # All three sync markers need to be available
    assert sync_markers[0] is not None
    assert sync_markers[1] is not None
    assert sync_markers[2] is not None
    
    # Return RAW frame and SYNC markers
    return raw_frame, sync_markers
  
  
'''
Loads the lifetime timestamps of all target domains. 
'''
def __load_target_times(data_frame):
    # Hods the information for one target domain
    class TargetTimes(object):
        def __init__(self):
            self.targetId = None
            self.init = None
            self.ramp_up = None
            self.ended = None
    
    # Mapping holds one mapping table for each driver node
    mappings = {}
    
    # For all driver nodes fetch target times
    for driver_node in DRIVER_NODES:
        # New mapping for this driver node
        mapping = {}
        
        # Add driver node mapping to mappings
        mappings[driver_node] = mapping        
        
        # Build query
        query = ttypes.LogsQuery()
        query.hostname = driver_node
        query.sensor = 'rain'
        query.startTime = data_frame[0]
        query.stopTime = data_frame[1]
        
        # Fetch log messages
        logs = connection.queryLogs(query)
        
        # For all log messages
        for log in logs:
            # Target initialized, create a new target definition and fill in init time
            STR_TARGET_INIT = 'Target init: '
            if log.logMessage.startswith(STR_TARGET_INIT):
                jsontext = log.logMessage[len(STR_TARGET_INIT):]
                info = json.loads(jsontext)
                tt = TargetTimes()
                tt.targetId = info['targetId']
                tt.init = log.timestamp
                mapping[tt.targetId] = tt
                
            # Ramp up finished, fill in ramp up finished time 
            STR_TARGET_RAMP_UP = 'Ramp up finished: '
            if log.logMessage.startswith(STR_TARGET_RAMP_UP):
                jsontext = log.logMessage[len(STR_TARGET_RAMP_UP):]
                info = json.loads(jsontext)
                tt = mapping[info['targetId']]
                tt.ramp_up = log.timestamp
                
            # Target ended, fill in ended time
            STR_TARGET_ENDED = 'Target ended: '
            if log.logMessage.startswith(STR_TARGET_ENDED):
                jsontext = log.logMessage[len(STR_TARGET_ENDED):]
                info = json.loads(jsontext)
                tt = mapping[info['targetId']]
                tt.ended = log.timestamp
                
    # For all mappings of the driver nodes
    for mapping in mappings.values():
        
        # For all target definitions in this mapping 
        for target in mapping.values():
            # Check if targetId is available
            assert target.targetId is not None
            
            # Check if init, ramp up and ended times are available
            assert target.ended is not None
            assert target.init is not None
            assert target.ramp_up is not None
                
    return mappings
        
'''
Load a mapping of domain names to targetIds of a load driver
'''
def __load_domain_target_mapping(data_frame):
    # Mapping of a domain name to targetId
    class Assignment(object):
        def __init__(self, targetId, node, start, end):
            self.targetId = targetId
            self.node = node
            self.start = start
            self.end = end
        
        def __repr__(self):
            return self.__str__()
            
        def __str__(self):
            return '(targetId=%i, node=%s, start=%i, end=%i)' % (self.targetId, self.node, self.start, self.end)
    
    # Mapping holds one mapping table for each driver node
    mappings = {}
    
    # For all driver nodes
    for driver_node in DRIVER_NODES:
        # Create new mapping
        mapping = {}
        
        # Add mapping to mappings
        mappings[driver_node] = mapping

        # Online target stack to keep track of online and offline targets
        online_targets = []
         
        # Build query
        query = ttypes.LogsQuery()
        query.hostname = driver_node
        query.sensor = 'rain'
        query.startTime = data_frame[0]
        query.stopTime = data_frame[1]
        
        # Fetch log messages
        logs = connection.queryLogs(query)
         
        # Go over all logs
        for log in logs:
            # Target launched
            STR_LAUNCHED = 'Target launched: '
            if log.logMessage.startswith(STR_LAUNCHED):
                jsontext = log.logMessage[len(STR_LAUNCHED):]
                
                # Load JSON data
                info = json.loads(jsontext)
                
                # Extract values
                domain = info['targetDomain']
                targetId = info['targetId']
                
                # Add domain with its assignments list to the mapping
                if not mapping.has_key(domain):
                    mapping[domain] = []
                    
                # Add target to the stack
                online_targets.append(domain)
                
                # Add assignment to the mapping list
                assignment = Assignment(targetId, domain, log.timestamp, None)
                mapping[domain].append(assignment)
                
            # Target terminated            
            STR_TERMINATED = 'Target terminated: '
            if log.logMessage.startswith(STR_TERMINATED):
                jsontext = log.logMessage[len(STR_TERMINATED):]
                info = json.loads(jsontext)
                domain = info['targetDomain']
                targetId = info['targetId']
                
                # Remove domain from the stack
                del online_targets[online_targets.index(domain)]
                
                # Find assignment in the mapping list
                for assignment in mapping[domain]:
                    # Check targetId
                    if assignment.targetId == targetId:
                        # Update its end time
                        assignment.end = log.timestamp
        
        # Bugfix - correcting targetId for some experiments
        if data_frame[0] <= FIX_B1: 
            __warn('Applying bugfix FIX_B1')
            # Apply bugfix: domain target mapping was not logged propertly. This fix
            # assumes that each load domain launched 18 targets
            replacement_id = 0
            for domain in mapping.keys():
                assignments = mapping[domain]
                for assignment in assignments:
                    assignment.targetId = replacement_id
                    replacement_id += 1
                        
        # Stack of online targets has to be empty
        assert not online_targets
        
        # For all domains in the mapping
        for domain in mapping.keys():
            # For all assignments of targetIds to the domain
            assignments = mapping[domain]
            for assignment in assignments:
                # Check if start, end time and targetId are there
                assert assignment.start is not None
                assert assignment.end is not None
                assert assignment.start < assignment.end
                assert assignment.targetId is not None
                
    return mappings

     
'''
Get a mapping of domain activations by domain name
'''
def __load_domain_activations(data_frame):
    # Build query
    query = ttypes.LogsQuery()
    query.hostname = CONTROLLER_NODE
    query.sensor = 'controller'
    query.startTime = data_frame[0]
    query.stopTime = data_frame[1]
    
    # Fetch log messages
    logs = connection.queryLogs(query)
    
    # Map of all activations
    activations = {}
    
    # For all log messages
    for log in logs: 
        STR_HANDOUT = 'Handout domain: '
        if log.logMessage.startswith(STR_HANDOUT):
            name = log.logMessage[len(STR_HANDOUT):]
            
            # If this domain hasn't been activated before
            if not activations.has_key(name):
                activations[name] = []
                
            # Create a new activation entry with a start timestamp
            activations[name].append([log.timestamp, None])
                
        STR_HANDIN = 'Handin domain: '
        if log.logMessage.startswith(STR_HANDIN):
            name = log.logMessage[len(STR_HANDIN):]
            
            # Update end timestamp of the last activation
            activations[name][-1][1] = log.timestamp
    
    # For all domains
#    for domain in activations.keys():
#        # For all activations of this domain
#        for activation in activations[domain]:
#            print domain
#            # Check timestamps
#            assert activation[0] is not None
#            assert activation[1] is not None
#            assert activation[0] <= activation[1]
            
    return activations
    
'''
Load all domain names used in the experiment
'''
def __load_domain_names(init_frame, data_frame):
    # List of all found domain names
    domain_names = []
    
    # Build query for initial domains
    query = ttypes.LogsQuery()
    query.hostname = CONTROLLER_NODE
    query.sensor = 'behaviors'
    query.startTime = init_frame[0]
    query.stopTime = init_frame[1]
    
    # Get all log messages
    logs = connection.queryLogs(query)
    
    # For all log messages
    for log in logs:
        # If initial domain log
        STR_INITIAL_DOMAINS = 'Initial Domains: '
        if log.logMessage.startswith(STR_INITIAL_DOMAINS):
            jsontext = log.logMessage[len(STR_INITIAL_DOMAINS):]
            info = json.loads(jsontext)
            
            # Add all initial domain names to the list
            domain_names.extend(info['domains'])
    
    # Build query for dynamic domains
    query = ttypes.LogsQuery()
    query.hostname = CONTROLLER_NODE
    query.sensor = 'controller'
    query.startTime = data_frame[0]
    query.stopTime = data_frame[1]
    
    # Get all log messages
    logs = connection.queryLogs(query)
    
    # For all log messages
    for log in logs:
        # Handin domain
        STR_HANDIN = 'Handin domain: '
        if log.logMessage.startswith(STR_HANDIN):
            name = log.logMessage[len(STR_HANDIN):]
            domain_names.append(name)
            
        # Handout domain
        STR_HANDOUT = 'Handout domain: '
        if log.logMessage.startswith(STR_HANDOUT):
            name = log.logMessage[len(STR_HANDOUT):]
            domain_names.append(name)
         
    # Remove duplicates
    domain_names = list(set(domain_names))
         
    # A least one domain name is required
    assert domain_names
    
    # For all domain names check that they are not None
    for name in domain_names: 
        assert name is not None
                
    return domain_names

'''
Load server activations and deactivations
'''
def __load_server_active_infos(data_frame):
    # Build query
    query = ttypes.LogsQuery()
    query.hostname = CONTROLLER_NODE
    query.sensor = 'controller'
    query.startTime = data_frame[0]
    query.stopTime = data_frame[1]
    
    # Get all log messages
    logs = connection.queryLogs(query)
    
    # List of server activation status informations
    active_infos = []
    
    # Each activation is a tuple
    Active = namedtuple('active', 'timestamp count servers')
    
    # For all log messages
    for log in logs:
        # Server activation
        STR_ACTIVE_SERVERS = 'Active Servers: '
        if log.logMessage.startswith(STR_ACTIVE_SERVERS):
            msg = log.logMessage[len(STR_ACTIVE_SERVERS):]
            msg = json.loads(msg)
            
            # Create new activation entry
            timestamp = msg['timestamp']
            count = msg['count']
            servers = msg['servers']
            active = Active(timestamp, count, servers)
            active_infos.append(active)
            
    # Validation
    assert active_infos
    for info in active_infos:
        assert info.timestamp is not None 
        assert info.timestamp > 0
        assert info.count >= 0
        assert len(info.servers) == info.count
            
    return active_infos
    
    
'''
Load cpu and mem load traces for all domains given
'''
def __load_traces(data_frame, domains):
    # Results
    cpu = {}
    mem = {}

    # Fetch CPU and MEM load for all nodes    
    for srv in conf_nodes.NODES:
        res_cpu, tim_cpu = __fetch_timeseries(connection, srv, 'psutilcpu', data_frame)
        res_mem, tim_mem = __fetch_timeseries(connection, srv, 'psutilmem.phymem', data_frame)
        cpu[srv] = (res_cpu, tim_cpu)
        mem[srv] = (res_mem, tim_mem)
    
    # Fetch CPU and MEM load for all domains
    for domain in domains:
        res_cpu, tim_cpu = __fetch_timeseries(connection, domain, 'psutilcpu', data_frame)
        res_mem, tim_mem = __fetch_timeseries(connection, domain, 'psutilmem.phymem', data_frame)
        cpu[domain] = (res_cpu, tim_cpu)
        mem[domain] = (res_mem, tim_mem)
        
    # Validation
#    for key in cpu.keys():
#        assert len(cpu[key][0]) > 0
#        assert len(cpu[key][0]) == len(cpu[key][1])
#        
#        assert len(mem[key][0]) > 0
#        assert len(mem[key][0]) == len(mem[key][1])
        
    return cpu, mem


'''
Extracts all JSON configuration and metric information from the Rain log. This
method only works this the most recent version of Rain dumps!
'''
RainResults = namedtuple('RainReslts', 'schedule, global_scorecard, target_scoreboards, agg_scoreboards, errors, error_data')
def __load_rain_results(load_host, timeframe):
    # Configuration
    schedule = None
    
    # Metrics
    global_scorecard = None
    target_scorecards = {}
    agg_operational_scoreboards = {}
    joined_msg = False
    
    errors = []
    error_data = []
     
    # Build query
    query = ttypes.LogsQuery()
    query.hostname = load_host
    query.sensor = 'rain'
    query.startTime = timeframe[0]
    query.stopTime = timeframe[1]
    logs = connection.queryLogs(query)
    
    # scan logs for results
    for log in logs:
        if log.timestamp > (timeframe[1] + 5 * 60) * 1000:
            print 'skipping remaining log messages - out of timeframe'
            break

        # Global benchmark schedule (start and end markers) 
        STR_BENCHMARK_SCHEDULE = 'Schedule: '
        if log.logMessage.startswith(STR_BENCHMARK_SCHEDULE):
            msg = log.logMessage[len(STR_BENCHMARK_SCHEDULE):]
            schedule = json.loads(msg)
            schedule = (schedule['startSteadyState'], schedule['endSteadyState'])
        
        # Read global scorecard (aggregation of all summary scorecards) 
        STR_MERGED_SCORECARD = 'Global scorecard: '
        if log.logMessage.startswith(STR_MERGED_SCORECARD):
            msg = log.logMessage[len(STR_MERGED_SCORECARD):]
            global_scorecard = json.loads(msg)
        
        # Read operational scorecards (aggregation of all operational scorecards by operation class name) 
        STR_AGGREGATED_SCORECARD = 'Aggregated scorecard for -'
        if log.logMessage.startswith(STR_AGGREGATED_SCORECARD):
            msg = log.logMessage[len(STR_AGGREGATED_SCORECARD):]
            driver = msg[:msg.find(':')]
            msg = msg[msg.find(':') + 2:]
            result = json.loads(msg)
            agg_operational_scoreboards[driver] = result
            
        # Read summary scorecard of each target (contains scorecard for each operation by class name) 
        STR_TARGET_SCOREBOARD = 'Target scoreboard statistics - '
        if log.logMessage.startswith(STR_TARGET_SCOREBOARD):
            msg = log.logMessage[len(STR_TARGET_SCOREBOARD):]
            targetId = int(msg[:msg.find(':')])
            msg = msg[msg.find(':') + 2:]
            result = json.loads(msg)
            target_scorecards[targetId] = result
        
        # Read MFG metrics
        JOINED = 'JOINED'
        if log.logMessage.startswith(JOINED):
            msg = log.logMessage[len(JOINED):]
            joined_msg = True
           
        # Extract errors
        if log.logLevel == 40000:
            errors.append(log.logMessage)
            error_data.append(log)   
        
    # Add warning if rain did not join in a right way
    if joined_msg == False:
        __warn('Missing "Rain Stopped" message')
        
    # Validation
    assert joined_msg
    assert schedule is not None
    assert schedule[0] < schedule[1]
    assert global_scorecard is not None
    for key in agg_operational_scoreboards.keys():
        assert agg_operational_scoreboards[key] is not None
    for key in target_scorecards.keys():
        assert target_scorecards[key] is not None
        
    # Return all data
    return RainResults(schedule, global_scorecard, target_scorecards, agg_operational_scoreboards, errors, error_data)


'''
Loads the response time for all domains sampled by a poisson process
'''
def __load_domain_rtime_poisson_TS(data_frame, domain_target_mapping):
    # Holds a list of TS for the response time
    all_ts = []
    
    # For each load node like load0 and load 1
    for load_node in domain_target_mapping.keys():
        # For each domain created by this load node 
        for domain in domain_target_mapping[load_node].keys():
            # A domain can have multiple targets assigned to it (domains are re-used) 
            for assignment in domain_target_mapping[load_node][domain]:
                # Create query   
                data_segment = (assignment.start, assignment.end)
                sensor = 'rain.rtime.sampler.%i.all' % assignment.targetId
                
                # Fetch TS
                print 'Fetching %s for %i minutes on %s...' % (sensor, (assignment.end - assignment.start) / 60, load_node)
                ts = __fetch_timeseries(connection, load_node, sensor, data_segment, True)
                
                # Append TS to the list of TS
                all_ts.append(ts)
    
    # Validation
    for ts in all_ts: 
        assert ts
    
    return all_ts

'''
Loads the response time for all domains as 99th percentile over 3 second intervals
'''
def __load_domain_rtime_99th_TS(data_frame, domain_target_mapping):
    # Holds a list of TS for the response time 
    all_ts = []
    
    # For each load node like load0 and load 1
    for load_node in domain_target_mapping.keys():
        # For each domain created by this load node 
        for domain in domain_target_mapping[load_node].keys():
            # A domain can have multiple targets assigned to it (domains are re-used) 
            for assignment in domain_target_mapping[load_node][domain]:
                # Prepare query   
                data_segment = (assignment.start, assignment.end)
                sensor = 'rain.rtime.99th.%i' % assignment.targetId

                # Fetch TS
                print 'Fetching %s for %i minutes on load driver %s ...' % (sensor, (assignment.end - assignment.start) / 60, load_node)
                ts = __fetch_timeseries(connection, load_node, sensor, data_segment)
                
                # Append TS to the list of TS
                all_ts.append(ts)
           
    # Validation
    for ts in all_ts:
        assert ts
                
    return all_ts
                
'''
Fetch number of response time violations
'''
def __analyze_rtime_thr_violations(threshold, rain_generated_TS):
    # Counters
    value_count, violated_values = 0, 0
    
    # For all TS
    for series in rain_generated_TS:
        # Unpack 
        values, time = series
        
        # Total values in time series
        value_count += len(time)
        
        # Extract values that are above the threshold
        # First parameter creates a 0,1 mask filter
        # Second parameter are the array that gets masked
        ext = np.extract(np.array(values) > threshold, values)
        
        # Count length of the masked array 
        violated_values += len(ext)


    # Validation
    assert value_count >= violated_values
    
    return value_count, violated_values
                
'''
Get min and max server demand
'''
def __analyze_min_max_server_count(active_servers):
    # Total time from first to last active server info
    total_time = active_servers[-1].timestamp - active_servers[0].timestamp
    
    # Server time segments
    segments = []
    for i in xrange(0, len(active_servers) - 1):
        a = active_servers[i]
        b = active_servers[i + 1]
        segments.append((a.count, b.timestamp - a.timestamp))
            
    # Sort segments by server count
    segments = sorted(segments, key=lambda segment: segment[0])
        
    print segments
        
    # Calculates a percentile based on the total time and segments
    def percentile(percentile):
        # Percentile time 
        # Assume that there is one segment for each second
        time = percentile * total_time
        print time
        # Go over all segments until time is reached
        offset = 0
        for i, segment in enumerate(segments):
            offset += segment[1]
            if time <= offset:
                return segments[i][0]
            
        # Nothing found so return last segment
        return segments[-1][0]

    # Calculate percentiles            
    p50th = percentile(.50)
    p90th = percentile(.90)
    
    # Determine min max
    min_srv = segments[0][0]
    max_srv = segments[-1][0]
    
    # Validation
    assert total_time > 0
    assert min_srv <= max_srv
    assert p50th <= p90th
    
    return min_srv, max_srv, p50th, p90th
    

'''
Average server count is calculated by a weighted mean. For $N$ active server ^
infos average server count is calculated by:
\bar{s} = \frac{\sum_{i=0}^{N-1}{s_i(t_{i+1}-t_i)}}{t_N-t_0} 
'''
def __analyze_avg_server_count(active_servers):
    # Total time from first to last timestamp
    time = active_servers[-1].timestamp - active_servers[0].timestamp
    
    # Area under the plot 
    weighted_sum = 0
    
    # For all active server infos except the last one (N-1)
    for i in xrange(0, len(active_servers) - 1):
        # Active server count for this field
        t = (active_servers[i + 1].timestamp - active_servers[i].timestamp)
        s = active_servers[i].count 
        weighted_sum += s * t

    # Calculate mean
    avg = float(weighted_sum) / float(time)
    
    # Validation
    assert time > 0
    assert avg > 0
    assert weighted_sum > 0
    
    return avg
  
'''
Extract how often a server was started and shut down
'''
def __analyze_server_activations(active_servers):
    activations, deactivations = 0, 0
    
    # If list is empty
    if not active_servers:
        return activations, deactivations
    
    # For all active server infos except the last one (N-1)
    prev = active_servers[0].count
    
    # Count initial activations
    activations += prev
    
    # For all remaining active server infos
    for current in active_servers[1:]:
        # Activations
        if current.count > prev:
            activations += abs(current.count - prev)
            
        # Deactivations
        elif current.count < prev:
            deactivations += abs(current.count - prev)
            
        # Update previous value
        prev = current.count
        
    # Validation
    assert activations >= 0
    assert deactivations >= 0
    assert deactivations <= activations
        
    return activations, deactivations
    
    
'''
Get the average server CPU load
'''
def __analyze_avg_server_load(active_servers, res_ts, thr):
    
    def __append_to_active(sequence, timestamp, status):
        if not sequence:
            sequence.append((timestamp, status))
        else:
            if sequence[-1][1] != status:
                sequence.append((timestamp, status))
    
    # Add a active server sequence list for each node
    active_sequence = {}
    for node in conf_nodes.NODES:
        active_sequence[node] = []
    
    # The sequence contains a list of tuples (timestamp, server state) for each server
    # Tuples are only added to the list if the server state changes
    # For each server there is a time series with values {0,1} indicating the server state
        
    # Go over all active server infos
    for active_server in active_servers:
        # Update active status for each server
        # Entries are only added if the status of one server changes
        for node in conf_nodes.NODES:
            __append_to_active(active_sequence[node], active_server.timestamp, node in active_server.servers)
            
    # Extract CPU load
    filtered_values = []
    for node in conf_nodes.NODES:
        # CPU TS
        res, time = res_ts[node]
        
        # Active element index
        iactive = 0
        
        # Go over all elements in the TS
        for i, t in enumerate(time):
            # Current active server info tuple
            current = active_sequence[node][iactive]
            
            # Check if next active server tuple is reached
            if len(active_sequence[node]) > (iactive + 1):
                next_active = active_sequence[node][iactive + 1]
                if t >= next_active[0]: 
                    iactive += 1
                    current = next_active
                    
            # If node is currently active record its CPU utilization
            if current[1]:
                filtered_values.append(res[i])
    
    # Calculate statistics
    mean = np.mean(filtered_values)
    p50 = np.percentile(filtered_values, 50)
    p90 = np.percentile(filtered_values, 90)
    p99 = np.percentile(filtered_values, 99)
    thr = len(np.extract(filtered_values > thr, filtered_values))
    
    return mean, p50, p90, p99, thr
    
'''
Get a list of live migrations
'''
def __fetch_migrations(timeframe):
    # Build query
    query = ttypes.LogsQuery()
    query.hostname = CONTROLLER_NODE
    query.sensor = 'controller'
    query.startTime = timeframe[0] - 60
    query.stopTime = timeframe[1]
    logs = connection.queryLogs(query)
    
    # Sync marker load balancer release
    sync_release = None
    
    # List of migrations
    successful = []
    failed = []
    server_active = [] 
    triggered = []
    
    # Initial model
    initial = None
    
    # scan logs for results
    for log in logs:
        if log.timestamp > timeframe[1]:
            print 'skipping remaining migrations - out of timeframe'
            # break
        
        if sync_release:        
            if log.logLevel == 50010:
                if log.logMessage == 'Releasing load balancer':
                    sync_release = log.timestamp
        else:
            # Initial model
            STR_INITIAL_MODEL = 'Controller Initial Model: '
            if log.logMessage.startswith(STR_INITIAL_MODEL):
                msg = log.logMessage[len(STR_INITIAL_MODEL):]
                initial = json.loads(msg)
            
            # Migration triggered
            STR_MIGRATION_TRIGGERED = 'Live Migration Triggered: '
            if log.logMessage.startswith(STR_MIGRATION_TRIGGERED):
                log.logMessage[len(STR_MIGRATION_TRIGGERED):]
                msg = log.logMessage[len(STR_MIGRATION_TRIGGERED):]
                migration = json.loads(msg)
                triggered.append((log.timestamp, migration)) 
            
            # Migration finished
            STR_MIGRATION_FINISHED = 'Live Migration Finished: '
            if log.logMessage.startswith(STR_MIGRATION_FINISHED):
                msg = log.logMessage[len(STR_MIGRATION_FINISHED):]
                migration = json.loads(msg)
                successful.append((log.timestamp, migration))
            
            # Migration failed
            STR_MIGRATION_FAILED = 'Live Migration Failed: '
            if log.logMessage.startswith(STR_MIGRATION_FAILED):
                msg = log.logMessage[len(STR_MIGRATION_FAILED):]
                migration = json.loads(msg)
                failed.append(migration)
                
            # Server empty
            STR_ACTIVE_SERVERS = 'Active Servers: '
            if log.logMessage.startswith(STR_ACTIVE_SERVERS):
                msg = log.logMessage[len(STR_ACTIVE_SERVERS):]
                active = json.loads(msg)
                active_state = (log.timestamp, active['count'], active['servers'])
                server_active.append(active_state)
                
    # Validation
    assert successful >= failed
    
    print len(triggered)
    print len(successful)
    print len(failed)
    
    print 'triggered'
    print triggered
    print 'successful'
    print successful
    print 'failed'
    print failed
    
    assert len(triggered) == (len(successful) + len(failed))
    assert initial is not None
    assert server_active is not None
                
    return successful, failed, server_active, triggered, initial


'''
Class holds all information of the global experimental summary
'''
class GlobalSummary(object):
        def __init__(self):
            self._ops_total = 0
            self._ops_successful = 0
            self._ops_failed = 0
            
            self._min_rtime = []
            self._max_rtime = []
            
            self._mean_rtime = []
            self._p50th_rtime = []
            self._p90th_rtime = []
            self._p99th_rtime = []
            
            self._load_ops = []
            self._load_req = []
            
            self._count_rtime_fthr = []

        @property
        def count_rtime_fthr(self):
            if not self._count_rtime_fthr:
                return 0
            return np.mean(self._count_rtime_fthr)
        
        @count_rtime_fthr.setter
        def count_rtime_fthr(self, value):
            self._count_rtime_fthr.append(value)

        @property
        def load_req(self):
            if not self._load_req:
                return 0
            return np.mean(self._load_req)
        
        @load_req.setter
        def load_req(self, value):
            self._load_req.append(value)

        @property
        def load_ops(self):
            if not self._load_ops:
                return 0
            return np.mean(self._load_ops)
        
        @load_ops.setter
        def load_ops(self, value):
            self._load_ops.append(value)

        @property
        def min_rtime(self):
            return min(self._min_rtime)
        
        @min_rtime.setter
        def min_rtime(self, value):
            self._min_rtime.append(value)

        @property
        def max_rtime(self):
            return max(self._max_rtime)
        
        @max_rtime.setter
        def max_rtime(self, value):
            self._max_rtime.append(value)

        @property
        def mean_rtime(self):
            return np.mean(self._mean_rtime)
        
        @mean_rtime.setter
        def mean_rtime(self, value):
            self._mean_rtime.append(value)
            
        @property
        def p50th_rtime(self):
            return np.mean(self._p50th_rtime)
        
        @p50th_rtime.setter
        def p50th_rtime(self, value):
            self._p50th_rtime.append(value)
        
        @property
        def p90th_rtime(self):
            return np.mean(self._p90th_rtime)
        
        @p90th_rtime.setter
        def p90th_rtime(self, value):
            self._p90th_rtime.append(value)
            
        @property
        def p99th_rtime(self):
            return np.mean(self._p99th_rtime)
        
        @p99th_rtime.setter
        def p99th_rtime(self, value):
            self._p99th_rtime.append(value)
            
        @property
        def ops_total(self):
            return self._ops_total
        
        @ops_total.setter
        def ops_total(self, value):
            print 'total ops %i' % value
            self._ops_total += value
            print 'total seen until now %i' % self._ops_total
            
        @property
        def ops_successful(self):
            return self._ops_successful
        
        @ops_successful.setter
        def ops_successful(self, value):
            self._ops_successful += value
            
        @property
        def ops_failed(self):
            return self._ops_failed
    
        @ops_failed.setter
        def ops_failed(self, value):
            self._ops_failed += value
        
        def __repr__(self):
            s = 'GlobalSummary: '
            s += 'ops total: %i ' % self.ops_total
            s += 'ops successful: %i ' % self.ops_successful
            s += 'ops failed: %i ' % self.ops_failed
            
            s += 'min %f ' % self.min_rtime
            s += 'max %f ' % self.max_rtime
            
            s += 'mean %f ' % self.mean_rtime
            s += '50th %f ' % self.p50th_rtime
            s += '90th %f ' % self.p90th_rtime
            s += '99th %f ' % self.p99th_rtime
            
            s += 'ops/sec %f ' % self.load_ops
            s += 'req/sec %f ' % self.load_req
            return s

        
def __analyze_rain_results(data):
    # Summarizes metrics from all global scorecards
    globalSummary = GlobalSummary()
    targetSummaries = []
    
    # RainResults = namedtuple('RainReslts', 'schedule, global_scorecard, target_scoreboards, agg_scoreboards, errors, error_data')
    for node_load in data.keys(): 
        result = data[node_load]

        globalSummary.ops_total = result.global_scorecard['summary']['ops_seen']
        globalSummary.ops_successful = result.global_scorecard['summary']['ops_successful']
        globalSummary.ops_failed = result.global_scorecard['summary']['ops_failed']
        globalSummary.min_rtime = result.global_scorecard['summary']['rtime_min']
        globalSummary.max_rtime = result.global_scorecard['summary']['rtime_max']
        globalSummary.mean_rtime = result.global_scorecard['summary']['sampler_rtime_mean']
        globalSummary.p50th_rtime = result.global_scorecard['summary']['sampler_rtime_50th']
        globalSummary.p90th_rtime = result.global_scorecard['summary']['sampler_rtime_90th']
        globalSummary.p99th_rtime = result.global_scorecard['summary']['sampler_rtime_99th']
        globalSummary.count_rtime_fthr = result.global_scorecard['summary']['rtime_thr_failed']
        globalSummary.load_ops = result.global_scorecard['summary']['effective_load_ops']
        globalSummary.load_req = result.global_scorecard['summary']['effective_load_req']
    
        targetSummaryAggregated = GlobalSummary()
    
        for target_sb in result.target_scoreboards.values():
            target_sb = target_sb['final_scorecard']['summary']
            
            # Dedicated target summary
            targetSummary = GlobalSummary()
            targetSummaries.append(targetSummary)
            targetSummary.ops_total = target_sb['ops_seen']
            targetSummary.ops_successful = target_sb['ops_successful']
            targetSummary.ops_failed = target_sb['ops_failed']
            targetSummary.min_rtime = target_sb['rtime_min']
            targetSummary.max_rtime = target_sb['rtime_max']
            targetSummary.mean_rtime = target_sb['sampler_rtime_mean']
            targetSummary.p50th_rtime = target_sb['rtime_50th']
            targetSummary.p90th_rtime = target_sb['rtime_90th']
            targetSummary.p99th_rtime = target_sb['rtime_99th']
            targetSummary.load_ops = target_sb['effective_load_ops']
            targetSummary.load_req = target_sb['effective_load_req']
            
            # Aggregated target summary
            targetSummaryAggregated.ops_total = target_sb['ops_seen']
            targetSummaryAggregated.ops_successful = target_sb['ops_successful']
            targetSummaryAggregated.ops_failed = target_sb['ops_failed']
            targetSummaryAggregated.min_rtime = target_sb['rtime_min']
            targetSummaryAggregated.max_rtime = target_sb['rtime_max']
            targetSummaryAggregated.mean_rtime = target_sb['sampler_rtime_mean']
            targetSummaryAggregated.p50th_rtime = target_sb['rtime_50th']
            targetSummaryAggregated.p90th_rtime = target_sb['rtime_90th']
            targetSummaryAggregated.p99th_rtime = target_sb['rtime_99th']
            targetSummaryAggregated.load_ops = target_sb['effective_load_ops']
            targetSummaryAggregated.load_req = target_sb['effective_load_req']
            
            # Global summary
            # globalSummary.count_rtime_fthr = target_sb['rtime_thr_failed']
            
    return globalSummary, targetSummaries, targetSummaryAggregated


def __analyze_rtime_poisson(poisson_rtimes):
    aggregated = []
    for ts, time in poisson_rtimes:
        aggregated.extend(ts) 
        
    p50 = np.percentile(aggregated, 50)
    p90 = np.percentile(aggregated, 90)
    return p50, p90

def analyze_experiment(connection):
    # Refine markers
    raw_frame, sync_markers = __refine_markers()
    init_frame = (sync_markers[0], sync_markers[2])
    data_frame = (sync_markers[2], raw_frame[1])
    print 'Data frame %i - %i' % data_frame
    
    ##################################################################
    # # Fetch                                                        #
    ##################################################################
    
    # Load server active infos
    print 'Loading activer server infos...'
    active_servers_infos = __load_server_active_infos(data_frame)
    
    # Load domain names of all domains handed out by the controller
    print 'Loading domain names...'
    domain_names = __load_domain_names(init_frame, data_frame)
    
    # Returns a list of lifetime tuples (start, end) for each domain
    print 'Loading domain activations...'
    __load_domain_activations(data_frame)
    
    # Loads a domain target mapping
    print 'Loading domain target mappings...'
    domain_target_mapping = __load_domain_target_mapping(data_frame)
    
    # Load target times (initialize, start, and end of a target)
    print 'Loading target times...'
    target_times = __load_target_times(data_frame)
    
    # Load node and domain utilization for MEM and CPU
    print 'Loading cpu, mem utilization traces...'
    cpu_utilization, mem_utilization = __load_traces(data_frame, domain_names)
    
    # Load Rain generated TS for all domains based on Sonar Metric Writer
    print 'Loading rtime 99th percentile traces...'
    rain_rtime_p99th_TS = __load_domain_rtime_99th_TS(data_frame, domain_target_mapping)
    
    # Load Rain generated TS for all domains based on Poisson sampling
    print 'Loading poisson rtime traces...'
    rain_rtime_poisson_TS = __load_domain_rtime_poisson_TS(data_frame, domain_target_mapping)
    
    # Read Rain metrics
    print 'Loading rain results...'
    rain_results = {}
    for node in DRIVER_NODES: 
        result = __load_rain_results(node, data_frame)
        rain_results[node] = result 
    
    ##################################################################
    # # Analyze                                                       #
    ##################################################################
    
    # Analyze response time traces (poisson sampling)
    rtime_p50th, rtime_p90th = __analyze_rtime_poisson(rain_rtime_poisson_TS)
    
    # Analyze and aggregate rain results from multiple nodes
    global_summary, target_summary, targetSummaryAggregated = __analyze_rain_results(rain_results)
    
    # Calculate average server count
    cserver_mean = __analyze_avg_server_count(active_servers_infos)
    
    # Calculate server activations and deactivations
    activations, deactivations = __analyze_server_activations(active_servers_infos)
    
    # Analyze server count percentiles
    cserver_min, cserver_max, cserver_p50th, cserver_p90th = __analyze_min_max_server_count(active_servers_infos)
    
    # Calculate average server CPU, MEM load and threshold violations
    cpu_mean, cpu_p50, cpu_p90, cpu_p99, cpu_thr = __analyze_avg_server_load(active_servers_infos, cpu_utilization, 90)
    mem_mean, mem_p50, mem_p90, mem_p99, mem_thr = __analyze_avg_server_load(active_servers_infos, mem_utilization, 90)
    
    # Count cell threshold violations based on Poisson sampled TS of rtimes
    total_cells, violated_cells = __analyze_rtime_thr_violations(3000, rain_rtime_p99th_TS)
    
    # Migrations
    migrations_successful, migrations_failed, migrations_server_active, migrations_triggered, migrations_initial = __fetch_migrations(data_frame)
    
    ##################################################################
    # # Results                                                       #
    ##################################################################
    # Map contains all results of the experiment
    global_metric_aggregation = {
                                 'server_activations' : activations,
                                 'server_deactivations' : deactivations,
                                 'server_count_mean' : cserver_mean,
                                 'server_count_p50th' : cserver_p50th,
                                 'server_count_p90th' : cserver_p90th,
                                 'server_count_min' : cserver_min,
                                 'server_count_max' : cserver_max,
                                 'sampled_rtime_p50th' : rtime_p50th,
                                 'sampled_rtime_p90th' : rtime_p90th,
                                 'mean_rtime_p2p50th' : targetSummaryAggregated.p50th_rtime,
                                 'mean_rtime_p2p90th' : targetSummaryAggregated.p90th_rtime,
                                 'cpu_load' : cpu_mean,
                                 'cpu_p50th' : cpu_p50,
                                 'mem_load' : mem_mean,
                                 'total_ops_successful' : global_summary.ops_successful,
                                 'total_operations_failed' : global_summary.ops_failed,
                                 'total_ops_seen' : global_summary.ops_total,
                                 'average_response_time' : global_summary.mean_rtime,
                                 'max_response_time' : global_summary.max_rtime,
                                 'effective_load_ops' : targetSummaryAggregated.load_ops,
                                 'effective_load_req' : targetSummaryAggregated.load_req,
                                 'total_reseponse_time_threshold' : global_summary.count_rtime_fthr,
                                 'migrations_successful' : len(migrations_successful),
                                 'srv_cpu_violations' : cpu_thr,
                                 }
    
    # Order in which global results are dumped
    dump = ('server_count_mean', 'server_count_p50th', 'server_count_p90th', 'server_count_min', 'server_count_max',
            'cpu_load', 'cpu_p50th', 'mem_load', 'total_ops_successful', 'total_operations_failed', 'average_response_time',
            'sampled_rtime_p50th', 'sampled_rtime_p90th', 'mean_rtime_p2p50th', 'mean_rtime_p2p90th',
             'max_response_time', 'effective_load_ops', 'effective_load_req', 'total_reseponse_time_threshold',
             'migrations_successful', 'srv_cpu_violations', 'server_activations', 'server_deactivations', 'total_ops_seen')
    
    # Create data for the dump order
    data = []
    for element in dump:
        try:
            value = global_metric_aggregation[element]
            data.append(str(value))
            print '%s = \t %s' % (element, str(value)) 
        except: 
            print 'Error in %s' % element
            
    # Finally dump data
    __dump_elements(tuple(data), dump, separator='\t')


if __name__ == '__main__':
    # Dump the configuration
    __dump_configuration()
    
    # Establish connection
    connection = __connect()
    try:
        # Run experimental analysis
        analyze_experiment(connection)
    except:
        # Error happened
        traceback.print_exc(file=sys.stdout)
    __disconnect()
    
    # Dump all warnings that occurred
    __dump_warns()
