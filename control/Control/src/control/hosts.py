'''
Manages a list of hosts with types. This data structure is required to
trigger actions by the host type in the control scripts. 
'''

class RelayHosts(object):
    
    def __init__(self):
        self.hosts_map = {}
        self.hosts = []

    def add_host(self, hostname, drone_type):
        if drone_type not in self.hosts_map:
            self.hosts_map[drone_type] = []
            
        self.hosts_map[drone_type].append(hostname)
        
        if hostname not in self.hosts:
            self.hosts.append(hostname)
    
    def clear(self):
        self.hosts_map.clear()
        del self.hosts[:]
    
    def get_index(self, host):
        index = self.hosts.index(host)
        return index
    
    def get_hosts(self, drone_type):
        if not self.hosts_map.has_key(drone_type):
            return []
        
        hostnames = self.hosts_map[drone_type]
        result = []
        for host in hostnames:
            result.append(host)
            
        return result
    
    def get_hosts_list(self):
        return self.hosts
