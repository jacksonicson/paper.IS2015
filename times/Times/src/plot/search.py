from service import times_client

connection = times_client.connect()

result = connection.find('TS_NAME')
for i in result:
    print i

#if True:
#    result = connection.find('^mkI_.*cpu_profile_norm$')
#    
#    for i in result:
#        data = connection.load(i)
#        res = (len(data.elements) * data.frequency) / (60.0*60.0)
#        print '%s - %i X %f = %f' % (i, len(data.elements), data.frequency, res)
    

times_client.close()