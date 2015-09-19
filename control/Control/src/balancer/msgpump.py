from twisted.internet import reactor
import configuration
import time
import sys
import traceback

class Entry:
    def __init__(self, cb_time, handler, *args):
        self.cb_time = float(cb_time)
        self.handler = handler
        self.args = args
        
    def scheduledCall(self):
        self.handler(*self.args)
    
    
class Pump(object):
    def __init__(self, initial_handler, *handler_args):
        # Thread init method
        super(Pump, self).__init__()
        
        self.handlers = []
        self.production = configuration.PRODUCTION
        self.start_time = time.time() if self.production else 0
        self.scheduledCall = None
        self.callLater(0, initial_handler, self, *handler_args)
        
        # If an error occurs its stored here
        self.exit_on_error = None
        
        
    def callLater(self, delay, handler, *data):
        if self.production:
            # Production mode just uses reactor timing
            reactor.callLater(delay, handler, *data)
        else:
            # Simulation needs to calculate simulated timings
            cb_time = self.sim_time() + delay
            entry = Entry(cb_time, handler, *data)
            self.handlers.append(entry)
            self.handlers.sort(key=lambda a: a.cb_time)
            if self.scheduledCall is None: 
                self.scheduledCall = reactor.callLater(0, self.__next_entry)
        
        
    def __next_entry(self):
        entry = self.handlers[0]
        self.handlers.remove(entry)
        self.start_time = entry.cb_time
        
        try:
            entry.scheduledCall()
        except:
            traceback.print_exc()
            self.exit_on_error = sys.exc_info()[0]
            reactor.crash()
            return        
        
        # Schedule next scheduledCall
        if self.handlers:
            self.scheduledCall = reactor.callLater(0, self.__next_entry)
        else:
            self.scheduledCall = None
        
        
    def stop(self):
        # Stop the twisted reactor
        reactor.stop()
        
    def sim_time(self):
        if self.production: 
            return time.time()
    
        return self.start_time
       
            
