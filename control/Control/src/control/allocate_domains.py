from balancer import controller
from logs import sonarlog
from virtual import allocation as virt
import json
import time

# Setup logging
logger = sonarlog.getLogger('initial_placement')

def allocate_domains(migrate, controller):
    # Calculate initial placement
    migrations, active_nodes = controller.strategy_initial_placement.execute() 
    print 'Initial node demand: %i' % active_nodes[0]

    # Log initial placement settings    
    logger.info('Initial Active Servers: %s' % json.dumps({'count' : active_nodes[0],
                                                           'servers' : active_nodes[1],
                                                           'timestamp' : time.time()}))
    
    # Trigger migrations
    if migrate:
        print 'Establishing new allocation by migration...'
        virt.migrateAllocation(migrations)


if __name__ == '__main__':
    controller = controller.Controller()
    allocate_domains(True, controller)

