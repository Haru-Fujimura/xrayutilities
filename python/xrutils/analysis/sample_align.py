"""
functions to help with experimental alignment during experiments, especially for
experiments with linear detectors
"""
# 2011/05/28: initial import; Dominik Kriegner

import numpy
import scipy
import scipy.stats
import scipy.optimize as optimize

try: 
    from matplotlib import pyplot as plt
except RuntimeError: 
    if config.VERBOSITY >= config.INFO_ALL:
        print("XU.analysis.sample_align: warning; plotting functionality not available")

from .. import config

#################################################
## channel per degree calculation 
#################################################
def psd_chdeg(angles,channels,plot=True):
    """
    function to determine the channels per degree using a linear
    fit.
    
    Parameters
    ----------
     angles:    detector angles for which the position of the beam was 
                measured
     channels:  detector channels where the beam was found
     plot:      flag to specify if a visualization of the fit should be done
    
    Returns:
     (chdeg,centerch)
        chdeg:    channel per degree
        centerch: center channel of the detector
    """
    
    (a_s,b_s,r,tt,stderr)=scipy.stats.linregress(angles,channels)
    
    if config.VERBOSITY >= config.DEBUG:
        print ("XU.analysis.psd_chdeg: %8.4f %8.4f %6.4f %6.4f %6.4f" %(a_s,b_s,r,tt,stderr))
    centerch = scipy.polyval(numpy.array([a_s,b_s]),0.0)
    chdeg = a_s

    try: plt.__name__ 
        except NameError: 
            print("XU.analyis.psd_chdeg: Warning: plot functionality not available")
            plot = False

    if plot:
        ymin = min(min(channels),centerch)
        ymax = max(max(channels),centerch)
        xmin = min(min(angles),0.0)
        xmax = max(max(angles),0.0)
        # open new figure for the plot
        plt.figure()
        plt.plot(angles,channels,'kx',ms=8.,mew=2.)
        plt.plot([xmin-(xmax-xmin)*0.1,xmax+(xmax-xmin)*0.1],scipy.polyval(numpy.array([a_s,b_s]),[xmin-(xmax-xmin)*0.1,xmax+(xmax-xmin)*0.1]),'g-',linewidth=1.5)
        ax = plt.gca()
        plt.grid()
        ax.set_xlim(xmin-(xmax-xmin)*0.15,xmax+(xmax-xmin)*0.15)
        ax.set_ylim(ymin-(ymax-ymin)*0.15,ymax+(ymax-ymin)*0.15)
        plt.vlines(0.0,ymin-(ymax-ymin)*0.1,ymax+(ymax-ymin)*0.1,linewidth=1.5)
        plt.xlabel("detector angle")
        plt.ylabel("PSD channel") 

    if config.VERBOSITY >= config.INFO_LOW:
        print("XU.analysis.psd_chdeg: channel per degree / center channel: %8.4f / %8.4f (R=%6.4f)" % (chdeg,centerch,r)) 
    return (chdeg,centerch)


#################################################
## equivalent to PSD_refl_align MATLAB script
## from J. Stangl 
#################################################
def psd_refl_align(primarybeam,angles,channels,plot=True):
    """
    function which calculates the angle at which the sample
    is parallel to the beam from various angles and detector channels 
    from the reflected beam. The function can be used during the half 
    beam alignment with a linear detector. 

    Parameters
    ----------
    primarybeam :   primary beam channel number
    angles :        list or numpy.array with angles
    channels :      list or numpy.array with corresponding detector channels
    plot:           flag to specify if a visualization of the fit is wanted
                    default: True

    Returns
    -------
    omega : angle at which the sample is parallel to the beam

    Example
    -------
    >>> psd_refl_align(500,[0,0.1,0.2,0.3],[550,600,640,700])

    """
    
    (a_s,b_s,r,tt,stderr)=scipy.stats.linregress(channels,angles)

    zeropos = scipy.polyval(numpy.array([a_s,b_s]),primarybeam)
    
    try: plt.__name__ 
        except NameError: 
            print("XU.analyis.psd_chdeg: Warning: plot functionality not available")
            plot = False
    
    if plot:
        xmin = min(min(channels),primarybeam)
        xmax = max(max(channels),primarybeam)
        ymin = min(min(angles),zeropos)
        ymax = max(max(angles),zeropos)
        # open new figure for the plot
        plt.figure()
        plt.plot(channels,angles,'kx',ms=8.,mew=2.)
        plt.plot([xmin-(xmax-xmin)*0.1,xmax+(xmax-xmin)*0.1],scipy.polyval(numpy.array([a_s,b_s]),[xmin-(xmax-xmin)*0.1,xmax+(xmax-xmin)*0.1]),'g-',linewidth=1.5)
        ax = plt.gca()
        plt.grid()
        ax.set_xlim(xmin-(xmax-xmin)*0.15,xmax+(xmax-xmin)*0.15)
        ax.set_ylim(ymin-(ymax-ymin)*0.15,ymax+(ymax-ymin)*0.15)
        plt.vlines(primarybeam,ymin-(ymax-ymin)*0.1,ymax+(ymax-ymin)*0.1,linewidth=1.5)
        plt.xlabel("PSD Channel")
        plt.ylabel("sample angle") 

    if config.VERBOSITY >= config.INFO_LOW:
        print("XU.analysis.psd_refl_align: sample is parallel to beam at goniometer angle %8.4f (R=%6.4f)" % (zeropos,r)) 
    return zeropos

#################################################
#  miscut calculation from alignment in 2 and 
#  more azimuths
#################################################
def miscut_calc(phi,aomega,zeros=None,plot=True,omega0=None):
    """
    function to calculate the miscut direction and miscut angle of a sample 
    by fitting a sinusoidal function to the variation of the aligned 
    omega values of more than two reflections.
    The function can also be used to fit reflectivity alignment values
    in various azimuths.

    Parameters
    ----------
     phi:       azimuths in which the reflection was aligned (deg)
     aomega:    aligned omega values (deg)
     zeros:     (optional) angles at which surface is parallel to 
                the beam (deg). For the analysis the angles 
                (aomega-zeros) are used.
     plot:      flag to specify if a visualization of the fit is wanted.
                default: True
     omega0:    if specified the nominal value of the reflection is not
                included as fit parameter, but is fixed to the specified
                value. This value is MANDATORY if ONLY TWO AZIMUTHs are
                given.

    Returns
    -------
    [omega0,phi0,miscut]

    list with fitted values for 
     omega0:    the omega value of the reflection should be close to 
                the nominal one
     phi0:      the azimuth in which the primary beam looks upstairs
     miscut:    amplitude of the sinusoidal variation == miscut angle

    """
    
    if zeros != None:
        om = (numpy.array(aomega)-numpy.array(zeros))
    else:
        om = numpy.array(aomega)

    a = numpy.array(phi)

    if omega0==None:
        # first guess for the parameters
        p0 = (om.mean(),a[om.argmax()],om.max()-om.min()) # omega0,phi0,miscut
        fitfunc = lambda p,phi: numpy.abs(p[2])*numpy.cos(numpy.radians(phi-(p[1]%360.))) + p[0]
    else:
        # first guess for the parameters
        p0 = (a[om.argmax()],om.max()-om.min()) # # omega0,phi0,miscut
        fitfunc = lambda p,phi: numpy.abs(p[1])*numpy.cos(numpy.radians(phi-(p[0]%360.))) + omega0
    errfunc = lambda p,phi,om: fitfunc(p,phi) - om
    errfunc2 = lambda p,phi,om: numpy.sum((fitfunc(p,phi) - om)**2)

    p1, success = optimize.leastsq(errfunc, p0, args=(a,om),maxfev=10000)
    if config.VERBOSITY >= config.INFO_ALL:
        print("xu.analysis.misfit_calc: leastsq optimization return value: %d" %success)

    try: plt.__name__ 
        except NameError: 
            print("XU.analyis.psd_chdeg: Warning: plot functionality not available")
            plot = False
    
    if plot:
        plt.figure()
        plt.plot(a,om,'kx',mew=2,ms=8)
        plt.plot(numpy.linspace(a.min()-45,a.min()+360-45,num=1000),fitfunc(p1,numpy.linspace(a.min()-45,a.min()+360-45,num=1000)),'g-',linewidth=1.5)
        plt.grid()
        plt.xlabel("azimuth")
        plt.ylabel("aligned sample angle") 

    if omega0==None:
        ret = [p1[0],p1[1]%360.,numpy.abs(p1[2])]
    else:
        ret = [omega0]+[p1[0]%360.,numpy.abs(p1[1])]
        
    if config.VERBOSITY >= config.INFO_LOW:
        print("xu.analysis.misfit_calc: \n \
                \t fitted reflection angle: %8.4f \n \
                \t looking upstairs at phi: %8.4f \n \
                \t mixcut angle: %8.4f \n" % (ret[0],ret[1],ret[2]))        
 
    return ret

