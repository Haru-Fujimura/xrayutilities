"""
module to provide functions that perform block averaging 
of intensity arrays to reduce the amount of data (mainly
for PSD and CCD measurements 

and

provide functions for normalizing intensities for 
 * count time
 * absorber (user-defined function)
 * monitor
"""

import numpy
import ctypes
import libxrayutils

def blockAverage1D(data,Nav):
    #{{{1
    """
    perform block average for 1D array/list of Scalar values
    all data are used. at the end of the array a smaller cell
    may be used by the averaging algorithm    
    
    Parameter
    ---------
    data:   data which should be contracted (length N)
    Nav:    number of values which should be averaged

    Returns
    -------
    block averaged numpy array of data type numpy.double 
    (length ceil(N/Nav))
    """

    if not isinstance(data,(numpy.ndarray,list)):
        raise TypeError("first argument has wrong data type")

    data = numpy.array(data,dtype=numpy.double)
    data = numpy.require(data,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])
    block_av = numpy.empty(numpy.ceil(data.size/float(Nav)),dtype=numpy.double,order='C')
    block_av = numpy.require(block_av,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])

    libxrayutils.cblockav_1d(block_av,data,Nav,data.size)    

    return block_av
    #}}}1

def blockAverage2D(data2d,Nav1,Nav2,**kwargs):
    #{{{1
    """
    perform a block average for 2D array of Scalar values
    all data are used therefore the margin cells may differ in size

    Parameter
    ---------
    data2d:     array of 2D data shape (N,M)
    Nav1,2:     a field of (Nav1 x Nav2) values is contracted
    **kwargs:   optional keyword argument
        roi:    region of interest for the 2D array. e.g. [20,980,40,960]
                N = 980-20; M = 960-40

    Returns
    -------
    block averaged numpy array with type numpy.double with shape
    ( ceil(N/Nav1), ceil(M/Nav2) )    
    """

    if not isinstance(data2d,(numpy.ndarray)):
        raise TypeError("first argument has wrong data type")

    # kwargs
    if kwargs.has_key('roi'):
        roi = kwargs['roi']
    else:
        roi = [0,data2d.shape[0],0,data2d.shape[1]]
        
    data = numpy.array(data2d[roi[0]:roi[1],roi[2]:roi[3]],dtype=numpy.double)
    (N,M) = data.shape
    data = data.flatten()
    data = numpy.require(data,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])
    block_av = numpy.empty(numpy.ceil(N/float(Nav1))*numpy.ceil(M/float(Nav2)),dtype=numpy.double,order='C')
    block_av = block_av.flatten()
    block_av = numpy.require(block_av,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])

    libxrayutils.cblockav_ccd(block_av,data,Nav1,Nav2,N,M)    

    block_av.shape = (numpy.ceil(N/float(Nav1)),numpy.ceil(M/float(Nav2)))
    return block_av
    
    #}}}1

def blockAveragePSD(psddata,Nav,**kwargs):
    #{{{1
    """
    perform a block average for serveral PSD spectra
    all data are used therefore the last cell used for
    averaging may differ in size

    Parameter
    ---------
    psddata:     array of 2D data shape (Nspectra,Nchannels)
    Nav:         number of channels which should be averaged
    **kwargs:    optional keyword argument
        roi:     region of interest for the 2D array. e.g. [20,980]
                 Nchannels = 980-20 

    Returns
    -------
    block averaged psd spectra as numpy array with type numpy.double
    of shape ( Nspectra , ceil(Nchannels/Nav) )  
    """
    
    if not isinstance(psddata,(numpy.ndarray)):
        raise TypeError("first argument has wrong data type")

    # kwargs
    if kwargs.has_key('roi'):
        roi = kwargs['roi']
    else:
        roi = [0,psddata.shape[1]]

    data = numpy.array(psddata[:,roi[0]:roi[1]],dtype=numpy.double)
    (Nspectra,Nchannels) = data.shape
    data = data.flatten()
    data = numpy.require(data,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])
    block_av = numpy.empty((Nspectra*numpy.ceil(Nchannels/float(Nav))),dtype=numpy.double,order='C')
    block_av = numpy.require(block_av,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])

    libxrayutils.cblockav_psd(block_av,data,Nav,Nchannels,Nspectra)    

    block_av.shape = (Nspectra,numpy.ceil(Nchannels/float(Nav)))
    return block_av
    #}}}1

######################################
##    Intensity correction class    ##
######################################
class IntensityNormalizer(object):
    #{{{1
    """
    generic class for correction of intensity (point detector,or MCA) 
    for count time and absorber factors
    the class must be supplied with a absorber correction function
    and works with data structures provided by xrutils.io classes or the 
    corresponding objects from hdf5 files read by pytables
    """
    def __init__(self,det,**keyargs):
        #{{{2
        """
        initialization of the corrector class

        Parameter
        ---------
        det : detector field name of the data structure
        **keyargs: 
            mon : monitor field name
            time: count time field name or count time as float
            av_mon: average monitor value (default: data[mon].mean())
            absfun: absorber correction function to be used as in
                    absorber_corrected_intensity = data[det]*absfun(data)

        Examples
        --------
        >>> detcorr = IntensityNormalizer(det="MCA",time="Seconds",absfun=lambda d: d["PSDCORR"]/d["PSD"].astype(numpy.float))
        """

        #check input arguments
        self._setdet(det)

        if keyargs.has_key('mon'):
            self._setmon(keyargs['mon'])
        else:
            self._mon = None

        if keyargs.has_key('time'):
            self._settime(keyargs['time'])
        else:
            self._time = None

        if keyargs.has_key('av_mon'):
            self._setavmon(keyargs['av_mon'])
        else:
            self._avmon = None

        if keyargs.has_key('absfun'):
            self._setabsfun(keyargs['absfun'])
        else:
            self._absfun = None
        #}}}2

    def _getdet(self):
        #{{{2
        """
        det property handler
        returns the detector field name
        """
        return self._det
        #}}}2

    def _setdet(self,det):
        #{{{2
        """
        det  property handler
        sets the detector field name
        """
        if isinstance(det,str):
            self._det = det
        else:
            self._det = None
            raise TypeError("det must be of type str")
        #}}}2

    def _gettime(self):
        #{{{2
        """
        time property handler
        returns the count time or the field name of the count time
        or None if time is not set
        """
        return self._time
        #}}}2

    def _settime(self,time):
        #{{{2
        """
        time property handler
        sets the count time field or value
        """
        if isinstance(time,str):
            self._time = time
        elif isinstance(time,(float,int)):
            self._time = float(time)
        elif isinstance(time,type(None)):
            self._time = None
        else:
            raise TypeError("time must be of type str, float or None")
        #}}}2

    def _getmon(self):
        #{{{2
        """
        mon property handler
        returns the monitor field name or None if not set
        """
        return self._mon
        #}}}2

    def _setmon(self,mon):
        #{{{2
        """
        mon property handler
        sets the monitor field name
        """
        if isinstance(mon,str):
            self._mon = mon
        elif isinstance(mon,type(None)):
            self._mon = None
        else: 
            raise TypeError("mon must be of type str")
        #}}}2

    def _getavmon(self):
        #{{{2
        """
        av_mon property handler
        returns the value of the average monitor or None
        if average is calculated from the monitor field
        """
        return self._avmon
        #}}}2

    def _setavmon(self,avmon):
        #{{{2
        """
        avmon property handler
        sets the average monitor field name
        """
        if isinstance(avmon,(float,int)):
            self._avmon = float(avmon)
        elif isinstance(avmon,type(None)):
            self._avmon = None
        else: 
            raise TypeError("avmon must be of type float or None")
        #}}}2

    def _getabsfun(self):
        #{{{2
        """
        absfun property handler
        returns the costum correction function or None
        """
        return self._absfun
        #}}}2

    def _setabsfun(self,absfun):
        #{{{2
        """
        absfun property handler
        sets the costum correction function
        """
        if callable(absfun):
            self._absfun = absfun
            if self._absfun.func_code.co_argcount != 1:
                raise TypeError("absfun must be a function with one argument (data object)")
        elif isinstance(absfun,type(None)):
            self._absfun = None
        else:
            raise TypeError("absfun must be of type function or None")
        #}}}2

    det = property(_getdet,_setdet)
    time = property(_gettime,_settime)
    mon = property(_getmon,_setmon)
    avmon = property(_getavmon,_setavmon)
    absfun = property(_getabsfun,_setabsfun)

    def __call__(self,data):
        #{{{2
        """
        apply the correction method which was initialized to the measured data

        Parameter
        ---------
        data: data object from xrutils.io classes (numpy.recarray)

        Returns
        -------
        corrint: corrected intensity as numpy.array of the same shape as data[det]
        """
        corrint = numpy.zeros(data[self._det].shape,dtype=numpy.float)
        
        # set needed variables
        # monitor intensity
        if self._mon:
            mon = data[self._mon]
        else:
            mon = 1.
        # count time
        if isinstance(self._time,str):
            time = data[self._time]
        elif isinstance(self._time,float):
            time = self._time
        else:
            time = 1.
        # average monitor counts
        if self._avmon:
            avmon = self._avmon
        else:
            avmon = numpy.mean(mon)
        # absorber correction function
        if self._absfun:
            abscorr = self._absfun(data)
        else:
            abscorr = 1.
        
        c = abscorr*avmon/(mon*time)
        # correct the correction factor if it was evaluated to an incorrect value
        c[numpy.isnan(c)] = 1.0
        c[numpy.isinf(c)] = 1.0
        c[c==0] = 1.0
        
        if len(data[self._det].shape) == 1:
            corrint = data[self._det]*c
        elif len(data[self._det].shape) == 2:
            corrint = data[self._det]*c[:,numpy.newaxis]
        else:
            raise TypeError("data[det] must be an array of dimension one or two")

        return corrint
        #}}}2
    #}}}1



