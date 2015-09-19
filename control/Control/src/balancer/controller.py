from logs import sonarlog
from twisted.internet import reactor
import conf_nodes
import configuration
import domain_provision
import metrichandler
import model
import msgpump
import scoreboard
import conf_controller as conf

# Setup logging
logger = sonarlog.getLogger('controller')

class Controller(object):
    
    def __init__(self):
        # New message pump with heartbeat to keep it spinning
        def heartbeat(pump):
            pump.callLater(10 * 60, heartbeat, pump)
        self.pump = msgpump.Pump(heartbeat)
        
        # Create scoreboard
        self.scoreboard = scoreboard.Scoreboard(self.pump)

        # Create new domain and node model
        self.model = model.Model(self.pump, self.scoreboard)

        # Create notification handler
        self.handler = metrichandler.MetricHandler(self.model)

        # Setup the re-allocation strategy        
        self.strategy_reallocation = self.__build_stragegy_reallocation()

        # Setup initial placement strategy
        self.strategy_initial_placement = self.__build_strategy_initial_placement()
        
        # Setup the placement strategy
        self.strategy_placement = self.__build_strategy_placement()
        
        
    def __build_strategy_initial_placement(self):
        if conf.STRATEGY_INITIAL_PLACEMENT == 'firstFit':
            import initial_placement_firstfit
            return initial_placement_firstfit.FirstFitPlacement()
        if conf.STRATEGY_INITIAL_PLACEMENT == 'firstFitVector':
            import initial_placement_ffvector
            return initial_placement_ffvector.FFVPlacement()
        if conf.STRATEGY_INITIAL_PLACEMENT == 'dotProduct':
            import initial_placement_dotproduct
            return initial_placement_dotproduct.DotProductPlacement()
        if conf.STRATEGY_INITIAL_PLACEMENT == 'cosine':
            import initial_placement_cosine
            return initial_placement_cosine.CosinePlacement()
        if conf.STRATEGY_INITIAL_PLACEMENT == 'ssapv':
            import initial_placement_ssapv
            return initial_placement_ssapv.SSAPvPlacement()
        if conf.STRATEGY_INITIAL_PLACEMENT == 'cssapv':
            import initial_placement_cssapv
            return initial_placement_cssapv.CSSAPvPlacement()
        if conf.STRATEGY_INITIAL_PLACEMENT == 'dsap':
            if conf.STRATEGY_REALLOCATION != 'dsap':
                print 'FATAL: STRATEGY REALLOCATION needs to be dsap'
            import initial_placement_dsap
            return initial_placement_dsap.DSAPPlacement(self.strategy_reallocation)
        if conf.STRATEGY_INITIAL_PLACEMENT == 'file':
            import initial_placement_file
            return initial_placement_file.FilePlacement()
        if conf.STRATEGY_INITIAL_PLACEMENT == 'round':
            import initial_placement_rr
            return initial_placement_rr.RRPlacement()
        else:
            print 'No initial placement strategy defined'
            return None
        
    def __build_strategy_placement(self):
        if conf.STRATEGY_PLACEMENT == 'static':
            import placement_static
            return placement_static.Static(self.model)
        
        if conf.STRATEGY_PLACEMENT == 'firstNode':
            import placement
            return placement.PlacementBase(self.model)
        
        elif conf.STRATEGY_PLACEMENT == 'random': 
            import placement_random
            return placement_random.RandomPlacement(self.model)
        
        elif conf.STRATEGY_PLACEMENT == 'firstFit':
            import placement_firstfit
            return placement_firstfit.FirstFit(self.model)
        elif conf.STRATEGY_PLACEMENT == 'firstFitDemand':
            import placement_firstfit_demand
            return placement_firstfit_demand.FirstFitDemand(self.model)
        
        elif conf.STRATEGY_PLACEMENT == 'bestFit':
            import placement_bestfit
            return placement_bestfit.BestFit(self.model)
        elif conf.STRATEGY_PLACEMENT == 'bestFitDemand':
            import placement_bestfit_demand
            return placement_bestfit_demand.BestFitDemand(self.model)
        
        elif conf.STRATEGY_PLACEMENT == 'worstFit':
            import placement_worstfit
            return placement_worstfit.WorstFit(self.model)
        elif conf.STRATEGY_PLACEMENT == 'worstFitDemand':
            import placement_worstfit_demand
            return placement_worstfit_demand.WorstFitDemand(self.model)
        
        elif conf.STRATEGY_PLACEMENT == 'nextFit':
            import placement_nextfit
            return placement_nextfit.NextFit(self.model)
        elif conf.STRATEGY_PLACEMENT == 'nextFitDemand':
            import placement_nextfit_demand
            return placement_nextfit_demand.NextFitDemand(self.model)
        
        elif conf.STRATEGY_PLACEMENT == 'dotProduct':
            import placement_dotproduct
            return placement_dotproduct.DotProduct(self.model)
        elif conf.STRATEGY_PLACEMENT == 'dotProductDemand':
            import placement_dotproduct_demand
            return placement_dotproduct_demand.DotProductDemand(self.model)
        
        elif conf.STRATEGY_PLACEMENT == 'l2':
            import placement_L2
            return placement_L2.L2(self.model)
        elif conf.STRATEGY_PLACEMENT == 'l2Demand':
            import placement_L2_demand
            return placement_L2_demand.L2Demand(self.model)
        
        elif conf.STRATEGY_PLACEMENT == 'harmonic':
            import placement_harmonic
            return placement_harmonic.Harmonic(self.model)
        
        elif conf.STRATEGY_PLACEMENT == 'round':
            import placement_round
            return placement_round.RoundRobin(self.model)
        
        else:
            print 'No placement strategy defined'
            return 
    
        
    def __build_stragegy_reallocation(self):
        # Create controller based on the strategy
        if conf.STRATEGY_REALLOCATION == 'tcontrol':
            import strategy_t
            return strategy_t.TTestStrategy(self.scoreboard, self.pump, self.model)
        if conf.STRATEGY_REALLOCATION == 'kmcontrol': 
            import strategy_km
            return strategy_km.Strategy(self.scoreboard, self.pump, self.model)
        elif conf.STRATEGY_REALLOCATION == 'dsap':
            import strategy_dsap
            return strategy_dsap.Strategy(self.scoreboard, self.pump, self.model)
        elif conf.STRATEGY_REALLOCATION == 'dsapp':
            import strategy_dsapp
            return strategy_dsapp.Strategy(self.scoreboard, self.pump, self.model)
        elif conf.STRATEGY_REALLOCATION == 'none':
            import strategy_none
            return strategy_none.Strategy(self.scoreboard, self.pump, self.model)
        else:
            print 'No controller defined'
            return
         
    
    def start(self):
        # Build model - This has to be executed at start not in init
        # The setup routine creates a Controller instance and then
        # calculates and establishes the initial placement.
        #
        # The model initialize method queries the libvirt for the 
        # current domain placement. This placement is established after
        # creating a Controller instance and its __imit__ method call.  
        # 
        # Hence, if the model was initialized in the init method it would 
        # acquire the infrastructure state before the calculated initial 
        # placement was established  
        if not self.__model_initialize():
            print 'Exiting because of error in initial placement'
            return
        
        # Exit after intial placement
        if conf.EXIT_AFTER_INITIAL_PLACEMENT:
            return

        # Production mode connects with sonar        
        if configuration.PRODUCTION:
            print 'RUNNING IN PRODUCTION MODE'
            if conf.is_start_reallocation():
                # Connect with Sonar for metric readings
                import connector
                connector.connect_sonar(self.model, self.handler)
                
                # Start reallocation strategy 
                self.strategy_reallocation.dump()
                self.strategy_reallocation.start()
                
            if conf.is_start_placement():
                # Create domain provisioner (the concrete one in this case)
                pv = domain_provision.ConcreteProvisioning(self.model, self.pump, self.strategy_placement)
                
                # Start infrastructure service with a reference to the provisioner 
                import infrastructure_service
                infrastructure_service.start(pv)
        else:
            print 'RUNNING IN SIMULATION MODE'
            
            # Start load driver that simulations Sonar
            import driver_load
            driver_load = driver_load.Driver(self.scoreboard, self.pump, 
                                             self.model, self.handler,
                                             not conf.is_start_placement())
            driver_load.start()
            
            if conf.is_start_reallocation():
                print 'Starting reallocation strategy...'
                
                # Start reallocation strategy 
                self.strategy_reallocation.dump()
                self.strategy_reallocation.start()
                
            if conf.is_start_placement():
                print 'Starting placement strategy...'
                
                # Create domain provisioner (the model one in this case)
                pv = domain_provision.Provisioning(self.model, self.pump, self.strategy_placement)
                
                # Start domain driver that simulates Rain domain provisioning 
                import driver_domains
                driver_domains = driver_domains.Driver(self.pump, self.scoreboard, pv)
                driver_domains.start()
            
            # Update scoreboard
            self.scoreboard.start()
            
    def __model_initialize(self):
        # Run configuration
        if configuration.PRODUCTION: 
            # Load current infrastructure state into model
            self.model.model_from_current_allocation()
        else:
            # Calculate initial placement
            migrations, servers = self.strategy_initial_placement.execute()
            
            # Update scoreboard
            self.scoreboard.set_initial_placement_duration()
            
            # Check for valid initial placement 
            if migrations is None and servers is None:
                print 'Invalid initial placement'
                self.scoreboard.add_active_info(conf_nodes.NODES, 0)
                return False
            else:
                # Get execution duration
                self.model.model_from_migrations(migrations)
        
        # Dump model
        self.model.dump()
        
        # Update empty counts
        self.model.log_active_server_info(); 
                
        # Initialize all control variables
        self.model.reset() 
        
        return True
        
def start():
    ###########################################################
    ### START CONTROLLER ######################################
    ###########################################################
    # Create a new controller instance and start the controller
    controller = Controller()
    controller.start()
        
    ###########################################################
    # Start reactor (is stopped in the message pump)
    if not conf.EXIT_AFTER_INITIAL_PLACEMENT:
        print 'Running reactor...'
        reactor.run()
    ###########################################################
    
    # Check if exited with an error
    if controller.pump.exit_on_error:
        raise controller.pump.exit_on_error
    
    # After the simulation get the scoreboard results
    print 'Reading scoreboard...' 
    controller.scoreboard.dump()
    names, res = controller.scoreboard.get_result_line()
    
    # Return results only 
    return names, res
            
            
if __name__ == '__main__':
    start() 
