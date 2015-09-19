'''
Provides a service to control the infrastructure like an
IaaS service 
'''

from control import behaviors
from iaas import Infrastructure
from thrift.protocol import TBinaryProtocol
from thrift.transport import TTwisted
from twisted.internet import reactor
from virtual import clone, domain_manager
from zope.interface import implements
import configuration as config

class Handler(object):
    implements(Infrastructure.Iface)
    
    '''
    IaaS service handler is based on the following modules:
    - domain provisioner
    - behavior trees
    - domain manager 
    '''
    
    def __init__(self, provision):
        # Domain provisioner handler
        self.provision = provision
    
    def allocateDomain(self, loadIndex, domain_size):
        d = self.provision.handout(loadIndex, domain_size)
        return d
    
    def deleteDomain(self, domain_name):
        status = self.provision.handin(domain_name)
        return status
    
    def launchDrone(self, drone_name, domain_name):
        btree = behaviors.StartGlassfishTree(domain_name)
        return btree.launch()
    
    def isDomainReady(self, domain_name):
        domain_configuration = self.provision.get_online_domain_configuration(domain_name)
        defer = domain_manager.try_connecting(domain_configuration)
        return defer

def start(provisioner):
    print 'Initializing clone...'
    clone.init()
    
    print 'Setting up IaaS service'
    handler = Handler(provisioner)
    processor = Infrastructure.Processor(handler)
    pfactory = TBinaryProtocol.TBinaryProtocolFactory()
    reactor.listenTCP(config.IAAS_PORT,
                TTwisted.ThriftServerFactory(processor,
                pfactory), interface='0.0.0.0')
    
    print 'Starting reactor on port %i ...' % (config.IAAS_PORT)
    
