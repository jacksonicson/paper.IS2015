from service import times_client
import csv
from times import ttypes 

def load_trace(path, identifier):
    print 'loading O2 data from %s -> %s' % (path, identifier)
    ts_file = open(path, 'rU')
    reader = csv.reader(ts_file, delimiter=';', quotechar='"')
    
    # Read the first line (CSV header) 
    line = reader.next()

    # Get all the service names    
    ts_names = []
    ts_elements = []
    for i in range(0, len(line)):
        filename = identifier + '_' + str(line[i])
        ts_names.append(filename)
        ts_elements.append([])
        
        # Check series exists
        res = connection.find(filename)
        if res:
            print 'removing: %s' % filename 
            connection.remove(filename)
        
        # 3 second monitoring frequency
        print 'creating: %s' % (filename)
        connection.create(filename, 60 * 60)
        
    # Timestamp 
    timestamp = 0
     
    # Read all the CSV lines
    for line in reader:
        for i in range(0, len(line)):
            element = ttypes.Element()
            element.timestamp = timestamp
            element.value = int(line[i])
            
            ts_elements[i].append(element)
        
        timestamp += (60 * 60)
    
    # Send TS to the service
    print 'Sending TS data...'
    for i in range(0, len(ts_names)):
        connection.append(ts_names[i], ts_elements[i])
    
            
if __name__ == '__main__':
    global connection
    connection = times_client.connect()
    
    #############################
    # Configuration #############
    files = [
                          ('D:/backups/time series data/O2 time series/eai-rcs-hour.csv', 'retail'),
                          ('D:/backups/time series data/O2 time series/eai-rcs-hour.csv', 'business'),
                          ]
    #############################

    for ts_file in files:
        print ts_file
        load_trace(ts_file[0], 'RAW_O2_%s' % (ts_file[1]))

    # Close connection
    times_client.close()
