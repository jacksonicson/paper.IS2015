from service import times_client
import sys

'''
Example usage for this in an R script: 
data = read.csv(pipe('python D:/work/dev/sonar/sonar/Times/src/radapt.py SIS_142_cpu'))
'''

if len(sys.argv) < 2:
    print 'Wrong number of arguments!'
    sys.exit(1)

try:
    name = sys.argv[1]
    port = times_client.port_DEFAULT
    if len(sys.argv) > 2:
        if sys.argv[2] == 'MKI':
            port = times_client.port_MKI
        else:
            port = times_client.port_MKII
    
    connection = times_client.connect(port)
    result = connection.find(name)
    if len(result) == 0:
        print 'No TS found with name: %s' %name
        sys.exit(1)
    
    print 'Time, Value'
    ts = connection.load(name)
    for element in ts.elements:
        print '%i,%i' % (element.timestamp, element.value)
    sys.stdout.flush()
    
finally:
    times_client.close()