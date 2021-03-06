from hosts import RelayHosts
from twisted.internet import defer, reactor
import base
import drones

# Connections to the relay hosts
hosts = RelayHosts()

def finished(done, client_list):
    print "execution successful"
    print "Status:"
    for i in done: 
        print i[0]
        
    reactor.stop()
 
 
def deploy_phase(client_list):
    print 'deploying rain driver...'
    
    dlist = []
    
    for host in hosts.get_hosts('deploy'):
        print '   %s' % (host)
        d = base.launch(hosts, client_list, host, 'rain_deploy', wait=True)
        dlist.append(d)
    
    # Wait for all drones to finish and set phase
    dl = defer.DeferredList(dlist)
    dl.addCallback(finished, client_list)
    
    
def main():
    # Create drones
    drones.main()
    
    # Add hosts
    hosts.add_host('load0', 'deploy')
    hosts.add_host('load1', 'deploy')
    
    # Connect with all drone relays
    hosts_map = hosts.get_hosts_list()
    dlist = base.connect(hosts_map)
        
    # Wait for all connections
    wait = defer.DeferredList(dlist)
    wait.addCallback(deploy_phase)
    
    # Start the Twisted reactor
    reactor.run()

if __name__ == '__main__':
    main()
