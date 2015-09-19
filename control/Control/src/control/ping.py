from twisted.internet import reactor
import drones
import base
import conf_domains
import conf_nodes

# Add hosts
hosts = []
index = 0

for dom_descriptor in conf_domains.initial_domains:
    hosts.append(dom_descriptor.name)

def finished(done, client_list):
    print "execution successful %s" % done
    reactor.stop()


def start_phase(client_list):
    print 'All Systems alive!'
    finished(client_list, client_list)

    
def errback(failure, host):
    print 'FAILED with %s' % host
    reactor.callLater(1, connect_next)
    

def connected(client, host):
    print 'OK with %s' % host
    reactor.callLater(0, connect_next)
    global index
    index += 1
    

def connect_next():
    global index
    
    if index >= len(hosts):
        print 'Successful'
        reactor.stop()
        return
    
    host = hosts[index]
    dlist = base.connect((host,))
    dlist[0].addCallback(connected, host)
    dlist[0].addErrback(errback, host)

    
def main():
    # Create drones
    drones.main()

    # Connect with all hosts step by step    
    connect_next()
    
    # Start the Twisted reactor
    reactor.run()

if __name__ == '__main__':
    main()
