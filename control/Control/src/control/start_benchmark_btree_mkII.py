from balancer import controller
from behaviorTree import behaviorTree as btree
from logs import sonarlog
from twisted.internet import defer, reactor
import behaviors
import hosts
import configuration
import conf_domains

######################
# CONFIGURATION     ##
######################
START_BT = True
######################

# Force production mode
configuration.force_production_mode()

# Setup logging
logger = sonarlog.getLogger('start_benchmark')

# Strategy instance
controller = controller.Controller()


def errback(failure):
    print 'Error while executing'
    print failure
    import sys
    sys.exit(1)


def finished(status):
    print 'Behavior reached end'
    if status == False:
        import sys
        sys.exit(1) 
    

def main():
    logger.log(sonarlog.SYNC, 'starting BTree')
    
    # Blackboard with hosts manager
    bb = btree.BlackBoard()
    bb.hosts = hosts.RelayHosts()
    
    # Use the domain setup type configuration in the domains module to fill hosts
    for entry in conf_domains.initial_domains_setup_types:
        bb.hosts.add_host(*entry)
    
    # Add load drivers to hosts
    bb.hosts.add_host('load0', 'load')
    bb.hosts.add_host('load1', 'load')
    
    # Start benchmark ###################################
    start = btree.Sequence(bb)
    
    # Log sync marker
    start.add(behaviors.SyncMarker('start of startup sequence'))
    
    # Stop everything
    start.add(behaviors.ShutdownAllDomains())
    
    # Add bheaviors to start and initialize the domains
    start.add(behaviors.AllocateDomains(controller))
    
    # Connect with all relay services
    start.add(behaviors.ConnectRelay())
    
    # Configure glassfish
    start.add(behaviors.ConfigureGlassfish())
    
    # Start Glassfish and Database
    pl = btree.ParallelNode(bb)
    pl.add(behaviors.StartGlassfish())
    pl.add(behaviors.StartDatabase())
    start.add(pl)
    
    # Start Rain and connect with its control service
    start.add(behaviors.StartRain())
    start.add(behaviors.ConnectRain())
    
    # Start controller
    start.add(behaviors.StartController(controller))
    
    # Trigger load generation in Rain
    start.add(behaviors.TriggerRain())
    
    # Stop benchmark ####################################
    stop = btree.Sequence(bb)
    stop.add(behaviors.ConnectRelay())
    stop.add(behaviors.StopGlassfishRain())
    
    # Execute Behavior Trees ############################
    if START_BT:
        print 'Running start BTree'
        defer = start.execute()
    else:
        print 'Running stop BTree'
        defer = stop.execute()
        
    # Finished callback to clean up          
    defer.addCallback(finished)

    # Start the Twisted reactor
    reactor.run()


if __name__ == '__main__':
    # Connect with Sonar logging
    sonarlog.connect()
    
    # Run main method
    main()
    
