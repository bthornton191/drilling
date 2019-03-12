"""Module for working with drilling data.

"""
import re
from scipy import signal
import pandas as pd

def pason_post_processing(t, sig):
    """
    Process a signal as it would be processed by pason
    
    This function applies the following processing steps:
        1. Sample at 50 Hz    
        2. Apply a digital low pass filter with a cutoff frequency of 0.99 Hz
        3. Resample at 5 Hz
        4. Calculate maximum over each 1 second period

    Parameters
    ----------
    t : list
        Time series corresponding to the signal to be processed
    
    sig : list
        Signal to be processed
                  
    Returns
    -------
    tuple
        time, processed signal
    """

    def sample(sig, time, freq_samp):                
        num = int((time[-1] - time[0])*freq_samp + 1)
        return signal.resample(sig,num,t)        

    def low_pass(sig, time, freq_cutoff):
        freq_samp = 1/(time[1]-time[0])
        omega = freq_cutoff/freq_samp*2
        b_coef, a_coef = signal.butter(5, omega)
        return list(signal.filtfilt(b_coef, a_coef, sig)), time

    def maximum(sig, time, period):  
        # Number of samples to between taking each maximum
        num = int(period/(time[1]-time[0]))   
        
        # Initialize `time_max` with the starting value of `time`   
        time_max = [time[0]]
        
        # Initilize `sig_max` with zero as a starting value
        sig_max = [0]
        
        counter = 0
        for i, t in enumerate(time):
            if counter == num:
                time_max.append(t)
                sig_max.append(max(sig[i-num:i]))
                counter = 0
            counter += 1

        # Set the first value equal to the second value to make the line look nice
        sig_max[0] = sig_max[1]

        return sig_max, time_max

    # (1) Sample at 50 Hz
    sig_1, t_1 = sample(sig, t, 50)

    # (2) 0.99 Hz Digital Low Pass Filter
    sig_2, t_2 = low_pass(sig_1, t_1, 0.99)

    # (3) resample at 5 Hz
    sig_3, t_3 = sample(sig_2, t_2, 5)

    # (4) calculate maximum over each 1 sec period
    sig_4, t_4 = maximum(sig_3, t_3, 1)

    return t_4, sig_4

class PasonData():
    """Object representing a Pason dataset.

    Examples
    --------
    Referring to the rpm by the :attr:`rpm` attribute

        >>> filename = 'pason.csv'
        >>> pason_data = PasonData(filename)
        >>> pason_data.rpm[1000:1002]
        [84.95, 83.89]
    
    Refering to the rpm by the standard signal name 'rpm' in the :attr:`data` attribute.

        >>> pason_data.data['rpm'][1000:1002].values
        array([84.95, 83.89])
    
    Refering to the rpm by its name in the referenced .csv file

        >>> pason_data.data['rotary_rpm'][1000:1002].values
        array([84.95, 83.89])
    
    Plotting all the standard signals. NOTE: :mod:`matplotlib.pyplot` is included in the class and can be accessed via `PasonData.plt`

        >>> for signal in PasonData.STANDARD_SIGNALS:
        >>>     pason_data.plt.figure() 
        >>>     plot = pason_data.data[signal].plot())
        >>>     plot.set_ylabel('{} ({})'.format(signal.capitalize(), pason_data.units[signal]))
        >>>     plot.set_xlabel('{} ({})'.format(pason_data.data.index.name, pason_data.units[pason_data.data.index.name]))
        >>>     plot.grid()
        >>> PasonData.plt.show()
        <matplotlib.axes._subplots.AxesSubplot object at 0x000000001C517EF0>

    Attributes
    ----------
    filename : str
        Name of the file from which Pason data was loaded.
    wob : list
        Weight on bit signal
    rpm : list
        Rotary RPM signal
    flow : list
        Mud flow rate signal
    torque : list
        Surface torque signal
    md : list
        Measured depth signal
    rop : list
        Rate of penetration signal
    pressure : list
        Differential pressure signal
    mse : list
        Mechanical specific energy signal
    units : dict
        Dictionary indicicating the units associated with each column in :attr:`data` 
    data : pandas.core.frame.DataFrame
        Pandas DataFrame containing all the data from :attr:`filename`.
    STANDARD_SIGNALS : dict
        Class attribute with standard signal name as keys and lists of expected names in the pason csv files as values.
    """
    from matplotlib import pyplot as plt

    STANDARD_SIGNALS = {
        'torque' : ['convertible_torque', 'rotary_torque', 'top_drive_torque'],
        'md' : ['bit_depth'],
        'pressure' : ['differential_pressure'],
        'mse' : ['mechanical_specific_energy'],
        'rop' : ['rate_of_penetration'],
        'rpm' : ['rotary_rpm'],
        'wob' : ['weight_on_bit'],
        'gpm' : ['total_pump_output']
    }

    def __init__(self, filename):
        """Initilizes the PasonData object.
        
        Parameters
        ----------
        filename : str
            Name of file from which Pason data will be imported.
        
        """
        self.filname = filename
        self.wob = []
        self.rpm = []
        self.flow = []
        self.torque = []
        self.md = []
        self.rop = []
        self.pressure = []
        self.mse = []
        self.units = {}

        # Read the csv file
        self.data = pd.read_csv(filename, sep=',', parse_dates=[[0,1]])

        # Create a time series and attribute and set it as the index
        self.data['time'] = (self.data[self.data.columns[0]] - self.data[self.data.columns[0]][0]).dt.total_seconds()        
        self.time = list(self.data['time'].values)
        self.units['time'] = 'sec'
        self.data.set_index('time', inplace=True)

        # Get new column names and units
        name_map = {}        
        for col_name in self.data:
            # For each column name, parse the name
            [new_col_name, *unit] = [text.strip().replace(' ','_').lower() for text in re.split('[()]', col_name)]
            name_map[col_name] = new_col_name
            
            if unit:
                # If the column name contains units
                # Add to the units dictionary
                self.units[new_col_name] = unit[0]

            # Check if the current column name matches any standard variables
            for var, expct_col_nms in self.STANDARD_SIGNALS.items():
                if new_col_name in expct_col_nms:
                    self.data[var] = self.data[col_name]
                    self.__dict__[var] = list(self.data[col_name].values)
                    if unit:
                        # If the column name contains units
                        # Add to the units dictionary
                        self.units[var] = unit[0]  
        
        # Rename the columns
        self.data.rename(index=str, columns=name_map, inplace=True)
        