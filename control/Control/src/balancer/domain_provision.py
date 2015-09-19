from logs import sonarlog
import conf_domains
import conf_domainsize
import configuration
import sys

# Setup logging
logger = sonarlog.getLogger('controller')

class Provisioning(object):
    '''
    Allocates and deallocates domains in the model only.
    '''
    
    def __init__(self, model, pump, placement_strategy):
        # Model references
        self.model = model
        self.pump = pump
        
        # Placement strategy
        self.placement = placement_strategy

        # Available domains sorted by their size        
        self.available = []
        for s in xrange(conf_domainsize.count_domain_sizes()):
            self.available.append(conf_domains.get_available_domains_by_size(s))
                     
        # Wasted lists
        self.wasted = []
                               
        # List of lists that hold all online domains
        self.online = [] 


    def get_online_domain_configuration(self, domain_name):
        for online_domain_config in self.online:
            if online_domain_config.name == domain_name:
                return online_domain_config
    
    def handin(self, domain_name):
        # Find domain object by name
        domain_config = self.get_online_domain_configuration(domain_name)
        if domain_config is None: 
            print 'WARN: Domain is not running: %s' % domain_name
            logger.warn('Handin failed, domain is not running: %s' % domain_name)
            return
        
        # Add domain to wasted list (do not reuse VMs)        
        self.wasted.append(domain_config)
        
        # Remove from online list
        del self.online[self.online.index(domain_config)]
        
        # Delete domain from model
        self.model.del_domain(domain_config)
        
        # Update active domains
        self.model.log_active_server_info()
            
        # Do logging
        print 'Handing domain: %s' % domain_config.name
        logger.info('Handin domain: %s' % domain_config.name)
        
        # Return domain object
        return domain_config
        
    
    def handout(self, loadIndex, domain_size):
        # Offline list
        offline_list = self.available[domain_size]
        # is a domain available
        if not offline_list:
            logger.error('cannot handout a domain, offline list is empty')
            print 'offline_medium list is empty'
            return None
        
        # Get next domain
        domain_config = offline_list.pop()
        
        # Update domain workload profile load index
        domain_config.loadIndex = loadIndex
        
        # Update online list
        self.online.append(domain_config)
        
        # Execute placement strategy
        node = self.placement.placement(domain_config)

        # Add domain to the model
        self.model.new_domain(node, domain_config)
        
        # Upate active domains
        self.model.log_active_server_info()
        
        # Do logging
        print 'Handout domain: %s' % domain_config.name
        logger.info('Handout domain: %s' % domain_config.name)
        
        return domain_config, node
        
    
class ConcreteProvisioning(Provisioning):
    '''
    Wrapper around provisioning that triggers domain start
    and stops on the production infrastructure
    '''
    def __init__(self, model, pump, placement_strategy):
        # This class only works in production mode
        assert configuration.PRODUCTION
        
        # Super init
        super(ConcreteProvisioning, self).__init__(model, pump, placement_strategy)
        
    def get_online_domain_configuration(self, domain_name):
        return super(ConcreteProvisioning, self).get_online_domain_configuration(domain_name)
        
    def handin(self, domain_name):
        # Update model
        try:
            domain_config = super(ConcreteProvisioning, self).handin(domain_name)
        except:
            import traceback
            traceback.print_exc()
        
        # Shutdown domain by libvirt
        print 'Destroying domain by libvirt...'
        from virtual import domain_manager
        domain_manager.shutdown(domain_config.name)
        
        # Everything is ok
        return True
        
    
    def handout(self, loadIndex, domain_type):
        # Update model
        try:
            domain_config, node = super(ConcreteProvisioning, self).handout(loadIndex, domain_type)
        except:
            import traceback
            traceback.print_exc() 
        
        # Start and migrate domain by libvirt
        print 'start and migrate: %s' % domain_config.name
        try:
            from virtual import domain_manager
            d = domain_manager.start_and_migrate(domain_config.name, node)
            print 'domain %s successfully started' % domain_config.name
        except:
            print 'Error while starting and migration VM %s' % sys.exc_info()[1] 
        
        return d
        
        
