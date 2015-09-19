from logs import sonarlog
from workload.timeutil import *  # @UnusedWildImport
import conf_domains
import conf_nodes
import initial_placement

# Setup logging
logger = sonarlog.getLogger('initial_placement')
   
class RRPlacement(initial_placement.InitialPlacement):
    def execute(self):
        # Execute super code
        super(RRPlacement, self).execute()
        
        print 'Distributing domains over all servers ...'
            
        # Logging
        logger.info('Placement strategy: Round Robin')
        logger.info('Required servers: %i' % conf_nodes.NODE_COUNT)
        
        
        migrations = []
        assignment = {}
        
        node_index = 0
        service_index = 0
        for maps in conf_domains.initial_domains:
            migrations.append((maps.name, node_index))
            node_index = (node_index + 1) % conf_nodes.NODE_COUNT
            
            assignment[service_index] = node_index
            service_index += 1
        
        print 'Assignment: %s' % assignment
        logger.info('Assignment: %s' % assignment)
        print 'Migrations: %s' % migrations
        logger.info('Migrations: %s' % migrations)
        
        return migrations, self._count_active_servers(assignment)
 
