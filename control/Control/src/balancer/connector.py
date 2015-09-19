'''
Provides a service to receive load data from Sonar
'''


from collector import NotificationClient, NotificationService
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer
from thrift.transport import TSocket, TTransport
import configuration as config
import threading

subscriptions = []

class ServiceThread(threading.Thread):
    def __init__(self, handler):
        threading.Thread.__init__(self)
        
        # Mark this one as a daemon so it can be killed by python
        self.setDaemon(True)
        self.setName('Metric handler thread')
        
        self.handler = handler
        
    def run(self):
        print self.handler
        processor = NotificationClient.Processor(self.handler)
        transport = TSocket.TServerSocket(host=config.LISTENING_INTERFACE_IPV4, port=config.LISTENING_PORT)
        
        tfactory = TTransport.TBufferedTransportFactory()
        pfactory = TBinaryProtocol.TBinaryProtocolFactory()
        
        # Launch the server
        server = TServer.TSimpleServer(processor, transport, tfactory, pfactory)
        
        print 'Starting TSD callback service...'
        server.serve()
  
def __subscribe(model_host, interface=config.LISTENING_INTERFACE_IPV4):
    print 'Subscribing %s' % model_host.name
    filters = []
    fi = model_host.get_watch_filter()
    identifier = '%s.%s' % (fi.hostname, fi.sensor)
    if identifier in subscriptions:
        return
    else:
        filters.append(fi)
        subscriptions.append(identifier)
    
    # Subscribe
    if filters:
        print 'Subscribing now...'
        serviceClient.subscribe(interface, config.LISTENING_PORT, filters),
    
    
def __unsubscribe(model_host, interface=config.LISTENING_INTERFACE_IPV4):
    print 'Unsubscribe %s' % model_host.name
    # Not supported by Sonar
    
def subscription_handler(model_host, alive):
    if alive:
        __subscribe(model_host)
    else:
        __unsubscribe(model_host)
    

def connect_sonar(model, handler, interface=config.LISTENING_INTERFACE_IPV4, collector=config.COLLECTOR_HOST):
    print 'Connecting with Sonar ...'

    # Start the Receiver    
    receiver = ServiceThread(handler)
    receiver.start()
    
    # Register the Receiver in the Controller
    # Make socket
    transport = TSocket.TSocket(collector, config.COLLECTOR_PORT)
    
    # Buffering is critical. Raw sockets are very slow
    transport = TTransport.TBufferedTransport(transport)
    
    # Wrap in a protocol
    protocol = TBinaryProtocol.TBinaryProtocol(transport)
    
    # Create a client to use the protocol encoder
    global serviceClient
    serviceClient = NotificationService.Client(protocol)
    
    # Connect!
    transport.open()

    # Define hosts and sensors to listen on
    filters = []
    for host in model.get_hosts():
        fi = host.get_watch_filter()
        filters.append(fi)

    # Subscribe
    print 'Subscribing now...'
    serviceClient.subscribe(interface, config.LISTENING_PORT, filters)
    
    # Register subscribe handler
    print 'Register subscribe handler...'
    model.add_subscribe_handler(subscription_handler)
    
