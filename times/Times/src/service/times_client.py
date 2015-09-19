from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from times import TimeService

transport = None
client = None

# Ports
port_DEFAULT = 7855 # MKII2
port_MKI = 7856
port_MKII = 7858
port_MKII2 = 7857

def connect(port=port_DEFAULT):
    global transport
    global client
    transport = TSocket.TSocket('localhost', port)
    transport = TTransport.TBufferedTransport(transport)
    protocol = TBinaryProtocol.TBinaryProtocol(transport)
    client = TimeService.Client(protocol)
    transport.open()
    return client

def connection():
    return client

def close():
    transport.close()
