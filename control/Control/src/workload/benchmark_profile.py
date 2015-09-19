from service import times_client as tc
from times import ttypes
from timeutil import hour, sec

# Configuration ###
overwrite = True
###################

def createBenchmarkProfile(name, users, freq, duration):
    # Check if the profile exists
    if len(tc.connection().find(name)) > 0:
        # Double check if it is allowed to overwrite profiles in Times
        if overwrite:
            tc.connection().remove(name)
        else:
            print 'WARNING - will not overwrite profile %s' % name
            return
        
    # Create a new ts
    print '    writing profile handles %s' % (name)
    tc.connection().create(name, freq)
    
    # Crete elements array
    elements = []
    for i in xrange(duration / freq):
        element = ttypes.Element()
        element.timestamp = i * freq
        element.value = users 
        elements.append(element)

    # Append elements to ts
    tc.connection().append(name, elements)


def main():
    tc.connect()
    createBenchmarkProfile('PUSER_BENCHMARK_SMALL', 100, sec(3), hour(6))
    createBenchmarkProfile('PUSER_BENCHMARK_MEDIUM', 150, sec(3), hour(6))
    createBenchmarkProfile('PUSER_BENCHMARK_LARGE', 200, sec(3), hour(6))
    tc.close()

if __name__ == '__main__':
    main() 