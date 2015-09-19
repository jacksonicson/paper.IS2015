'''
All Domains (VMs) are configure_domain on the srv0 system! This is the initialization system. If a Domain is moved 
to another system it's configuration has to be created on the target system. 
'''

from control import drones
from lxml import etree
from relay import RelayService
from thrift.protocol import TBinaryProtocol
from thrift.transport import TTwisted
from twisted.internet import defer, reactor, threads as tthread
from twisted.internet.defer import DeferredQueue
from twisted.internet.protocol import ClientCreator
import configuration as config
import configure
import conf_nodes
import time
import util

###############################################
# CONFIG                                     ##
###############################################
STORAGE_POOLS = ['s0a0', 's0a1', 's1a0']
SETUP_SERVER = 'srv0'
###############################################

# Distribute images across all pools, pool_index gives the pool where the next VM will be created
pool_index = long(time.time()) % len(STORAGE_POOLS)

# Clone queue
queue = DeferredQueue()

# Cloned domains that are up and running 
active_list = []
 
  
class CloneJob(object):
    '''
    Describes one clone entry in the clone queue
    '''
    
    def __init__(self, source, target, domain_id, exitClone=None, launch=True):
        self.source = source
        self.target = target
        self.domain_id = domain_id
        self.exitClone = exitClone
        self.launch = launch


def _domain_configuration_finished(clone_entry):
    '''
    Is called as soon as a domain is fully configured. 
    '''
    
    # Check if this job has the exit flag set
    if clone_entry.exitClone is not None:
        clone_entry.exitClone()
        return
    
    # Launch domain flag
    if clone_entry.launch:
        print 'Launching domain again...'
        conn = util.connections[SETUP_SERVER]
        new_domain = conn.lookupByName(clone_entry.target)
        new_domain.create()
        active_list.append(clone_entry.target)
    
    print 'Domain cloned successfully'
    _wait_for_next_entry()


def _mac_by_id(domain_id):
    '''
    Is used to give target0 always the same MAC for each clone_domain process. 
    If random MACs are used the DNS server registers multiply mappings and cannot
    resolve the names properly. 
    '''
    
    base = '52:54:00'
    # generate 3 0xNN blocks
    for _ in xrange(3):
        rand = domain_id
        value = hex(rand)[2:]
        if len(value) == 1:
            value = '0' + value
        base += ':' + value

    print 'By ID generated MAC: %s' % base    
    return base

def _clone_domain(connections, source, target, domain_id):
    # Connection for srv0
    conn = connections[SETUP_SERVER]
    
    # Connect with all known storage pools
    print 'Connecting with storage pools...'
    pools = []
    for name in STORAGE_POOLS:
        pool = conn.storagePoolLookupByName(name)
        pools.append(pool)
    
    # Delete target if it exists
    print 'Remove old domain description...'
    for host in conf_nodes.NODES:
        try:
            dom_target = connections[host].lookupByName(target)
            if dom_target != None:
                ret = dom_target.undefine()
                print 'Domain removed: %i' % ret 
        except:
            pass
        
        
    print 'Removing old volume...'
    for delpool in pools:
        try:
            volume_target = delpool.storageVolLookupByName(target + ".qcow")
            if volume_target != None:
                ret = volume_target.delete(0)
                print 'Volume removed: %i' % ret
        except:
            pass

    
    # Select pool to clone to
    global pool_index
    print 'Cloning to dst_pool: %i - %s' % (pool_index, STORAGE_POOLS[pool_index])
    dst_pool = STORAGE_POOLS[pool_index]
    dst_pool_pool = pools[pool_index]
    pool_index = (pool_index + 1) % len(STORAGE_POOLS)
    
    # Load source domain
    source_domain = conn.lookupByName(source)
    
    # Get source pool
    xml_dom_desc = source_domain.XMLDesc(0)
    xml_tree = etree.fromstring(xml_dom_desc)
    name = xml_tree.xpath('/domain/devices/disk/source')
    name = name[0].get('file')
    name = name[5:9]
    src_pool_index = STORAGE_POOLS.index(name)
    src_pool = pools[src_pool_index]
    
    # Get source volume
    volume = src_pool.storageVolLookupByName(source + ".qcow")

    # Reconfigure the volume description    
    xml_vol_desc = volume.XMLDesc(0)
    xml_tree = etree.fromstring(xml_vol_desc)
    name = xml_tree.xpath('/volume/name')[0]
    name.text = target + '.qcow'
    key = xml_tree.xpath('/volume/key')[0]
    key.text = '/mnt/' + dst_pool + '/' + target + '.qcow'
    path = xml_tree.xpath('/volume/target/path')[0]
    path.text = '/mnt/' + dst_pool + '/' + target + '.qcow'
    xml_vol_desc = etree.tostring(xml_tree)
    
    # Create a new volume
    print 'Cloning volume...'
    dst_pool_pool.createXMLFrom(xml_vol_desc, volume, 0)
    
    # Reconfigure the domain description
    xml_domain_desc = source_domain.XMLDesc(0)
    # print xml_domain_desc # print original domain description
    
    xml_tree = etree.fromstring(xml_domain_desc)
    name = xml_tree.xpath('/domain/name')[0]
    name.text = target
    uuid = xml_tree.xpath('/domain/uuid')[0]
    uuid.getparent().remove(uuid)
    source = xml_tree.xpath('/domain/devices/disk/source')[0]
    source.set('file', '/mnt/' + dst_pool + '/' + target + '.qcow')
    mac = xml_tree.xpath('/domain/devices/interface/mac')[0]
    mac.attrib['address'] = _mac_by_id(domain_id)
    xml_domain_desc = etree.tostring(xml_tree)
    # print xml_domain_desc # print final domain description
    
    # Create a new Domain
    print 'Creating domain...'
    new_domain = conn.defineXML(xml_domain_desc)
    
    # Launch domain
    print 'Launching Domain...'
    new_domain.create()
 
 
def _delete_domain_data(to_del):
    # Connection for srv0
    conn = util.connections[SETUP_SERVER]
    
    # Connect with all known storage pools
    print 'Connecting with storage pools...'
    pools = []
    for name in STORAGE_POOLS:
        pool = conn.storagePoolLookupByName(name)
        pools.append(pool)
    
    # Delete target if it exists
    print 'Remove old domain description...'
    for host in conf_nodes.NODES:
        try:
            dom_target = util.connections[host].lookupByName(to_del)
            if dom_target != None:
                ret = dom_target.undefine()
                print 'Domain removed: %i' % ret 
        except:
            pass
        
    print 'Removing old volume...'
    for delpool in pools:
        try:
            volume_target = delpool.storageVolLookupByName(to_del + ".qcow")
            if volume_target != None:
                ret = volume_target.delete(0)
                print 'Volume removed: %i' % ret
        except:
            pass
 
 
def _delete_domain(to_del):
    # Destroy the VM
    for host in conf_nodes.NODES:
        # Go over all domains on the node 
        conn = util.connections[host]
        ids = conn.listDomainsID()
        for domain_id in ids:
            domain = conn.lookupByID(domain_id)
            name = domain.name
            if name == to_del:
                print 'destroying domain %s' % to_del
                domain.destroy()
                return
            
    # Delete domain instance and storage volume
    _delete_domain_data(to_del)
    
    # Remove it from the active list
    if to_del in active_list:
        index = active_list.index(to_del)
        del active_list[index]
 
 
def _configure_domain(clone_entry):
    conf = configure.DomainConfiguration(util.connections, SETUP_SERVER, _domain_configuration_finished)
    conf.configure_domain(clone_entry)
 

def _wait_for_next_entry():
    '''
    Waits until a new clone entry occurs in the list
    ''' 
    
    def _process_clone_entry(entry):
        print 'processing next clone entry in queue...'
    
        # Clone the domain in a separate thread
        # This will not block the reactor thread! 
        d = tthread.deferToThread(_clone_domain, util.connections, entry.source, entry.target, entry.domain_id)
        
        # Configure domain after cloning it
        d.addCallback(lambda res: _configure_domain(entry))
    
    # Register callback handler again to handle the next entry
    # in the clone queue
    d = queue.get() 
    d.addCallback(_process_clone_entry)
 

def _try_connecting(domain, defer):
    '''
    Connects with the domain's Relay service. If it does not respond in 5 seconds
    it is assumed that the domain is not available right now 
    '''
    creator = ClientCreator(reactor,
                          TTwisted.ThriftClientProtocol,
                          RelayService.Client,
                          TBinaryProtocol.TBinaryProtocolFactory(),
                          ).connectTCP(domain, config.RELAY_PORT, timeout=10)
    creator.addCallback(lambda conn: conn.client)
    
    creator.addCallback(lambda value: defer.callback(True))
    creator.addErrback(lambda value: defer.callback(False))
   
   
def init():
    # Build drones
    drones.main()
    
    # Start clone queue listener
    _wait_for_next_entry()

 
def clone(source, target, count, exitClone=None, launch=True):
    # Create a new entry that describes the clone
    entry = CloneJob(source, target, count, exitClone, launch)
    
    # Add the entry to the queue (thread safe) 
    reactor.callFromThread(queue.put, entry)

   
def delete(domain):
    reactor.callFromThread(_delete_domain, domain)

   
def try_connecting(domain, cloned=True):
    if cloned and domain not in active_list:
        return False
     
    d = defer.Deferred()
    _try_connecting(domain, d)
    return d
   



