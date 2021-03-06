from collector import CollectService, ttypes
from thrift.protocol import TBinaryProtocol
from thrift.transport import TSocket, TTransport
import configuration as config
import logging
import sys
import time

LOG_LEVELS = {60: 50010, 
              50:50000, 
              40:40000, 
              30:30000, 
              20:20000, 
              10:10000} 
SYNC = 60

logging.addLevelName(SYNC, 'SYNC')

loggingClient = None

loggers = {}

def connect():
    # Make socket
    global transportLogging
    transportLogging = TSocket.TSocket(config.COLLECTOR_IP, config.LOGGING_PORT)
    
    # Buffering is critical. Raw sockets are very slow
    transportLogging = TTransport.TBufferedTransport(transportLogging) 
    
    # Setup the clients
    global loggingClient
    loggingClient = CollectService.Client(TBinaryProtocol.TBinaryProtocol(transportLogging));
    
    # Open the transports
    transportLogging.open()

def close():
    transportLogging.close()

class SonarLogHandler(logging.Handler):
    def __init__(self, server, port, hostname, sensor, programName):
        logging.Handler.__init__(self)
        
        self.server = server
        self.port = port
        self.hostname = hostname
        self.sensor = sensor
        self.programName = programName
        
    def emit(self, record):
        ids = ttypes.Identifier()
        ids.timestamp = int(time.time())
        ids.sensor = self.sensor
        ids.hostname = self.hostname
        
        value = ttypes.LogMessage()
        value.logLevel = LOG_LEVELS[record.levelno]
        value.logMessage = record.getMessage()
        value.programName = self.programName
        value.timestamp = ids.timestamp
        
        for _ in xrange(3): 
            try:
                print 'SonarLog: %s' % value
                loggingClient.logMessage(ids, value)
                break
            except Exception as inst:
                time.sleep(1)
                print 'COULD NOT LOG: %s' % record.getMessage()
                print inst
                pass

def getLogger(sensor, hostname=config.HOSTNAME):
    #if loggingClient is None:
    #    connect()
          
    global loggers
    if loggers.has_key(sensor) == False:
        logger = logging.getLogger(sensor)
        loggers[sensor] = logger
        
        if config.SONAR_LOGGING:
            logger.addHandler(SonarLogHandler(config.COLLECTOR_IP, config.LOGGING_PORT, hostname, sensor, "RelayControl"))
        else:
            ch = logging.StreamHandler(stream=sys.stdout)
            ch.setLevel(logging.INFO)
            logger.addHandler(ch)
        
        logger.setLevel(logging.DEBUG)
    else:
        logger = loggers[sensor]
    
    return logger
