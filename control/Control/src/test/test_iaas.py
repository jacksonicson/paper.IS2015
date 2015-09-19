'''
Test program for the IaaS service
'''

from iaas import Infrastructure
from thrift.protocol import TBinaryProtocol
from thrift.transport import TTwisted, TSocket
from twisted.internet import reactor
from twisted.internet.protocol import ClientCreator
import configuration as config
import time

def main():
    creator = ClientCreator(reactor,
                          TTwisted.ThriftClientProtocol,
                          Infrastructure.Client,
                          TBinaryProtocol.TBinaryProtocolFactory(),
                          ).connectTCP(config.IAAS_INTERFACE_IPV4, config.IAAS_PORT)
    creator.addCallback(lambda conn: conn.client)
    creator.addCallback(connected)
    reactor.run()
    
def connected(c):
    # Set connection 
    global client
    client = c
    
    # Start small domain
    d = client.allocateDomain(1, 1)
    d.addCallback(small_domain_allocated)
    
def small_domain_allocated(a):
    # Start small domain
    d = client.deleteDomain(a)
    d.addCallback(done)
    
def done(a):
    print 'done'
    reactor.stop()
    
    
    
def ds(dn):
    if dn is False:
        d = client.isDomainReady(dnn)
        d.addCallback(ds)
        print 'connection retry...'
        time.sleep(1)
    else:
        print 'launching drone...'
        d = client.launchDrone('spec_dbload', dnn)
        d.addCallback(launched)
        
def launched(v):
    print 'launching drone...'
    d = client.launchDrone('glassfish_start', dnn)
    d.addCallback(glassfish)
    
def glassfish(v):
    print 'launching drone...'
    d = client.launchDrone('glassfish_wait', dnn)
    d.addCallback(deleted)
    
def deleted(v):
    print 'done'
    print v


def test_allocation_cycle(client):
    domain = test_allocate(client)
    time.sleep(20)
    # test_wait_ready(client, domain)
    # test_launch_drone(client, domain, 'glassfish')
    test_deallocate(client, domain)
    test_deallocate(client, domain)
    test_deallocate(client, domain)    

def test_launch_drone(client, domain , drone):
    print 'Launching drone...'
    client.launchDrone(drone, domain) 

def test_wait_ready(client, domain):
    print 'Waiting...'
    while client.isDomainReady(domain) == False:
        print 'Waiting for domain...'
        time.sleep(3)

def test_deallocate(client, domain):
    print 'delete: %s' % domain
    client.deleteDomain(domain)

def test_allocate(client):
    hostname = client.allocateDomain(1)
    print 'hostname: %s' % hostname
    return hostname

if __name__ == '__main__':
    main()
    
