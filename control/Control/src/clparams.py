from optparse import OptionParser, BadOptionError, AmbiguousOptionError
import sys

# Parameters
CL_RESULT_FILE = 'undefined'

class PassThroughOptionParser(OptionParser):
    '''
    Ignore options that are not in hte option list
    '''
    def _process_args(self, largs, rargs, values):
        while rargs:
            try:
                OptionParser._process_args(self, largs, rargs, values)
            except (BadOptionError, AmbiguousOptionError), e:
                largs.append(e.opt_str)

# Argument parser
parser = PassThroughOptionParser()
parser.add_option('-f', '--filename', dest='filename', help='output file to store the simulation result')

# Parse command line arguments 
options, args = parser.parse_args()

if options.filename is not None:
    print 'Appending results to file: %s' % options.filename 
    CL_RESULT_FILE = options.filename

def build_result_log_title():
    header, values = [], []
    for i, param in enumerate(sys.argv):
        if not param.isupper():
            continue
        if not param.startswith('-'):
            continue
        
        # Add param name without dash
        header.append(sys.argv[i][1:])
        
        # Add param value 
        values.append(sys.argv[i + 1])
        
    return header, values

def load_parameters(module):
    '''
    Overwrite configuration params in a module using command line params
    '''
    variables = dir(module)
    for i, param in enumerate(sys.argv):
        param = param[1:]
        if param in variables:
            curr = getattr(module, param)
            if type(curr) == type(1):
                value = int(sys.argv[i + 1])
                print 'Applying parameter %s to %i in module %s (int)' % (param, value, module.__name__)
            elif type(curr) == type(1.):
                value = float(sys.argv[i + 1])
                print 'Applying parameter %s to %f in module %s (float)' % (param, value, module.__name__)
            elif type(curr) == type(''):
                value = str(sys.argv[i + 1])
                print 'Applying parameter %s to %s in module %s (str)' % (param, value, module.__name__)

            setattr(module, param, value)
