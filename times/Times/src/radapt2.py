from service import times_client
import sys
import argparse

class Find(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        try:
            query = values
            port = times_client.port_MKII
            if namespace.version == 1:    
                port = times_client.port_MKI
            else:
                port = times_client.port_MKII

            connection = times_client.connect(port)
            results = connection.find(query)
            print 'name'
            for result in results:
                print '%s' % result
        finally:
            times_client.close()

        
class Download(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        try:
            name = values
            port = times_client.port_MKII    
            if namespace.version == 1:
                if namespace.version == 1:
                    port = times_client.port_MKI
                else:
                    port = times_client.port_MKII
            
            connection = times_client.connect(port)
            result = connection.find(name)
            if len(result) == 0:
                print '0,0'
                sys.exit(1)
            
            ts = connection.load(name)
            print 'timestamp,value'
            for element in ts.elements:
                print '%i,%i' % (element.timestamp, element.value)
            
        finally:
            times_client.close()


parser = argparse.ArgumentParser(description='R adapter for Times')
parser.add_argument('--version', default=2, type=int)
group = parser.add_mutually_exclusive_group()
group.add_argument('--find', action=Find)
group.add_argument('--download', action=Download)
res = parser.parse_args()

