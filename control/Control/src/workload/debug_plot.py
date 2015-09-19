import load
import conf_domainsize
import matplotlib.pyplot as plt
import configuration
import conf_load

def plot_all():
    print 'Total profiles: %i' % load.count()
    
    # For each workload profile available
    for i in xrange(load.count()):
        # For all domain sizes configured
        for s in xrange(conf_domainsize.count_domain_sizes()):
            # Load user profile
            ts = load.get_user_profile(i, s)[1]
            #ts = load.get_cpu_profile(i, s)[1]
            
            # Create figure
            fig = plt.figure()
            subplot = fig.add_subplot(111)
            subplot.set_ylim(ymax=100, ymin=0)
            subplot.plot(range(len(ts)), ts)
            
            # Path and save 
            path = configuration.path('%s_%i_%i' % (conf_load.TIMES_SELECTED_MIX.name, i, s),'png') 
            print path
            plt.savefig(path)


def print_all():
    print 'Total profiles: %i' % load.count()
    for i in xrange(load.count()):
        print load.get_cpu_profile(i, conf_domainsize.DEFAULT)

if __name__ == '__main__':
    # print_all()
    plot_all()
    