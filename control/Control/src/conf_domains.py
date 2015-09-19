'''
Configures static and dynamic domains
'''
from workload import load
import conf_domainsize
import json
import clparams
import sys

# Configuration ##############
AVAILABLE_DOMAINS = 35 # Number of domains for each *domainsize*
INITIAL_DOMAINS = 0 # Number of initial domains
##############################

# Load parameters from command line
clparams.load_parameters(sys.modules[__name__])

class DomainConfiguration(object):
    '''
    Configuration of a single domain, either static or dynamic 
    '''
    def __init__(self, index, name, size, loadIndex, clone_source = None):
        # Index of this configuration
        self.index = index
        
        # Name
        self.name = name
        
        # Domain size 
        self.size = size
        
        # Load index can be used to lookup a workload profile  
        self.loadIndex = loadIndex
        
        # Domain name that is used as clone source to create a new domain instance for this configuration
        self.clone_source = clone_source
        
    def get_domain_spec(self):
        return conf_domainsize.get_domain_spec(self.size)


# Available domains for dynamic activation
available_domains = []
for size, source in enumerate(conf_domainsize.get_domain_size_clone_sources()): #  xrange(conf_domainsize.count_domain_sizes()):
    available_domains.extend([DomainConfiguration(i, 'dynamic_size%i_index%i' % (size, i), size, None, source) for i in range(AVAILABLE_DOMAINS)])

# Initial domain configuration
initial_domains = []  # Domain profile mapping
initial_domains_setup_types = []  # List is used to configure the domains by using Relay
for i in xrange(INITIAL_DOMAINS):
    # Create a new domain profile mapping
    name = 'static_size0_index%i' % (i)
    clone_source = conf_domainsize.get_domain_size_clone_sources()[conf_domainsize.DEFAULT]
    domain = DomainConfiguration(i, name, conf_domainsize.DEFAULT, i, clone_source)
    
    # Add domain to active domains
    initial_domains.append(domain)
    
    # Add domain with its setup targets 
    initial_domains_setup_types.append((name, 'target'))
    initial_domains_setup_types.append((name, 'database'))
    
def to_delete_domains():
    '''
    Returns a list of domain names to delete
    '''
    # Domains to delete from the infrastructure (clone script)
    delete_names = []
    delete_names.extend(conf.name for conf in initial_domains)
    delete_names.extend(conf.name for conf in available_domains)
    return delete_names
    
    
def to_clone_domains():
    '''
    Returns a list of domain configurations for cloning process
    '''
    clone = []
    clone.extend(initial_domains)
    clone.extend(available_domains)
    return clone
      

def is_initial_domain(domain_name):
    '''
    Check if domain name is in the initial_domains list. This function is used to filter
    out domains that are running in the infrastructure but do not belong to the experiment. 
    '''
    for config in initial_domains: 
        if config.name == domain_name:
            return True 
    return False 

def count():
    '''
    Returns the number of active domains
    '''
    return len(initial_domains)


def find_any_domain_by_name(name):
    '''
    Returns the domain configuration by name
    '''
    # Search in active domains
    configs = []
    configs.extend(initial_domains)
    configs.extend(initial_domains)
    for domain in configs:
        if domain.name == name:
            return domain
        
    return None


def get_available_domains_by_size(size, extract=None):
    '''
    Returns a list of domain configurations by size. The extractor function 
    can be used to get only certain attributes of the domain configuration. 
    '''
    elements = []
    for domain in available_domains:
        if domain.size == size:
            if extract is None:
                elements.append(domain)
            else:
                elements.append(extract(domain))
    return elements


def initial_domain_index(domain_name):
    '''
    Returns the index for a domain name in the initial domains
    '''
    for i, mapping in enumerate(initial_domains):
        if mapping.name == domain_name:
            return i
    return None

def available_domain_index(domain_name):
    '''
    Returns the index for a domain name in the available domains
    '''
    for i, mapping in enumerate(available_domains):
        if mapping.name == domain_name:
            return i
    return None
  
  
def dump_json(logger):
    '''
    Dump active domains
    '''
    initial_domain_names = []
    for domain in initial_domains:
        initial_domain_names.append(domain.name)
        
    logger.info('Initial Domains: %s' % json.dumps({'domains' : initial_domain_names}))
    
