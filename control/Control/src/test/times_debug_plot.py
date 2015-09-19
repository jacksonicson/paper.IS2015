from service import times_client
import matplotlib.pyplot as plt

def plot(profile=None):
    # Setup the new plot
    fig = plt.figure()
     
    # Create a new subplot
    ax = fig.add_subplot(1, 1, 1)
    if profile is None:
        # Connect with Times
        connection = times_client.connect()
        # Download TS
        timeSeries = connection.load('PUSER_MIX0_O2_business_ADDORDER')
        
        # Disconnect from Times      
        times_client.close()
        # Generate (x,y) signal
        signal = []
        for element in timeSeries.elements:
            signal.append(element.value)
        ax.plot(range(0, len(signal)), signal)  
    else:
        ax.plot(range(0, len(profile)), profile)
    # Display the plot        
    plt.show()

if __name__ == '__main__':
    plot() 
