import conf_domainsize as domainsize

'''
List of all hosts/nodes in the infrastructure. It is assumed that
all nodes have the same hardware specification. 
'''

######################
# CONFIGURATION     ##
######################
NODE_COUNT = 6  # Number of available nodes
NODE_CPU_CORES = 4.0  # CPU cores for each node
NODE_MEM = 15 * 1024  # MByte (available memory of the node estimated)
NODES = []  # Name of all available nodes
UTIL = 100 # 100% CPU utilization value
######################

# Fill node list
for i in xrange(NODE_COUNT):
    NODES.append('srv%i' % i)

def get_node_name(index):
    return NODES[index]

def index_of(node_name):
    for i, node in enumerate(NODES):
        if node == node_name:
            return i
    return None

def to_node_load(domain_load, domain_size):
    domain_cores = domainsize.get_domain_spec(domain_size).phy_cpu_cores()
    return float(domain_load * domain_cores) / float(NODE_CPU_CORES)

def to_node_load_ts(demand, domain_size):
    for i in xrange(len(demand)):
        demand[i] = to_node_load(demand[i], domain_size)
    return demand

def dump(logger):
    logger.info('NODES = %s' % NODES)
    logger.info('NODE_MEM = %i' % NODE_MEM)
    logger.info('NODE_CPU_CORES = %i' % NODE_CPU_CORES)
    
