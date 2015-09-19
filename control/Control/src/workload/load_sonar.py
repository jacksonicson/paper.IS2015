from collector import ManagementService, ttypes
from thrift.protocol import TBinaryProtocol
from thrift.transport import TSocket, TTransport
from timeutil import *  # @UnusedWildImport
import conf_load
import configuration
import sonar_meta as meta
import time
import util
from times import ttypes as times_types

# Connection with sonar
connection = None

'''
Convert a datetime from a string to a UNIX timestamp
'''
def __to_timestamp(date):
    res = time.strptime(date, '%d/%m/%Y %H:%M:%S')    
    return int(time.mktime(res))

'''
Connect with Sonar collector 
'''
def __connect():
    global connection
    if connection is not None:
        return connection
        
    # Make socket
    transportManagement = TSocket.TSocket(configuration.COLLECTOR_IP, configuration.COLLECTOR_MANAGEMENT_PORT)
    transportManagement = TTransport.TBufferedTransport(transportManagement)
    connection = ManagementService.Client(TBinaryProtocol.TBinaryProtocol(transportManagement));
    
    # Open the transports
    while True:
        try:
            transportManagement.open();
            break
        except Exception:
            print 'Retrying connection...'
            time.sleep(1)
            
    return connection

'''
Fetch a timeseries either from Sonar or from the local file cache
if possible. 
'''
def __fetch_timeseries(host, sensor, timeframe):
    from filelock.fl import FileLock
    cache_file = '%s_%s_%s_%s' % (str(host), str(sensor), str(timeframe[0]), str(timeframe[1]))
    cache_file = configuration.path(cache_file)
    with FileLock(cache_file, timeout=60):
        try:
            with open(cache_file):
                # Open file in binary mode
                f = open(cache_file, 'rb')
                t = TTransport.TFileObjectTransport(f)
                prot = TBinaryProtocol.TBinaryProtocolAccelerated(t)
                
                # Decode binary stream as Thrift object
                ts = times_types.TimeSeries()
                ts.read(prot)
                f.close()
                
                # Convert to array
                load = [x.value for x in ts.elements]
                
                # Return elements
                return load
            
        except IOError:
            __connect()
            
            query = ttypes.TimeSeriesQuery()
            query.hostname = host
            query.startTime = timeframe[0]
            query.stopTime = timeframe[1]
            query.sensor = sensor
            
            result = connection.query(query)
            _, ts_load = util.to_array_collector(result, timeframe)
            
            # Build file as Thrift object
            ts = times_types.TimeSeries()
            ts.name = 'cache'
            ts.frequency = 3
            ts.elements = []
            
            for i, load in enumerate(ts_load):
                new_el = times_types.Element(i*3, int(load))
                ts.elements.append(new_el)
            
            # Write Thrift object to a cache file
            f = open(cache_file, 'wb')
            t = TTransport.TFileObjectTransport(f)
            prot = TBinaryProtocol.TBinaryProtocolAccelerated(t)
            ts.write(prot)
            f.close()
            
            return ts_load
        
##################################################################

def count():
    return len(meta.raw_segments)


def get_user_profile(index, domain_size):
    print 'FATAL ERROR: Sonar does not support user profiles'
    import sys
    sys.exit(1)


def get_user_profile_name(index, domain_size):
    print 'FATAL ERROR: Sonar does not support user profiles'
    import sys
    sys.exit(1)

def get_cpu_trace(index, domain_size):
    return get_cpu_profile(index, domain_size)


def get_cpu_profile(index, domain_size):
    RAW, host = meta.get(conf_load.SCRAMBLER, index)
    START, END = RAW.split('    ')
    start = __to_timestamp(START)
    stop = __to_timestamp(END)
    
    limit = start + hour(6)
    if stop < limit:
        print 'WARNING: Time series is not long enough'
    stop = min(stop, limit)
    
    raw_frame = (start, stop)
    result = __fetch_timeseries(host, 'psutilcpu', raw_frame)
    
    frequency = sec(3)  # Sampling frequency of Sonar
    
    return frequency, result


if __name__ == '__main__':
    '''
    Tests if all registered TS in sonar meta are of sufficient length
    '''
    import matplotlib.pyplot as plt
    plot_counter = 0
    for segment in meta.raw_segments:
        RAW, host = segment
        START, END = RAW.split('    ')
        start = __to_timestamp(START)
        stop = __to_timestamp(END)
        raw_frame = (start, stop) 
        load = __fetch_timeseries(host, 'psutilcpu', raw_frame)
        
        # Check whether the TS is long enough
        if len(load) < 7600: 
            print "invalid TS: ('%s', '%s')" % (segment[0], segment[1])
            
        # Plot time series for debugging purpose
        fig = plt.figure()
        plot_counter += 1
        ax = fig.add_subplot(111)
        ax.plot(range(len(load)), load)
        plt.savefig(configuration.path('sonar_trace%s' % (plot_counter), 'png'), dpi=30)
        plt.close()
        
            