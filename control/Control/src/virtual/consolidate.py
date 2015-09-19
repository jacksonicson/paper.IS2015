import util
import conf_domains
import allocation
import conf_nodes


def main():
    # Setup a migration list
    migrations = []
    
    # Consolidate everything from the delete list
    for to_delete in conf_domains.to_delete_domains(): 
        migrations.append([to_delete, 0])

    # Establish allocation    
    print 'Running migrations...'
    allocation.migrateAllocation(migrations, True)
    print 'Exiting'
    

if __name__ == '__main__':
    main()
