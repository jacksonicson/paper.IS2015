import time
import configuration 

class MetricHandler(object):
    '''
    Receives metric data from the simulation or from Sonar
    and feeds the data into the model. The data is later used
    by the load balancer to resolve over- and underloads.
    '''
    def __init__(self, model):
        self.model = model
        self.lastt = time.time()
        self.crt = 0
    
    def receive(self, datalist):
        if (time.time() - self.lastt) > 10:
            print 'WARN: Bottleneck in metric handler thread'
        else:
            if configuration.PRODUCTION:
                self.crt = (self.crt + 1) % 500
                if self.crt == 0:
                    print '#',
            
        self.lastt = time.time()
        
        # Go over all received data
        for data in datalist:
            # Get hostname
            hostname = data.id.hostname
            
            # Get domain or node from model
            host = self.model.get_host(hostname)
            if host == None:
                return
             
            # Add data to the domain or node
            host.put(data.reading)