import sys
import time
import numpy as np
import argparse
import os

# Program assumes default checkout directory structure
p = os.path.split(__file__)[0]
sys.path.append(os.path.realpath(os.path.join(p, '..', '..', 'src')))
sys.path.append(os.path.realpath(os.path.join(p, '..', '..', 'generated')))

from thrift.protocol import TBinaryProtocol
from thrift.transport import TSocket, TTransport
from collector import ManagementService, ttypes
from workload import util

COLLECTOR_IP = 'monitor0.dfg'
MANAGEMENT_PORT = 7931
LOGGING_PORT = 7921

'''
Example usage for this in an R script: 
data = read.csv(pipe('python D:/work/control/Control/src/sonar/rsonar.py --host srv0 --sensor psutilcpu --from-date 11/20/2013 --from-time 8:00 --to-date 11/20/2013 --to-time 20:00'))
'''

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
Disconnect from Sonar
'''
def __disconnect():
    transportManagement.close()
    

'''
Convert a datetime from a string to a UNIX timestamp
'''
def __to_timestamp(date):
    res = time.strptime(date, '%m/%d/%Y %H:%M')    
    return int(time.mktime(res))


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
    if not valid_empty: 
        # Mean of all values gerater zero
        assert len(result) > 0
        
        # Mean of all values gerater zero
        assert np.mean(result) > 0
        
        # Time between the first and last entry greater 30 secs
        assert (time[-1] - time[0]) > 30
        
    # Return time series and timestamps
    return result, time
    
    
'''
Main function reads all arguments, execues a Sonar query and returns results
'''
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Execute a Sonar query for time series data.')
    parser.add_argument('--host', dest='host', help='Hostname', required=True)
    parser.add_argument('--sensor', dest='sensor', help='Sensor name', required=True)
    parser.add_argument('--from-date', dest='fromdate', help='Start date', required=True)
    parser.add_argument('--from-time', dest='fromtime', help='Start time', required=True)
    parser.add_argument('--to-date', dest='todate', help='End date', required=True)
    parser.add_argument('--to-time', dest='totime', help='End date', required=True)
    args = parser.parse_args()

    # Convert dates to timestamps
    query_from = __to_timestamp( "%s %s" % (args.fromdate, args.fromtime)  )
    query_to =  __to_timestamp("%s %s" % (args.todate, args.totime))

    # Establish connection
    connection = __connect()
    
    # Query time series
    result, time = __fetch_timeseries(connection, args.host, args.sensor, [query_from, query_to])
    
    # Close connection
    __disconnect()
    
    # Print a CSV table with the time series
    for i in xrange(0, len(result)):
        print '%i,%i' % (time[i], result[i])
    

