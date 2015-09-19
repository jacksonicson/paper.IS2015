'''
Global Configuration File
'''

from socket import gethostname
import platform
import sys

###################################################################################################
# WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING #
###################################################################################################  
# ENABLE PRODUCTION MODE ###
############################
PRODUCTION = False
###################################################################################################
# WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING #
###################################################################################################

# Debug mode is enabled for development
DEBUG = False

# Ask user explicitly if production mode is enabled
__asked = False
if PRODUCTION == True and __asked == False:
    __asked = True
    
    if gethostname() != 'Andreas-PC':
        print 'ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR '
        print 'You hostname %s is not allowed to launch in production mode' % gethostname()
        print 'ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR '
        sys.exit(0)
    
    print 'WARNING WARNING WARNING WARNING WARNING WARNING WARNING'
    print 'Production mode is set to TRUE'
    print 'WARNING WARNING WARNING WARNING WARNING WARNING WARNING'
    yes = raw_input('Enter "y" to continue:')
    if yes != 'y':
        print 'Exiting'
        sys.exit(0);

if DEBUG: 
    production_hosts = ('Andreas-PC', 'vrtbichler2')
    if platform.system() == 'Linux':
        if gethostname() in production_hosts:
            print 'WARNING WARNING WARNING WARNING WARNING WARNING WARNING'
            print 'Trying to run in DEBUG mode on a production system'
            print 'WARNING WARNING WARNING WARNING WARNING WARNING WARNING'
            print 'Exiting'
            sys.exit(1)

##########################
# COLLECTOR ##############
COLLECTOR_IP = 'monitor0.dfg'
COLLECTOR_HOST = 'monitor0.dfg'
COLLECTOR_PORT = 7911
COLLECTOR_MANAGEMENT_PORT = 7931

##########################
# RELAY ##################
RELAY_PORT = 7900

##########################
# # LOGGING              ##
# Logging to Sonar is only enabled in production mode. Everything else
# is debugging or playground tests. 
SONAR_LOGGING = PRODUCTION
LOGGING_PORT = 7921
HOSTNAME = gethostname()

##########################
# CONTROLLER ############
LISTENING_PORT = 9876
LISTENING_INTERFACE_IPV4 = '192.168.96.6'
PUMP_SPEEDUP = 1
MIGRATION_DOWNTIME = 15000

##########################
# IAAS ###################
IAAS_PORT = 9877
IAAS_INTERFACE_IPV4 = '192.168.96.6'

##########################
# FILES ##################
def path(filename, ending='txt'):
    directories = {
                   'Linux' : '/tmp/%s.%s' % (filename, ending),
                   'Darwin' : '/tmp/%s.%s' % (filename, ending),
                   'Windows' : 'C:/temp/%s.%s' % (filename, ending)
                   }
    return directories[platform.system()]


def force_production_mode():
    if not PRODUCTION:
        print 'This program requires PRODUCTION=True mode'
        sys.exit(1)
        