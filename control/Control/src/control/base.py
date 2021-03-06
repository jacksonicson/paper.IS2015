from relay import RelayService
from thrift.protocol import TBinaryProtocol
from thrift.transport import TTwisted
from twisted.internet import defer, reactor
from twisted.internet.protocol import ClientCreator
import drones
import configuration as config

'''
Provides helper functions for all control modules
'''

def client(hosts, client_list, host):
    return client_list[hosts.get_index(host)][1]

def launch(hosts, client_list, host, droneName, wait=True):
    try:
        drone = drones.load_drone(droneName)
        if wait:
            print 'launching: %s' % (drone.name)
            d = client(hosts, client_list, host).launch(drone.data, drone.name)
            return d
        else:
            print 'launching (no wait): %s' % (droneName)
            d = client(hosts, client_list, host).launchNoWait(drone.data, drone.name)            
            return d
    except Exception, e:
        print 'error %s' % (e)


def poll_for_message(hosts, client_list, host, droneName, message):
    try:
        print 'launching (poll for message): %s' % (droneName)
        drone = drones.load_drone(droneName)
        d = client(hosts, client_list, host).pollForMessage(drone.data, drone.name, message)
        return d
    except Exception, e:
        print 'error %s' % (e)


def wait_for_message(hosts, client_list, host, droneName, message, out=None):
    try:
        print 'launching (wait for message): %s' % (droneName)
        drone = drones.load_drone(droneName)
        d = client(hosts, client_list, host).waitForMessage(drone.data, drone.name, message, out)
        return d
    except Exception, e:
        print 'error %s' % (e)


def connect_err(failure):
    print 'connection failed'
    print failure

def connect(hosts_map):
    dlist = []
    for i in hosts_map:
        print 'Connecting with relay %s:%i ' % (i, config.RELAY_PORT)
        
        creator = ClientCreator(reactor,
                          TTwisted.ThriftClientProtocol,
                          RelayService.Client,
                          TBinaryProtocol.TBinaryProtocolFactory(),
                          ).connectTCP(i, config.RELAY_PORT)
        creator.addCallback(lambda conn: conn.client)
        
        d = defer.Deferred()
        creator.addCallback(d.callback)
        creator.addErrback(d.errback)
        dlist.append(d)
        
    return dlist

def millis():
    import time as time_
    return int(round(time_.time() * 1000)) 
    