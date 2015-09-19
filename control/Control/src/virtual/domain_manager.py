from twisted.internet import defer, reactor
import allocation
import clone
import util
import sys
from logs import sonarlog

# Setup logging
logger = sonarlog.getLogger('controller')

def try_connecting(domain_configuration):
    '''
    Wait until a connection with domain's Relay service
    could be established. 
    '''
    return clone.try_connecting(domain_configuration.name, False)


def start_and_migrate(domain, target_node):
    '''
    Start domain and migrate it to the target node
    '''
    
    # Get libivrt connection
    _, lv_connection = util.find_domain(domain)
    
    # Lookup libvirt domain object
    lv_domain = lv_connection.lookupByName(domain)
    
    # Launch domain
    print 'Starting domain: %s' % domain
    started = False
    while not started:
        try:
            lv_domain.create()
            started = True
        except:
            print 'ERROR while starting domain'
            print sys.exc_info()[0]
            print 'retrying...'
    
    # Create a deferred to return    
    dret = defer.Deferred()
    
    # Migration callback handler
    def handler(domain_name, node_from, node_to, starsst, end, info, 
                success, error):
        logger.info('Migrated status: %s - %s' % (domain_name, success))
        
        # Migration failed
        if success == False:
            print 'Error - migration failed, checking if domain still exists...'
            _, lv_connection = util.find_domain(domain)
            if lv_connection is not None:
                logger.info('Retrying migration: %s -> %s' % (domain, target_node))
                reactor.callFromThread(lambda: allocation.migrateDomain(domain, lv_connection.getHostname(), 
                                                                    target_node, handler))
                # Retry
                return
            else:
                print 'Error - Fatal - Could not retry migration, domain is not active in the infrastructure'
        
        # Trigger defer callback - for successful and unsuccessful migrations
        reactor.callFromThread(lambda: dret.callback(domain_name)) 
    
    
    # Check if migration is necessary
    if lv_connection.getHostname().find(target_node) == -1:
        # Migration is neccessary
        logger.info('Migrating: %s -> %s from %s' % (domain, target_node, lv_connection.getHostname()))
        allocation.migrateDomain(domain, lv_connection.getHostname(), 
                                 target_node, handler)
    else:
        # Migration is NOT necessary
        logger.info('Skipping: %s -> %s from %s' % (domain, target_node, lv_connection.getHostname()))
        # reactor.callLater(3, lambda: dret.callback(domain))
        return domain
        
    # Return deferred object that will be called after the migration
    return dret
    
    
def shutdown(domain):
    '''
    Stop given domain
    '''
    
    # Find libvirt connection for domain
    _, lv_connection = util.find_domain(domain)
    
    # Get libvirt domain object
    lv_domain = lv_connection.lookupByName(domain)
    
    # Destroy domain
    print 'Shutdown domain: %s' % domain 
    lv_domain.destroy()
    
    