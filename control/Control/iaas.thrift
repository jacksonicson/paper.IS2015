namespace java de.tum.in.storm.iaas 

typedef i64 long
typedef i32 int

service Infrastructure {
	string allocateDomain(1:int workloadProfileIndex, 2:int domainSize); 

	bool isDomainReady(1:string hostname);
	
	bool deleteDomain(1:string hostname);
	
	bool launchDrone(1:string drone, 2:string hostname);
}
