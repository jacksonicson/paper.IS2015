import clone
import threading
from twisted.internet import reactor
import util
import conf_domains

def _start_reactor():
    # Reactor run in its own thread
    class ThreadWrapper(threading.Thread):
        def run(self):
            reactor.run(installSignalHandlers=0)
            
    thr = ThreadWrapper()
    thr.start()
    return thr


def main():
    # Start reactor
    thr = _start_reactor()
    
    # stop all
    util.shutdownall()
    
    # Establish libvirt connections and start reactor
    clone.init()
    
    # Remove everything in delete list
    for to_delete in conf_domains.to_delete_domains(): 
        clone.delete(to_delete)
    
    # Get domain specs to clone
    to_clone_domains = conf_domains.to_clone_domains()
    
    # Schedule all clone entries
    index = 0
    for to_clone in to_clone_domains:
        exitHere = to_clone == to_clone_domains[-1]
        if exitHere: 
            exitHere = lambda: reactor.stop()
        else:
            exitHere = None
            
        clone.clone(to_clone.clone_source, to_clone.name, index, exitHere, False)
        index += 1
    
    # Wait for exit
    print 'Waiting for clone process...'
    thr.join()
    print 'Exiting'
    

if __name__ == '__main__':
    main()
