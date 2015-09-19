from control import drones
from relay import RelayService
from string import Template
from thrift.protocol import TBinaryProtocol
from thrift.transport import TTwisted
from twisted.internet.protocol import ClientCreator
from twisted.internet import reactor
import configuration as config
import sys
import time
import traceback

###############################################
# ## CONFIG                                  ##
###############################################
DEFAULT_SETUP_IP = 'vmt'
###############################################

class DomainConfiguration(object):

    def __init__(self, connections, setup_server, finish_handler):
        self.setup_server = setup_server
        self.connections = connections
        self.finish_handler = finish_handler

    def _domain_configuration_finished(self, clone_entry):
        self.finish_handler(clone_entry)

    def _restart_domain(self, ret, clone_entry, relay_conn):
        '''
        Waits until a domain is shut down. After a timeout the domain 
        gets killed.
        '''
        print 'Update executed'
        
        # Sometimes VMs stall while shutting down
        # Wait until VM is dead for max. 60 seconds then kill it
        conn = self.connections[self.setup_server]
        new_domain = conn.lookupByName(clone_entry.target)
        state = 0
        wait_time = 0
        while state != 5 and wait_time < 60:
            print state
            time.sleep(5)
            wait_time += 5
            state = new_domain.state(0)[0]
            
        if wait_time >= 60:
            print 'Killing domain %s' % (clone_entry.target)
            new_domain.destroy()
        
        # Finish
        self._domain_configuration_finished(clone_entry)
    
    
    def _launch_drone(self, ret, clone_entry):
        '''
         Launches the drone on the connection in the parameter
        '''
        
        print 'Launching drone (connection established)'
        
        try:
            # Read configuration template
            config = open(drones.DRONE_DIR + '/setup_vm/main_template.sh', 'r')
            data = config.readlines()
            data = ''.join(data)
            config.close()
            
            # Templating engine
            templ = Template(data)
            d = dict(hostname=clone_entry.target)
            templ = templ.substitute(d)
                
            # Write result configuration
            config = open(drones.DRONE_DIR + '/setup_vm/main.sh', 'w')
            config.writelines(templ)
            config.close()
        except Exception, e:
            traceback.print_exc(file=sys.stdout)
            return
       
        # Rebuild drones
        drones.main()
        
        # Load and execute drone
        print 'Waiting for drone...'
        drone = drones.load_drone('setup_vm')
        ret.launchNoWait(drone.data, drone.name).addCallback(self._restart_domain, clone_entry, ret)
            
    
    def _configuration_error(self, err, clone_entry):
        '''
        Error handler if the connection with the new domain fails 
        configuraiont is retried
        '''
        reactor.callLater(3, self.configure_domain, clone_entry)
        
    
    def configure_domain(self, clone_entry):
        '''
        Reconfigures a domain by running the reconfiguration drone 
        '''
        
        print 'Connecting with new domain.'
        creator = ClientCreator(reactor,
                              TTwisted.ThriftClientProtocol,
                              RelayService.Client,
                              TBinaryProtocol.TBinaryProtocolFactory(),
                              ).connectTCP(DEFAULT_SETUP_IP, config.RELAY_PORT, timeout=10)
        creator.addCallback(lambda conn: conn.client)
        creator.addCallback(self._launch_drone, clone_entry)
        creator.addErrback(self._configuration_error, clone_entry)
    

