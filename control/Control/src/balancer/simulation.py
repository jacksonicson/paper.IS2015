from filelock.fl import FileLock
import clparams
import configuration
import controller
import traceback

if __name__ == '__main__':
    if configuration.PRODUCTION != False:
        print 'Configuration is set to PRODUCTION MODE'
        print 'Change configuration.PRODUCTION = False for simulations'
    else:
        try:
            names, res= controller.start()
        
            # Build header and values for this experiment
            conf_head, conf_values = clparams.build_result_log_title()
            names = '%s \t %s' % ('\t'.join(conf_head), names)
            res= '%s \t %s' % ('\t'.join(conf_values), res)
            
            # Append results to file
            filename = configuration.path(clparams.CL_RESULT_FILE, 'csv')
            with FileLock(filename):
                # Add header only if file is new
                try:
                    with open(filename):
                        pass
                except IOError:
                    f = open(filename, 'w')
                    f.write(names)
                    f.write('\n')
                    f.close()
                
                # Append row information 
                f = open(filename, 'a')
                f.write(res)
                f.write('\n')
                f.close()
        except:
            # Print error
            traceback.print_exc()
            
            # Build header and values for this experiment
            conf_head, conf_values = clparams.build_result_log_title()
            names = '\t'.join(conf_head)
            res= '\t'.join(conf_values)
            
            # Append results to file
            filename = configuration.path(clparams.CL_RESULT_FILE, 'err')
            with FileLock(filename):
                # Add header only if file is new
                try:
                    with open(filename):
                        pass
                except IOError:
                    f = open(filename, 'w')
                    f.write(names)
                    f.write('\n')
                    f.close()
                
                # Append row information 
                f = open(filename, 'a')
                f.write(res)
                f.write('\n')
                f.close()
                
            
            
            
