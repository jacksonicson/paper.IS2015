import conf_nodes
import libvirt

# Established connections
connections = {}

def connect(node):
    # Check if connection exists
    if node in connections:
        return connections[node]
    
    try:
        print 'connecting with %s' % node
        conn_str = "qemu+ssh://root@%s/system" % (node)
        
        print 'connecting with %s' % (conn_str)
        conn = libvirt.open(conn_str)
        
        # Add connection to list
        connections[node] = conn
        return conn
    except:
        print 'failed connecting with node %s' % node
        return None


def get_hostname(connection):
    for name in connections:
        if connections[name] == connection:
            return name
    return None 


def connect_all():
    print 'Connecting with all libvirt services...'
    for node in conf_nodes.NODES:
        connect(node) 


def close_all():
    print 'Closing libvirtd connections...'
    for connection in connections.values():
        connection.close()
    
    
def find_domain(domain_name):
    last = None, None
    for lv_connection in connections.values():
        try:
            # Check if domain is running on current connection
            lv_domain = lv_connection.lookupByName(domain_name)
            
            # Last valid entry
            last = lv_domain, lv_connection
            
            # Check if domain is active and return it if so
            state = lv_domain.state(0)[0]
            if state == 1:
                return lv_domain, lv_connection
        except:
            pass
        
    # Return last known position of domain
    return last
    
    
def shutdownall():
    # Go over all nodes
    for host in conf_nodes.NODES:
        # Go over all domains on the node 
        lv_connection = connections[host]
        lv_ids = lv_connection.listDomainsID()
        for lv_domain_id in lv_ids:
            # Get domain for ID 
            domain = lv_connection.lookupByID(lv_domain_id)
            
            # Shutdown domain
            print '   Shutting down: %s' % (domain.name())
            domain.destroy()
    
    
# Connect with all servers
connect_all()    
    