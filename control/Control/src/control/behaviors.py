from behaviorTree import behaviorTree as btree
from control import drones, hosts, base
from logs import sonarlog
from rain import RainService
from thrift.protocol import TBinaryProtocol
from thrift.transport import TTwisted
from twisted.internet import defer, reactor
from twisted.internet.protocol import ClientCreator
from virtual import util
import conf_schedule
import conf_domains

# Setup logging
logger = sonarlog.getLogger('behaviors')

class ShutdownAllDomains(btree.Action):
    '''
    Shutdown all running VMs in the infrastructure
    '''
    def action(self):
        util.shutdownall()
        return True
    
    
class StartDatabase(btree.Action):
    '''
    Start MySQL database on all hosts of type 'database'.
    '''
    def action(self):
        print 'Starting MySQL database...'
        logger.info('starting database')
        
        try:
            # List of deferred objects
            dlist = []
            
            # Trigger drone on all domains
            for target in self.blackboard.hosts.get_hosts('database'):
                print '   * initializing database on host %s' % (target)
                d = base.launch(self.blackboard.hosts, self.blackboard.client_list, target, 'spec_dbload', wait=True)
                dlist.append(d)
            
            # Wait for all drones to finish and set phase
            d = defer.Deferred()
            dl = defer.DeferredList(dlist)
            dl.addCallback(self.ok, d)
            return d
        
        except Exception, e:
            # Log error and exit this action with a failure
            logger.error(e)
            return False
        
    def ok(self, status, d):
        # Exit this action with success
        d.callback(True)

        
class StartGlassfishTree(object):
    '''
    This behavior tree is executed by IaaS service to initialize
    new domains. 
    '''
    
    def __init__(self, domain):
        # Target host
        self.domain = domain
    
    def launch(self):
        # Blackboard
        bb = btree.BlackBoard()
        bb.hosts = hosts.RelayHosts()
        bb.hosts.clear()
        
        # Add domain to hosts
        bb.hosts.add_host(self.domain, 'target')
        bb.hosts.add_host(self.domain, 'database')
        
        # Start behavior tree
        start = btree.Sequence(bb)
        
        # Connect with domain
        start.add(ConnectRelay())
        
        # Configure and start MySQL and Glassfish
        start.add(ConfigureGlassfish())
        start.add(StartDatabase())
        start.add(StartGlassfish())
        
        # Launch behavior tree with deferred
        d = defer.Deferred()
        d_bt = start.execute()
        d_bt.addCallback(lambda _: d.callback(True))
        return d

        
class ConnectRelay(btree.Action):
    def action(self):
        # Create drones
        drones.build_all_drones()
        
        # Create deferred and connect
        d = defer.Deferred()
        self.connect(d)
        return d
        
    def connect(self, d):
        # Connect with all drone relays
        hosts_map = self.blackboard.hosts.get_hosts_list()
        dlist = base.connect(hosts_map)
            
        # Wait for all connections
        logger.info('connecting with relay services')
        wait = defer.DeferredList(dlist, fireOnOneErrback=True)
        wait.addCallback(self.connected, d)
        wait.addErrback(self.error_retry, d)
        
    def error_retry(self, failure, d):
        print 'Failure while connecting with Relays'
        print 'Retrying...'
        import time
        time.sleep(30)
        self.connect(d)
        
    def connected(self, client_list, d):
        print d
        # Add client list to blackboard
        self.blackboard.client_list = client_list
        d.callback(True)
        
        
class SyncMarker(btree.Action):
    '''
    Write message into Sonar at SYNC priority
    '''
    def __init__(self, message):
        self.message = message
        
    def action(self):
        logger.log(sonarlog.SYNC, self.message)
        return True


class AllocateDomains(btree.Action):
    '''
    Allocate domains according to initial allocation
    '''
    def __init__(self, controller):
        self.controller = controller 
        
    def action(self):
        logger.info('Setting up initial allocation')
        
        # Dump initial domains
        conf_domains.dump_json(logger)
        
        # Establish initial allocation
        import allocate_domains
        allocate_domains.allocate_domains(True, self.controller)
        
        d = defer.Deferred()
        reactor.callLater(0, d.callback, True)
        return d


class StopGlassfishRain(btree.Action):
    '''
    Stop Glassfish server and Rain load drivers on all 'target' and 'load' hosts
    '''
    
    def action(self):
        print "stopping glassfish and rain DRIVER_NODES..."
        logger.info('stopping glassfish and rain DRIVER_NODES')
        
        # List of deferred objects
        dlist = []
        
        print('stopping glassfish on targets: '),
        for target in self.blackboard.hosts.get_hosts('target'):
            print target 
            d = base.launch(self.blackboard.hosts, self.blackboard.client_list, target, 'glassfish_stop')
            dlist.append(d)
        print ''
        
        print('stopping rain on targets: '),
        for target in self.blackboard.hosts.get_hosts('load'):
            print target
            d = base.launch(self.blackboard.hosts, self.blackboard.client_list, target, 'rain_stop')
            dlist.append(d)
        print ''
        
        # Wait for all drones to terminate
        dl = defer.DeferredList(dlist)
        d = defer.Deferred()
        dl.addCallback(self.ok, d)
        return d
        
    def ok(self, status, d):
        d.callback(True)
    
   
class StartController(btree.Action):
    '''
    Start controller that is given by reference
    '''
    
    def __init__(self, controller):
        super(StartController, self)
        self.controller = controller
    
    def action(self):
        print '### STARTING CONTROLLER ######################'
        logger.info('starting Controller')
        
        # Controller uses the BTree ractor that is already running
        self.controller.start()
        
        # Deferred for callback
        self.d = defer.Deferred()
        
        logger.info('Sleeping while controller is starting')
        reactor.callLater(10, self.controller_launched)
        
        # Return deferred
        return self.d

    def controller_launched(self):
        logger.info('controller launched')
        logger.log(sonarlog.SYNC, 'end of startup sequence')
        
        # Call deferred
        self.d.callback(True)


class TriggerRain(btree.Action):
    '''
    Trigger Rain drivers to release load. Used to synchronize multiple
    Rain drivers.
    '''
    
    def action(self):
        print 'Releasing Rain load...'
        logger.log(sonarlog.SYNC, 'releasing load on rain DRIVER_NODES')
    
        # Deferred list
        dlist = []
        
        # For all Rain hosts
        for client in self.blackboard.rain_clients:
            print '   * releasing %s' % (client)
            logger.info('releasing %s' % client)
            
            # Call start benchmark
            d = client.startBenchmark(long(base.millis()))
            dlist.append(d)

        # Wait for all release calls to finish
        dl = defer.DeferredList(dlist)
        self.da = defer.Deferred()
        dl.addCallback(self.triggered)
        dl.addErrback(self.error)
        return self.da
    
    def error(self, err):
        # Error while releasing rain workload
        logger.error('Could not release RAIN drivers - %s' % err)
        print 'FATAL: could not release RAIN drivers - %s' % err
        
        # Action failed
        self.da.callback(False)
    
    def triggered(self, rt):
        # Log that all Rain drivers are released
        logger.log(sonarlog.SYNC, 'RAIN drivers launched')
        logger.info('RAIN drivers launched')
        
        # Exit this action successfully
        self.da.callback(True)
    
   
class ConnectRain(btree.Action):
    '''
    Connect with all Rain drivers (Rain services not Relay!)  
    '''
    
    def action(self, d=None):
        print 'Connecting with Rain DRIVER_NODES...'
        logger.info('connecting with rain DRIVER_NODES')
        
        # Deferred list
        dlist = []
        
        # For all load drivers
        for driver in self.blackboard.hosts.get_hosts('load'):
            print '   * connecting %s' % (driver)
            
            # Create a new client to Rain
            creator = ClientCreator(reactor,
                                  TTwisted.ThriftClientProtocol,
                                  RainService.Client,
                                  TBinaryProtocol.TBinaryProtocolFactory(),
                                  ).connectTCP(driver, 7852, timeout=120)
            dlist.append(creator)
          
        # Create new deferred object if non exists
        if d == None:
            d = defer.Deferred()
              
        # Wait for all connections
        dl = defer.DeferredList(dlist)                  
        dl.addCallback(self.ok, d)
        dl.addErrback(self.err, d)
        return d
        
        
    def ok(self, rain_clients, d):
        # Rain connection successfully
        _rain_clients = []
        for client in rain_clients:
            # Get client object
            _rain_clients.append(client[1].client)
            
            # Check if client object is valid
            if client[0] == False:
                logger.warn('Could not connect with all Rain services')
                print 'FATAL: Could not connect with all Rain serivces'
                
                # Action failed
                d.callback(False)
                            
        # Add Rain clients to the blackboard        
        self.blackboard.rain_clients = _rain_clients
        d.callback(True)
        
        
    def err(self, status, d):
        print 'Connection with Rain service failed'
        print 'Known reasons: '
        print '   * Rain startup process took long which caused Twisted to time out'
        print '   * System was started the first time - Glassfish&SpecJ did not find the database initialized'
        print '   * Rain crashed - see rain.log on the load servers'
        logger.debug('Connection with Rain service failed')
        
        # Retry connection
        reactor.callLater(10, self.action, d)
    
    
class StartRain(btree.Action):
    '''
    Start Rain workload driver programs (this will not trigger load)
    '''
    
    def action(self):
        print 'Starting rain DRIVER_NODES...'
        logger.info('starting rain DRIVER_NODES')
        
        # Deferred list
        dlist = []
    
        # Get all driver hosts
        DRIVER_NODES = self.blackboard.hosts.get_hosts('load')
        driver_count = len(DRIVER_NODES)
        
        # Load schedules as JSON
        from schedule import schedule_builder
        json_schedules = schedule_builder.load_entries(conf_schedule.SCHEDULE_ID)
        
        # For each Rain driver
        for i in range(0, driver_count):
            # Driver host 
            driver = DRIVER_NODES[i]
            
            # Create launch drone with appropriate schedule
            drones.prepare_drone('rain_start', 'rain.config.specj.json',
                                  schedule=json_schedules[i])
            drones.create_drone('rain_start')
            
            # Launch this drone
            logger.info('Launching Rain: %s' % driver)
            d = base.wait_for_message(self.blackboard.hosts, self.blackboard.client_list, driver, 'rain_start', 'Waiting for start signal...', '/opt/rain/rain.log')
            dlist.append(d)
        
        
        # Wait for all Rain drivers to start
        dl = defer.DeferredList(dlist)
        d = defer.Deferred()
        dl.addCallback(self.ok, d)
        return d
        
    def ok(self, status, d):
        d.callback(True)

            
class StartGlassfish(btree.Action):
    '''
    Start Glassfish server
    '''
    
    def action(self):
        print 'Starting glassfish...'
        logger.info('starting glassfish')
        
        try:
            # Deferred list
            dlist = []
            
            # For all target domains
            for target in self.blackboard.hosts.get_hosts('target'):
                print '   * starting glassfish on target %s' % (target) 
                d = base.launch(self.blackboard.hosts, self.blackboard.client_list, target, 'glassfish_start', wait=False)
                dlist.append(d)
                
                print '   * waiting for glassfish on target %s' % (target)
                d = base.poll_for_message(self.blackboard.hosts, self.blackboard.client_list, target, 'glassfish_wait', 'Name: domain1 Status: Running')
                dlist.append(d)
            
            # Wait for all drones to finish and set phase
            d = defer.Deferred()
            dl = defer.DeferredList(dlist)
            dl.addCallback(self.ok, d)
            return d
            
        except Exception, e:
            print e
            logger.error(e)
            return False
        
    def ok(self, status, d):
        print 'sleeping after glassfish launch'
        reactor.callLater(10, d.callback, True)
        

class ConfigureGlassfish(btree.Action):
    '''
    Configure Glassfish server
    '''
    
    def action(self):
        logger.info('Rerconfiguring glassfish')
        try:
            # Deferred list
            dlist = []
            
            # Run drone on all target domains
            for target in self.blackboard.hosts.get_hosts('target'):
                print '   * configuring glassfish on target %s' % (target)
                
                # mysql_name = target.replace('glassfish', 'mysql')
                mysql_name = 'localhost'
                print '     using mysql name: %s' % (mysql_name)
                drones.prepare_drone('glassfish_configure', 'domain.xml', mysql_server=mysql_name, targetHostName=target)
                drones.create_drone('glassfish_configure')
                
                d = base.launch(self.blackboard.hosts, self.blackboard.client_list, target, 'glassfish_configure', wait=True)
                dlist.append(d)
            
            # Wait for all drones to finish and set phase
            dl = defer.DeferredList(dlist)
            d = defer.Deferred()
            dl.addCallback(self.ok, d)
            return d
            
        except Exception, e:
            print 'FATAL: Error while configuring glassfish'
            print e
            return False
            
    def ok(self, status, d):
        d.callback(True)
