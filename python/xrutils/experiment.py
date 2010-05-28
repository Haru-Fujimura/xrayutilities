"""
module helping with planning and analyzing experiments

various classes are provided for 
 * describing experiments
 * calculating angular coordinates of Bragg reflections
 * converting angular coordinates to Q-space and vice versa
 * simulating powder diffraction patterns for materials
"""

import numpy
import math
import materials
from numpy.linalg import norm
import warnings
import re
import ctypes
import libxrayutils

_e_const = 1.60219e-19
_h_const = 6.62602e-34
_c_const = 2.997925e8
_epsilon = 1.e-7

# regular expression to check goniometer circle syntax
circleSyntax = re.compile("[xyz][+-]")

class QConversion(object):
#{{{1
    """
    Class for the conversion of angular coordinates to momentum
    space for arbitrary goniometer geometries

    the class is configured with the initialization and does provide three
    distinct routines for conversion to momentum space for 

      * point detector:     point(...) or __call__()
      * linear detector:    linear(...)
      * area detector:      area(...)

    linear() and area() can only be used after the init_linear() 
    or init_area() routines were called
    """
    def __init__(self,sampleAxis,detectorAxis,r_i,**kwargs):
        #{{{2
        """
        initialize Qconversion object. 
        This means the sample and detector cicles are set and if detector geometries for 
        linear or area detector are given they are also initialized

        Parameters
        ----------
        sampleAxis:     list or tuple of sample circles, e.g. ['x+','z+']
        detectorAxis:   list or tuple of detector circles
        r_i:            vector giving the direction of the primary beam (length is irrelevant)
        **kwargs:       optional keyword arguments
            wl:        wavelength of the x-rays in Angstroem
        """

        self._set_sampleAxis(sampleAxis)
        self._set_detectorAxis(detectorAxis)
        
        # r_i
        if isinstance(r_i,(list,tuple,numpy.ndarray)):
            self.r_i = numpy.array(r_i,dtype=numpy.double)
            self.r_i = numpy.require(self.r_i,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])
            if self.r_i.size != 3:
                print "QConversion: warning invalid primary beam direction given -> using [0,1,0]"
                self.r_i = numpy.array([0,1,0],dtype=numpy.double,order='C')
                self.r_i = numpy.require(self.r_i,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])
        else:
            raise TypeError("QConversion: invalid type of primary beam direction r_i")

        # kwargs
        if kwargs.has_key('wl'):
            self._wl = numpy.double(kwargs['wl'])
        else:
            self._wl = numpy.double(1.5406)

        self._linear_init = False
        self._area_init = False
        #}}}2

    def _set_sampleAxis(self,sampleAxis):
        #{{{2
        """
        property handler for _sampleAxis

        checks if a syntactically correct list of sample circles is given

        Parameter
        ---------
        sampleAxis:     list or tuple of sample circles, e.g. ['x+','z+']
        """

        if isinstance(sampleAxis,(str,list,tuple)):
            if isinstance(sampleAxis,str):
                sAxis = list([sampleAxis])
            else:
                sAxis = list(sampleAxis)
            for circ in sAxis:
                if not isinstance(circ,str) or len(circ)!=2:
                    raise ValueError("QConversion: incorrect sample circle syntax")
                if not circleSyntax.search(circ):
                    raise ValueError("QConversion: incorrect sample circle syntax (%s)" %circ)
        else: 
            raise TypeError("Qconversion error: invalid type for sampleAxis")
        self._sampleAxis = sAxis
        self._sampleAxis_str = ''
        for circ in self._sampleAxis:
            self._sampleAxis_str += circ
        #}}}2

    def _get_sampleAxis(self):
        #{{{2
        """
        property handler for _sampleAxis

        Returns
        -------
        list of sample axis following the syntax /[xyz][+-]/
        """
        return self._sampleAxis
        #}}}2

    def _set_detectorAxis(self,detectorAxis):
        #{{{2
        """
        property handler for _detectorAxis_

        checks if a syntactically correct list of detector circles is given

        Parameter
        ---------
        detectorAxis:     list or tuple of detector circles, e.g. ['x+']
        """
        if isinstance(detectorAxis,(str,list,tuple)):
            if isinstance(detectorAxis,str):
                dAxis = list([detectorAxis])
            else:
                dAxis = list(detectorAxis)
            for circ in dAxis:
                if not isinstance(circ,str) or len(circ)!=2:
                    raise ValueError("QConversion: incorrect detector circle syntax")
                if not circleSyntax.search(circ):
                    raise ValueError("QConversion: incorrect detector circle syntax (%s)" %circ)
        else: 
            raise TypeError("Qconversion error: invalid type for detectorAxis")
        self._detectorAxis = dAxis
        self._detectorAxis_str = ''
        for circ in self._detectorAxis:
            self._detectorAxis_str += circ
        #}}}2

    def _get_detectorAxis(self):
        #{{{2
        """
        property handler for _detectorAxis

        Returns
        -------
        list of detector axis following the syntax /[xyz][+-]/
        """
        return self._detectorAxis
        #}}}2

    sampleAxis = property(_get_sampleAxis,_set_sampleAxis)
    detectorAxis = property(_get_detectorAxis,_set_detectorAxis)

    def __str__(self):
        #{{{2
        pstr =  'QConversion geometry \n'
        pstr += '---------------------------\n'
        pstr += 'sample geometry(%d): ' %len(self._sampleAxis) + self._sampleAxis_str + '\n'
        pstr += 'detector geometry(%d): ' %len(self._detectorAxis) + self._detectorAxis_str + '\n'
        pstr += 'primary beam direction: (%5.2f %5.2f %5.2f) \n' %(self.r_i[0],self.r_i[1],self.r_i[2])

        if self._linear_init:
            pstr += '\n linear detector initialized:\n'
            pstr += 'linear detector mount direction: ' + self._linear_detdir + '\n'
            pstr += 'number of channels/center channel: %d/%d\n' %(self._linear_Nch,self._linear_cch)
            pstr += 'distance to center of rotation/pixel width: %10.4g/%10.4g \n' %(self._linear_distance,self._linear_pixwidth)
            chpdeg = 2*self._linear_distance/self._linear_pixwidth*numpy.tan(numpy.radians(0.5))
            pstr += 'corresponds to channel per degree: %8.2f\n' %(chpdeg)
        if self._area_init:
            pstr += '\n area detector initialized:\n'
            pstr += 'area detector mount directions: %s/%s\n' %(self._area_detdir1,self._area_detdir2) 
            pstr += 'number of channels/center channels: (%d,%d) / (%d,%d)\n' %(self._area_Nch1,self._area_Nch2,self._area_cch1,self._area_cch2)
            pstr += 'distance to center of rotation/pixel width: %10.4g/ (%10.4g,%10.4g) \n' %(self._area_distance,self._area_pwidth1,self._area_pwidth2)
            chpdeg1 = 2*self._area_distance/self._area_pwidth1*numpy.tan(numpy.radians(0.5))
            chpdeg2 = 2*self._area_distance/self._area_pwidth2*numpy.tan(numpy.radians(0.5))
            pstr += 'corresponds to channel per degree: (%8.2f,%8.2f)\n' %(chpdeg1,chpdeg2)
       
        return pstr
        #}}}2

    def __call__(self,*args,**kwargs):
        #{{{2
        """
        wrapper function for point(...)
        """
        return self.point(*args,**kwargs)
        #}}}2

    def point(self,*args,**kwargs):
        #{{{2
        """
        angular to momentum space conversion for a point detector
        located in direction of self.r_i when detector angles are zero

        Parameters
        ----------
        *args:          sample and detector angles as numpy array, lists or Scalars
                        in total len(self.sampleAxis)+len(detectorAxis) must be given
                        always starting with the outer most circle
                        all arguments must have the same shape or length
            sAngles:    sample circle angles, number of arguments must correspond to 
                        len(self.sampleAxis)
            dAngles:    detector circle angles, number of arguments must correspond to
                        len(self.detectorAxis)

        **kwargs:       optional keyword arguments
            delta:      giving delta angles to correct the given ones for misalignment
                        delta must be an numpy array or list of len(*args)
                        used angles are than *args - delta
            wl:         x-ray wavelength in angstroem (default: self._wl)
            deg:        flag to tell if angles are passed as degree (default: True)

        Returns
        -------
        reciprocal space positions as numpy.ndarray with shape ( * , 3 )
        where * corresponds to the number of points given in the input
        """
        
        Ns = len(self.sampleAxis)
        Nd = len(self.detectorAxis)
        Ncirc = Ns + Nd

        # kwargs
        if kwargs.has_key('wl'):
            wl = numpy.double(kwargs['wl'])
        else:
            wl = self._wl

        if kwargs.has_key('deg'):
            deg = kwargs['deg']
        else:
            deg = True

        if kwargs.has_key('delta'):
            delta = numpy.array(kwargs['delta'],dtype=numpy.double)
            if delta.size != Ncirc:
                raise ValueError("QConversion: keyword argument delta does not have an appropriate shape")
        else:
            delta = numpy.zeros(Ncirc)
        
        # prepare angular arrays from *args
        # need one sample angle and one detector angle array 
        if len(args) != Ncirc:
            raise Exception("QConversion: wrong amount (%d) of arguments given, \
                             number of arguments should be %d" %(len(args),Ncirc))
        
        try: Npoints = len(args[0])
        except TypeError: Npoints = 1

        sAngles = numpy.array((),dtype=numpy.double)
        for i in range(Ns):
            arg = args[i]
            if not isinstance(arg,(numpy.ScalarType,list,numpy.ndarray)):
                raise TypeError("QConversion: invalid type for one of the sample coordinates")
            elif isinstance(arg,numpy.ScalarType):
                arg = numpy.array([arg],dtype=numpy.double)
            elif isinstance(arg,list):
                arg = numpy.array(arg,dtype=numpy.double)
            arg = arg - delta[i]
            sAngles = numpy.concatenate((sAngles,arg))
        
        dAngles = numpy.array((),dtype=numpy.double)
        for i in range(Ns,Ncirc):
            arg = args[i]
            if not isinstance(arg,(numpy.ScalarType,list,numpy.ndarray)):
                raise TypeError("QConversion: invalid type for one of the detector coordinates")
            elif isinstance(arg,numpy.ScalarType):
                arg = numpy.array([arg],dtype=numpy.double)
            elif isinstance(arg,list):
                arg = numpy.array(arg,dtype=numpy.double)      
            arg = arg - delta[i]
            dAngles = numpy.concatenate((dAngles,arg))
        
        if Npoints > 1:
            sAngles.shape = (Ns,Npoints)
            sAngles = numpy.ravel(sAngles.transpose())
            dAngles.shape = (Nd,Npoints)
            dAngles = numpy.ravel(dAngles.transpose())

        if deg:
            sAngles = numpy.radians(sAngles)
            dAngles = numpy.radians(dAngles)

        sAngles = numpy.require(sAngles,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])
        dAngles = numpy.require(dAngles,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])

        # initialize return value (qposition) array
        qpos = numpy.empty(Npoints*3,dtype=numpy.double,order='C')
        qpos = numpy.require(qpos,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])
        
        sAxis=ctypes.c_char_p(self._sampleAxis_str)
        dAxis=ctypes.c_char_p(self._detectorAxis_str)

        libxrayutils.cang2q_point(sAngles, dAngles, qpos, self.r_i,len(self.sampleAxis),
                     len(self.detectorAxis),Npoints,sAxis,dAxis,wl)

        #reshape output
        qpos.shape = (Npoints,3)

        return qpos[:,0],qpos[:,1],qpos[:,2]
        #}}}2

    def init_linear(self,detectorDir,cch,Nchannel,distance=None,pixelwidth=None,chpdeg=None,**kwargs):
        #{{{2
        """
        initialization routine for linear detectors
        detector direction as well as distance and pixel size or
        channels per degree must be given.

        Parameters
        ----------
        detectorDir:     direction of the detector (along the pixel array); e.g. 'z+'
        cch:             center channel, in direction of self.r_i at zero
                         detectorAngles
        Nchannel:        total number of detector channels 
        distance:        distance of center channel from center of rotation
        pixelwidth:      width of one pixel (same unit as distance)
        chpdeg:          channels per degree (only absolute value is relevant) sign 
                         determined through detectorDir

                         !! Either distance and pixelwidth or chpdeg must be given !!

        **kwargs:        optional keyword arguments
            Nav:         number of channels to average to reduce data size (default: 1)
            roi:         region of interest for the detector pixels; e.g. [100,900]
        """
        
        # detectorDir
        if not isinstance(detectorDir,str) or len(detectorDir)!=2:
            raise ValueError("QConversion: incorrect detector direction syntax")
        if not circleSyntax.search(detectorDir):
            raise ValueError("QConversion: incorrect detector direction syntax (%s)" %detectorDir)
        self._linear_detdir = detectorDir
        
        self._linear_Nch = int(Nchannel)
        self._linear_cch = float(cch)
        
        if distance!=None and pixelwidth!=None:
            self._linear_distance = float(distance)
            self._linear_pixwidth = float(pixelwidth)
        elif chpdeg!=None:
            self._linear_distance = 1.0
            self._linear_pixwidth = 2*self._linear_distance/numpy.abs(float(chpdeg))*numpy.tan(numpy.radians(0.5))
        else:
            # not all needed values were given 
            raise Exception("QConversion: not all mandatory arguments were given -> read API doc")


        # kwargs
        if kwargs.has_key('roi'):
            self._linear_roi = kwargs['roi']
        else:
            self._linear_roi = [0,self._linear_Nch]
        if kwargs.has_key('Nav'):
            self._linear_nav = kwargs['Nav']
        else:
            self._linear_nav = 1
        
        self._linear_init = True

        #}}}2
               
    def linear(self,*args,**kwargs):
        #{{{2
        """
        angular to momentum space conversion for a linear detector
        the cch of the detector must be in direction of self.r_i when 
        detector angles are zero

        the detector geometry must be initialized by the init_linear(...) routine

        Parameters
        ----------
        *args:          sample and detector angles as numpy array, lists or Scalars
                        in total len(self.sampleAxis)+len(detectorAxis) must be given
                        always starting with the outer most circle
                        all arguments must have the same shape or length
            sAngles:    sample circle angles, number of arguments must correspond to 
                        len(self.sampleAxis)
            dAngles:    detector circle angles, number of arguments must correspond to
                        len(self.detectorAxis)

        **kwargs:       possible keyword arguments
            delta:      giving delta angles to correct the given ones for misalignment
                        delta must be an numpy array or list of len(*args)
                        used angles are than *args - delta
            Nav:        number of channels to average to reduce data size (default: self._linear_nav)
            roi:        region of interest for the detector pixels; e.g. [100,900] (default: self._linear_roi)
            wl:         x-ray wavelength in angstroem (default: self._wl)
            deg:        flag to tell if angles are passed as degree (default: True)

        Returns
        -------
        reciprocal space position of all detector pixels in a numpy.ndarray of shape
        ( (*)*(self._linear_roi[1]-self._linear_roi[0]+1) , 3 )
        """
        
        if not self._linear_init:
            raise Exception("QConversion: linear detector not initialized -> call Ang2Q.init_linear(...)")

        Ns = len(self.sampleAxis)
        Nd = len(self.detectorAxis)
        Ncirc = Ns + Nd

        # kwargs
        if kwargs.has_key('wl'):
            wl = numpy.double(kwargs['wl'])
        else:
            wl = self._wl

        if kwargs.has_key('deg'):
            deg = kwargs['deg']
        else:
            deg = True

        if kwargs.has_key('Nav'):
            nav = kwargs['Nav']
        else:
            nav = 1

        if kwargs.has_key('roi'):
            roi = kwargs['roi']
        else:
            roi = self._linear_roi

        if kwargs.has_key('delta'):
            delta = numpy.array(kwargs['delta'],dtype=numpy.double)
            if delta.size != Ncirc:
                raise ValueError("QConversion: keyword argument delta does not have an appropriate shape")
        else:
            delta = numpy.zeros(Ncirc)
        
        # prepare angular arrays from *args
        # need one sample angle and one detector angle array 
        if len(args) != Ncirc:
            raise Exception("QConversion: wrong amount (%d) of arguments given, \
                             number of arguments should be %d" %(len(args),Ncirc))
        
        try: Npoints = len(args[0])
        except TypeError: Npoints = 1

        sAngles = numpy.array((),dtype=numpy.double)
        for i in range(Ns):
            arg = args[i]
            if not isinstance(arg,(numpy.ScalarType,list,numpy.ndarray)):
                raise TypeError("QConversion: invalid type for one of the sample coordinates")
            elif isinstance(arg,numpy.ScalarType):
                arg = numpy.array([arg],dtype=numpy.double)
            elif isinstance(arg,list):
                arg = numpy.array(arg,dtype=numpy.double)
            arg = arg - delta[i]
            sAngles = numpy.concatenate((sAngles,arg))
        
        dAngles = numpy.array((),dtype=numpy.double)
        for i in range(Ns,Ncirc):
            arg = args[i]
            if not isinstance(arg,(numpy.ScalarType,list,numpy.ndarray)):
                raise TypeError("QConversion: invalid type for one of the detector coordinates")
            elif isinstance(arg,numpy.ScalarType):
                arg = numpy.array([arg],dtype=numpy.double)
            elif isinstance(arg,list):
                arg = numpy.array(arg,dtype=numpy.double)      
            arg = arg - delta[i]
            dAngles = numpy.concatenate((dAngles,arg))

        # flatten angular arrays for passing them to C subprogram
        if Npoints > 1:
            sAngles.shape = (Ns,Npoints)
            sAngles = numpy.ravel(sAngles.transpose())
            dAngles.shape = (Nd,Npoints)
            dAngles = numpy.ravel(dAngles.transpose())

        if deg:
            sAngles = numpy.radians(sAngles)
            dAngles = numpy.radians(dAngles)

        # check correct array type for passing to C subprogram
        sAngles = numpy.require(sAngles,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])
        dAngles = numpy.require(dAngles,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])

        # initialize psd geometry to for C subprogram (include Nav and roi possibility)
        cch = self._linear_cch/float(nav)
        pwidth = self._linear_pixwidth*nav
        roi = numpy.ceil(numpy.array(roi)/float(nav)).astype(numpy.int32)

        # initialize return value (qposition) array
        shape = Npoints*(roi[1]-roi[0])*3
        qpos = numpy.empty(shape,dtype=numpy.double,order='C')
        qpos = numpy.require(qpos,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])
        
        sAxis=ctypes.c_char_p(self._sampleAxis_str)
        dAxis=ctypes.c_char_p(self._detectorAxis_str)
        
        libxrayutils.cang2q_linear(sAngles, dAngles, qpos, self.r_i,len(self.sampleAxis),
                     len(self.detectorAxis),Npoints,sAxis,dAxis,cch, pwidth,roi,
                     self._linear_detdir,wl)

        #reshape output
        qpos.shape = (Npoints*(roi[1]-roi[0]),3)

        return qpos[:,0],qpos[:,1],qpos[:,2]
        #}}}2

    def init_area(self,detectorDir1,detectorDir2,cch1,cch2,Nch1,Nch2,distance=None,
                  pwidth1=None,pwidth2=None,chpdeg1=None,chpdeg2=None,**kwargs):
        #{{{2
        """
        initialization routine for area detectors
        detector direction as well as distance and pixel size or
        channels per degree must be given. Two separate pixel sizes and 
        channels per degree for the two orthogonal directions can be given 

        Parameters
        ----------
        detectorDir1:    direction of the detector (along the pixel direction 1); e.g. 'z+'
        detectorDir2:    direction of the detector (along the pixel direction 2); e.g. 'x+'
        cch1,2:          center pixel, in direction of self.r_i at zero
                         detectorAngles
        Nch1:            number of detector pixels along direction 1
        Nch2:            number of detector pixels along direction 2
        distance:        distance of center pixel from center of rotation
        pwidth1,2:       width of one pixel (same unit as distance)
        chpdeg1,2:       channels per degree (only absolute value is relevant) sign 
                         determined through detectorDir1,2

                         !! Either distance and pwidth1,2 or chpdeg1,2 must be given !!

        **kwargs:        optional keyword arguments
            Nav:         number of channels to average to reduce data size (default: [1,1])
            roi:         region of interest for the detector pixels; e.g. [100,900,200,800]
        """
     
        # detectorDir
        if not isinstance(detectorDir1,str) or len(detectorDir1)!=2:
            raise ValueError("QConversion: incorrect detector direction1 syntax")
        if not circleSyntax.search(detectorDir1):
            raise ValueError("QConversion: incorrect detector direction1 syntax (%s)" %detectorDir1)
        self._area_detdir1 = detectorDir1
        if not isinstance(detectorDir2,str) or len(detectorDir2)!=2:
            raise ValueError("QConversion: incorrect detector direction2 syntax")
        if not circleSyntax.search(detectorDir2):
            raise ValueError("QConversion: incorrect detector direction2 syntax (%s)" %detectorDir2)
        self._area_detdir2 = detectorDir2
        
        # other nonw keyword arguments 
        self._area_Nch1 = int(Nch1)
        self._area_Nch2 = int(Nch2)
        self._area_cch1 = int(cch1)
        self._area_cch2 = int(cch2)
        
        # mandatory keyword arguments
        if distance!=None and pwidth1!=None and pwidth2!=None:
            self._area_distance = float(distance)
            self._area_pwidth1 = float(pwidth1)
            self._area_pwidth2 = float(pwidth2)
        elif chpdeg1!=None and chpdeg2!=None:
            self._area_distance = 1.0
            self._area_pwidth1 = 2*self._area_distance/numpy.abs(float(chpdeg1))*numpy.tan(numpy.radians(0.5))
            self._area_pwidth2 = 2*self._area_distance/numpy.abs(float(chpdeg2))*numpy.tan(numpy.radians(0.5))
        else:
            # not all needed values were given 
            raise Exception("Qconversion errror: not all mandatory arguments were given -> read API doc")
        
        # kwargs
        if kwargs.has_key('roi'):
            self._area_roi = kwargs['roi']
        else:
            self._area_roi = [0,self._area_Nch1-1,0,self._area_Nch2-1]
        if kwargs.has_key('Nav'):
            self._area_nav = kwargs['Nav']
        else:
            self._area_nav = [1,1]
        
        self._area_init = True
        #}}}2
        
    def area(self,*args,**kwargs):
        #{{{2
        """
        angular to momentum space conversion for a area detector
        the center pixel defined by the init_area routine must be 
        in direction of self.r_i when detector angles are zero

        the detector geometry must be initialized by the init_area(...) routine

        Parameters
        ----------
        *args:          sample and detector angles as numpy array, lists or Scalars
                        in total len(self.sampleAxis)+len(detectorAxis) must be given
                        always starting with the outer most circle
                        all arguments must have the same shape or length
            sAngles:    sample circle angles, number of arguments must correspond to 
                        len(self.sampleAxis)
            dAngles:    detector circle angles, number of arguments must correspond to
                        len(self.detectorAxis)

        **kwargs:       possible keyword arguments
            delta:      giving delta angles to correct the given ones for misalignment
                        delta must be an numpy array or list of len(*args)
                        used angles are than *args - delta
            roi:        region of interest for the detector pixels; e.g. [100,900,200,800]
                        (default: self._area_roi)
            Nav:        number of channels to average to reduce data size e.g. [2,2] 
                        (default: self._area_nav)
            wl:         x-ray wavelength in angstroem (default: self._wl)
            deg:        flag to tell if angles are passed as degree (default: True)

        Returns
        -------
        reciprocal space position of all detector pixels in a numpy.ndarray of shape
        ( (*)*(self._area_roi[1]-self._area_roi[0]+1)*(self._area_roi[3]-self._area_roi[2]+1) , 3 )
        were detectorDir1 is the fastest varing
        """
        
        if not self._area_init:
            raise Exception("QConversion: area detector not initialized -> call Ang2Q.init_area(...)")

        Ns = len(self.sampleAxis)
        Nd = len(self.detectorAxis)
        Ncirc = Ns + Nd

        # kwargs
        if kwargs.has_key('wl'):
            wl = numpy.double(kwargs['wl'])
        else:
            wl = self._wl

        if kwargs.has_key('deg'):
            deg = kwargs['deg']
        else:
            deg = True
        
        if kwargs.has_key('roi'):
            roi = kwargs['roi']
        else:
            roi = self._area_roi

        if kwargs.has_key('Nav'):
            nav = kwargs['Nav']
        else:
            nav = self._area_nav
       
        if kwargs.has_key('delta'):
            delta = numpy.array(kwargs['delta'],dtype=numpy.double)
            if delta.size != Ncirc:
                raise ValueError("QConversion: keyword argument delta does not have an appropriate shape")
        else:
            delta = numpy.zeros(Ncirc)

        # prepare angular arrays from *args
        # need one sample angle and one detector angle array 
        if len(args) != Ncirc:
            raise Exception("QConversion: wrong amount (%d) of arguments given, \
                             number of arguments should be %d" %(len(args),Ncirc))
        
        try: Npoints = len(args[0])
        except TypeError: Npoints = 1

        sAngles = numpy.array((),dtype=numpy.double)
        for i in range(Ns):
            arg = args[i]
            if not isinstance(arg,(numpy.ScalarType,list,numpy.ndarray)):
                raise TypeError("QConversion: invalid type for one of the sample coordinates")
            elif isinstance(arg,numpy.ScalarType):
                arg = numpy.array([arg],dtype=numpy.double)
            elif isinstance(arg,list):
                arg = numpy.array(arg,dtype=numpy.double)
            arg = arg - delta[i]
            sAngles = numpy.concatenate((sAngles,arg))
        
        dAngles = numpy.array((),dtype=numpy.double)
        for i in range(Ns,Ncirc):
            arg = args[i]
            if not isinstance(arg,(numpy.ScalarType,list,numpy.ndarray)):
                raise TypeError("QConversion: invalid type for one of the detector coordinates")
            elif isinstance(arg,numpy.ScalarType):
                arg = numpy.array([arg],dtype=numpy.double)
            elif isinstance(arg,list):
                arg = numpy.array(arg,dtype=numpy.double)      
            arg = arg - delta[i]
            dAngles = numpy.concatenate((dAngles,arg))

        # flatten arrays with angles for passing to C routine
        if Npoints > 1:
            sAngles.shape = (Ns,Npoints)
            sAngles = numpy.ravel(sAngles.transpose())
            dAngles.shape = (Nd,Npoints)
            dAngles = numpy.ravel(dAngles.transpose())

        if deg:
            sAngles = numpy.radians(sAngles)
            dAngles = numpy.radians(dAngles)

        # check that arrays have correct type and memory alignment for passing to C routine
        sAngles = numpy.require(sAngles,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])
        dAngles = numpy.require(dAngles,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])

        # initialize ccd geometry to for C subroutine (include Nav and roi possibility)
        cch1 = self._area_cch1/float(nav[0])
        cch2 = self._area_cch2/float(nav[1])
        pwidth1 = self._area_pwidth1*nav[0]
        pwidth2 = self._area_pwidth2*nav[1]
        roi = numpy.array(roi)
        roi[:2] = numpy.ceil(roi[:2]/float(nav[0]))
        roi[2:] = numpy.ceil(roi[2:]/float(nav[1]))
        roi = roi.astype(numpy.int32)

        # initialize return value (qposition) array
        qpos = numpy.empty(Npoints*(roi[1]-roi[0])*(roi[3]-roi[2])*3,
                                    dtype=numpy.double,order='C')
        qpos = numpy.require(qpos,dtype=numpy.double,requirements=["ALIGNED","C_CONTIGUOUS"])
        
        sAxis=ctypes.c_char_p(self._sampleAxis_str)
        dAxis=ctypes.c_char_p(self._detectorAxis_str)

        libxrayutils.cang2q_area(sAngles, dAngles, qpos, self.r_i,len(self.sampleAxis),
                     len(self.detectorAxis),Npoints,sAxis,dAxis, cch1, cch2, pwidth1, pwidth2,
                     roi,self._area_detdir1,self._area_detdir2,wl)

        #reshape output
        qpos.shape = (Npoints*(roi[1]-roi[0])*(roi[3]-roi[2]),3)

        return qpos[:,0],qpos[:,1],qpos[:,2]
        #}}}2

#}}}1

class Experiment(object):
    #{{{1
    """
    base class for describing experiments
    users should use the derived classes: HXRD, GID, Powder
    """
    def __init__(self,ipdir,ndir,**keyargs):
        #{{{2
        """
        initialization of an Experiment class needs the sample orientation
        given by the samples surface normal and an second not colinear direction
        specifying the inplane reference direction.

        Parameters
        ----------
        ipdir:      inplane reference direction (ipdir points into the PB
                    direction at zero angles)
        ndir:       surface normal 
        keyargs:    optional keyword arguments
            wl:     wavelength of the x-rays in Angstroem (default: 1.5406A)
            en:     energy of the x-rays in eV (default: 8048eV == 1.5406A )
                    the en keyword overrulls the wl keyword
        """
        if isinstance(ipdir,list):
            self.idir = numpy.array(ipdir,dtype=numpy.double)
        elif isinstance(ipdir,numpy.ndarray):
            self.idir = ipdir
        else:
            raise TypeError("Inplane direction must be list or numpy array")
        
        if isinstance(ndir,list):
            self.ndir = numpy.array(ndir,dtype=numpy.double)
        elif isinstance(ndir,numpy.ndarray):
            self.ndir = ndir
        else:
            raise TypeError("normal direction must be list or numpy array")
        
        #test the given direction to be not parallel and warn if not perpendicular
        if(norm(numpy.cross(self.idir,self.ndir))<_epsilon):
            raise ValueError("given inplane direction is parallel to normal direction, they must be linear independent!")
        if(numpy.dot(self.idir,self.ndir)> _epsilon):
            self.idir = numpy.cross(numpy.cross(self.ndir,self.idir),self.ndir)
            self.idir = self.idir/norm(self.idir)
            warnings.warn("Experiment: given inplane direction is not perpendicular to normal direction\n -> Experiment class uses the following direction with the same azimuth:\n %s" %(' '.join(map(str,numpy.round(self.idir,3)))))

        #set the coordinate transform for the azimuth used in the experiment
        v1 = numpy.cross(self.ndir,self.idir)
        self.transform = math.CoordinateTransform(v1,self.idir,self.ndir)
       
        # initialize Ang2Q conversion
        self._A2QConversion = QConversion('x+','x+',[0,1,0]) # 1S+1D goniometer  
        self.Ang2Q = self._A2QConversion

        #calculate the energy from the wavelength
        if keyargs.has_key("wl"):
            self._set_wavelength(keyargs["wl"])
        else:
            self._set_wavelength(1.5406)

        if keyargs.has_key("en"):
            self._set_energy(keyargs["en"])

        #}}}2

    def __str__(self):
        #{{{2
        ostr = "inplane azimuth: (%f %f %f)\n" %(self.idir[0],
                                                 self.idir[1],
                                                 self.idir[2])
        ostr += "surface normal: (%f %f %f)\n" %(self.ndir[0],
                                                 self.ndir[1],
                                                 self.ndir[2])
        ostr += "energy: %f (eV)\n" %self._en
        ostr += "wavelength: %f (Anstrom)\n" %(self._wl)
        ostr += self._A2QConversion.__str__()

        return ostr
        #}}}2

    def _set_energy(self,energy):
        #{{{2
        self._en = energy
        self._wl = _c_const*_h_const/self._en/_e_const/1.e-10
        self.k0 = numpy.pi*2./self._wl
        self._A2QConversion._wl = self._wl
        #}}}2

    def _set_wavelength(self,wl):
        #{{{2
        self._wl = wl
        self._en = _c_const*_h_const/self._wl/1.e-10/_e_const
        self.k0 = numpy.pi*2./self._wl
        self._A2QConversion._wl = self._wl
        #}}}2

    def _get_energy(self):
        return self._en

    def _get_wavelength(self):
        return self._wl

    energy = property(_get_energy,_set_energy)
    wavelength = property(_get_wavelength,_set_wavelength)

    def _set_inplane_direction(self,dir):
        #{{{2
        if isinstance(dir,list):
            self.idir = numpy.array(dir,dtype=numpy.double)
        elif isinstance(dir,numpy.ndarray):
            self.idir = dir
        else:
            raise TypeError("Inplane direction must be list or numpy array")

        v1 = numpy.cross(self.ndir,self.idir)
        self.transform = math.CoordinateTransform(v1,self.idir,self.ndir)
        #}}}2

    def _get_inplane_direction(self):
        return self.idir

    def _set_normal_direction(self,dir):
        #{{{2
        if isinstance(dir,list):
            self.ndir = numpy.array(dir,dtype=numpy.double)
        elif isinstance(dir,numpy.ndarray):
            self.ndir = dir
        else:
            raise TypeError("Surface normal must be list or numpy array")

        v1 = numpy.cross(self.ndir,self.idir)
        self.transform = math.CoordinateTransform(v1,self.idir,self.ndir)
        #}}}2

    def _get_normal_direction(self):
        return self.ndir

    def Q2Ang(self,qvec):
        pass

    def Transform(self,v):
        return self.transform(v)

# funcionality is moved to xrutils.vis
# this comment can be removed in future versions
#    def AlignIntensity(self,data):
#        pass
#
#    def Align2DMatrix(self,data):
#        return numpy.flipud(numpy.rot90(data))

    def TiltAngle(self,q,deg=True):
        #{{{2
        """
        TiltAngle(q,deg=True):
        Return the angle between a q-space position and the surface normal.

        Parameters
        ----------
        q:          list or numpy array with the reciprocal space position
        
        optional keyword arguments:
        deg:        True/False whether the return value should be in degree or radians 
                    (default: True)
        """

        if isinstance(q,list):
            qt = numpy.array(q,dtype=numpy.double)
        elif isinstance(q,numpy.ndarray):
            qt = q
        else:
            raise TypeError("q-space position must be list or numpy array")

        return math.VecAngle(self.ndir,qt,deg)
        #}}}2
    #}}}1


class HXRD(Experiment):
    #{{{1
    """
    class describing high angle x-ray diffraction experiments
    the class helps with calculating the angles of Bragg reflections
    as well as helps with analyzing measured data

    the class describes a two circle (omega,twotheta) goniometer to 
    help with coplanar x-ray diffraction experiments. Nevertheless 3D data
    can be treated with the use of linear and area detectors.
    see help self.Ang2Q
    """
    def __init__(self,idir,ndir,**keyargs):
        #{{{2
        """
        initialization routine for the HXRD Experiment class
        
        Parameters
        ----------
        same as for the Experiment base class
        +
        keyargs         additional optional keyword argument
            geometry:   determines the scattering geometry:
                        "hi_lo" (default) high incidence-low exit
                        "lo_hi" low incidence - high exit
        """
        Experiment.__init__(self,idir,ndir,**keyargs)
        
        if keyargs.has_key('geometry'):
            if keyargs['geometry'] in ["hi_lo","lo_hi"]:
                self.geometry = keyargs['geometry']
            else: 
                raise ValueError("HXRD: invalid value for the geometry argument given")
        else:
            self.geometry = "hi_lo"

        # initialize Ang2Q conversion
        self._A2QConversion = QConversion('x+','x+',[0,1,0],wl=self._wl) # 1S+1D goniometer 
        self.Ang2Q = self._A2QConversion

        #}}}2

    def TiltCorr(self,q,ang,deg=False):
        #{{{2
        """
        Correct a q-space position by a certain tilt angle.

        Parameters
        ----------
        q:       list or numpy array with the tilted q-space position
        ang:     tilt angle

        optional keyword arguments:
        deg:     True/False (default False) whether the input data is 
                 in degree or radians

        Returns
        -------
        numpy array with the corrected q-space position
        """

        #calculate the angular position of the q-space point
        [om,tth,delta] = self.Q2Ang(q)

        #calcualte the new direction of the peak
        q = self._Ang2Q(om-a,tth,delta)

        return q
        #}}}2

    def _Ang2Q(self,om,tth,delta,deg=True,dom=0.,dtth=0.,ddel=0.):
        #{{{2
        """
        deprecated conversion of angular into Q-space positions. see Ang2Q 
        QConversion object for more versatile Ang2Q routines

        Parameters
        ----------
        om:     omega angle
        tth:    2theta scattering angle
        delta:  off-plane angle (apart the scattering plane)

        optional keyword arguments:
        dom:    omega offset
        dtth:   tth offset
        ddel:   delta offset
        deg:    True/Flase (default is True) determines whether 
                or not input angles are given in degree or radiants

        Returns
        -------
        [qx,qy,qz]: array of q-space values
        """
        
        if deg:
            ltth = numpy.radians(tth-dtth)
            lom  = numpy.radians(om-dom)
            ldel = numpy.radians(delta-ddel)
        else:
            ltth = tth - dtth
            lom  = om - dom
            ldel = delta-ddel

        qx=2.0*self.k0*numpy.sin(ltth*0.5)*numpy.sin(lom-0.5*ltth)*numpy.sin(ldel)
        qy=2.0*self.k0*numpy.sin(ltth*0.5)*numpy.sin(lom-0.5*ltth)*numpy.cos(ldel)
        qz=2.0*self.k0*numpy.sin(0.5*ltth)*numpy.cos(lom-0.5*ltth)      

        return [qx,qy,qz]
        #}}}2

    def Q2Ang(self,Q,trans=True,deg=True,**keyargs):
        #{{{2
        """
        Convert a reciprocal space vector Q to scattering angles.
        The keyword argument trans determines whether Q should be transformed 
        to the experimental coordinate frame or not. 

        Parameters
        ----------
        Q:          a list or numpy array of shape (3) with 
                               q-space vector components

        optional keyword arguments:
        trans:      True/False apply coordinate transformation on Q
        deg:        True/Flase (default True) determines if the
                    angles are returned in radians or degrees
        geometry:   determines the scattering geometry:
                    "hi_lo" high incidence-low exit
                    "lo_hi" low incidence - high exit
                    default: self.geometry

        Returns
        -------
        a numpy array of shape (3) with three scattering angles which are
        [phi,omega,twotheta]
        phi:        sample azimuth
        omega:      incidence angle with respect to surface
        twotheta:   scattering angle
        """

        if isinstance(Q,list):
            q = numpy.array(Q,dtype=numpy.double)
        elif isinstance(Q,numpy.ndarray):
            q = Q
        else:
            raise TypeError("Q vector must be a list or numpy array")
    
        if keyargs.has_key('geometry'):
            if keyargs['geometry'] in ["hi_lo","lo_hi"]:
                self.geometry = keyargs['geometry']
            else: 
                raise ValueError("HXRD: invalid value for the geometry argument given")
        else:
            geom = self.geometry

        if trans:
            q = self.transform(q)

        qa = math.VecNorm(q)
        tth = 2.*numpy.arcsin(qa/2./self.k0)

        #calculation of the delta angle
        delta = numpy.arctan(q[0]/q[1])
        if numpy.isnan(delta):
            delta =0 
        
        om1 = numpy.arcsin(q[1]/qa/numpy.cos(delta))+0.5*tth
        om2 = numpy.arcsin(q[0]/qa/numpy.sin(delta))+0.5*tth
        if numpy.isnan(om1):
            om = om2
        elif numpy.isnan(om2):
            om = om1
        else:
            om = om1

        #have to take now the scattering geometry into account
        if(geom=="hi_lo" and om<tth/2.):
            om = tth-om
        elif(geom=="lo_hi" and om>tth/2.):
            om = tth-om

        if deg:
            return [numpy.degrees(delta),numpy.degrees(om),numpy.degrees(tth)]
        else:
            return [delta,om,tth]
        #}}}2
    #}}}1


class GID(Experiment):
    #{{{1
    """
    class describing grazing incidence x-ray diffraction experiments
    the class helps with calculating the angles of Bragg reflections
    as well as it helps with analyzing measured data

    the class describes a four circle (alpha_i,omega,twotheta,beta) 
    goniometer to help with GID experiments at the ROTATING ANODE. 
    3D data can be treated with the use of linear and area detectors.
    see help self.Ang2Q
    """
    def __init__(self,idir,ndir,**keyargs):
        #{{{2
        """
        initialization routine for the GID Experiment class

        idir defines the inplane reference direction (idir points into the PB
        direction at zero angles)
        
        Parameters
        ----------
        same as for the Experiment base class

        """
        Experiment.__init__(self,idir,ndir,**keyargs)
        
        # initialize Ang2Q conversion
        self._A2QConversion = QConversion(['z-','x+'],['x+','z-'],[0,1,0],wl=self._wl) # 2S+2D goniometer 
        self.Ang2Q = self._A2QConversion

        #}}}2

    def Q2Ang(self,Q,trans=True,deg=True,**kwargs):
        #{{{2
        """
        calculate the GID angles needed in the experiment
        the inplane reference direction defines the direction were
        the reference direction is parallel to the primary beam
        (i.e. lattice planes perpendicular to the beam)

        Parameters
        ----------
        Q:          a list or numpy array of shape (3) with 
                    q-space vector components

        optional keyword arguments:
        trans:      True/False apply coordinate transformation on Q
        deg:        True/Flase (default True) determines if the
                    angles are returned in radians or degrees

        Returns
        -------
        a numpy array of shape (2) with three scattering angles which are
        [omega,twotheta]
        omega:      incidence angle with respect to surface
        twotheta:   scattering angle
        """

        if isinstance(Q,list):
            q = numpy.array(Q,dtype=numpy.double)
        elif isinstance(Q,numpy.ndarray):
            q = Q
        else:
            raise TypeError("Q vector must be a list or numpy array")

        if trans:
            q = self.transform(q)
        
        # check if reflection is inplane
        if numpy.abs(q[2]) >= 0.001:
            print("Q: " + q.__str__())
            raise Exception("Reflection not reachable in GID geometry")

        # calculate angle to inplane reference direction
        aref = numpy.arctan2(q[0],q[1])
        # print("Directions differs by: %5.2f deg" %numpy.degrees(aref))
        
        # calculate scattering angle
        qa = math.VecNorm(q)
        tth = 2.*numpy.arcsin(qa/2./self.k0)
        om = numpy.pi/2 + aref + tth/2.

        if deg: 
            ang = [numpy.degrees(om),numpy.degrees(tth)]
        else:
            ang = [om,tth]

        return ang
        #}}}2
    #}}}1


class GID_ID10B(GID):
    #{{{1
    """
    class describing grazing incidence x-ray diffraction experiments
    the class helps with calculating the angles of Bragg reflections
    as well as it helps with analyzing measured data

    the class describes a four circle (theta,omega,delta,gamma) 
    goniometer to help with GID experiments at ID10B / ESRF. 
    3D data can be treated with the use of linear and area detectors.
    see help self.Ang2Q
    """
    def __init__(self,idir,ndir,**keyargs):
        #{{{2
        """
        initialization routine for the GID Experiment class

        idir defines the inplane reference direction (idir points into the PB
        direction at zero angles)
        
        Parameters
        ----------
        same as for the Experiment base class

        """
        Experiment.__init__(self,idir,ndir,**keyargs)
        
        # initialize Ang2Q conversion
        self._A2QConversion = QConversion(['x+','z-'],['x+','z-'],[0,1,0],wl=self._wl) # 2S+2D goniometer 
        self.Ang2Q = self._A2QConversion

        #}}}2

    def Q2Ang(self,Q,trans=True,deg=True,**kwargs):
        """
        calculate the GID angles needed in the experiment
        """
        pass

    #}}}1


class GISAXS(Experiment):
    pass

class Powder(Experiment):
    #{{{1
    """
    Experimental class for powder diffraction
    This class is able to simulate a powder spectrum for the given material
    """
    def __init__(self,mat,**keyargs):
        """
        the class is initialized with xrutils.materials.Material instance
        
        Parameters
        ----------
        mat:        xrutils.material.Material instance
                    giving the material for the experimental class
        keyargs:    optional keyword arguments
                    same as for the Experiment base class
        """
        Experiment.__init__(self,[0,1,0],[0,0,1],**keyargs)
        if isinstance(mat,materials.Material):
            self.mat = mat
        else:
            raise TypeError("mat must be an instance of class Material")

        self.digits = 5 # number of significant digits, needed to identify equal floats

    def PowderIntensity(self):
        """
        Calculates the powder intensity and positions up to an angle of 180 deg
        and stores the result in:
            data .... array with intensities
            ang ..... angular position of intensities
            qpos .... reciprocal space position of intensities
        """
        
        # calculate maximal Bragg indices
        hmax = int(numpy.ceil(norm(self.mat.lattice.a1)*self.k0/numpy.pi))
        hmin = -hmax
        kmax = int(numpy.ceil(norm(self.mat.lattice.a2)*self.k0/numpy.pi))
        kmin = -kmax
        lmax = int(numpy.ceil(norm(self.mat.lattice.a3)*self.k0/numpy.pi))
        lmin = -lmax
        
        qlist = []
        qabslist = []
        hkllist = []
        # calculate structure factor for each reflex
        for h in range(hmin,hmax+1):
            for k in range(kmin,kmax+1):
                for l in range(lmin,lmax+1):
                    q = self.mat.rlattice.GetPoint(h,k,l)
                    if norm(q)<2*self.k0:
                        qlist.append(q)
                        hkllist.append([h,k,l])
                        qabslist.append(numpy.round(norm(q),self.digits))
        
        qabs = numpy.array(qabslist,dtype=numpy.double)
        s = self.mat.lattice.StructureFactorForQ(self.energy,qlist)
        r = numpy.absolute(s)**2

        _tmp_data = numpy.zeros(r.size,dtype=[('q',numpy.double),('r',numpy.double),('hkl',list)])
        _tmp_data['q'] = qabs
        _tmp_data['r'] = r
        _tmp_data['hkl'] = hkllist
        # sort the list and compress equal entries
        _tmp_data.sort(order='q')

        self.qpos = [0]
        self.data = [0]
        self.hkl = [[0,0,0]]
        for r in _tmp_data:
            if r[0] == self.qpos[-1]:
                self.data[-1] += r[1]
            elif numpy.round(r[1],self.digits) != 0.:
                self.qpos.append(r[0])
                self.data.append(r[1])
                self.hkl.append(r[2])

        # cat first element to get rid of q = [0,0,0] divergence
        self.qpos = numpy.array(self.qpos[1:],dtype=numpy.double)
        self.ang = self.Q2Ang(self.qpos)  
        self.data = numpy.array(self.data[1:],dtype=numpy.double)
        self.hkl = self.hkl[1:]

        # correct data for polarization and lorentzfactor and unit cell volume
        # and also include Debye-Waller factor for later implementation
        # see L.S. Zevin : Quantitative X-Ray Diffractometry 
        # page 18ff
        polarization_factor = (1+numpy.cos(numpy.radians(2*self.ang))**2)/2.
        lorentz_factor = 1./(numpy.sin(numpy.radians(self.ang))**2*numpy.cos(numpy.radians(self.ang)))
        B=0 # do not have B data yet: they need to be implemented in lattice base class and feeded by the material initialization also the debye waller factor needs to be included there and not here
        debye_waller_factor = numpy.exp(-2*B*numpy.sin(numpy.radians(self.ang))**2/self._wl**2)
        unitcellvol = self.mat.lattice.UnitCellVolume()
        self.data = self.data * polarization_factor * lorentz_factor / unitcellvol**2

    def Convolute(self,stepwidth,width,min=0,max=None):
        """
        Convolutes the intensity positions with Gaussians with width in momentum space 
        of "width". returns array of angular positions with corresponding intensity
            theta ... array with angular positions
            int ..... intensity at the positions ttheta
        """
        
        if not max: max= 2*self.k0
        # define a gaussion which is needed for convolution
        def gauss(amp,x0,sigma,x):
            return amp*numpy.exp(-(x-x0)**2/(2*sigma**2))
        
        # convolute each peak with a gaussian and add them up
        qcoord = numpy.arange(min,max,stepwidth)
        theta = self.Q2Ang(qcoord)
        intensity = numpy.zeros(theta.size,dtype=numpy.double)
        
        for i in range(self.ang.size):
            intensity += gauss(self.data[i],self.qpos[i],width,qcoord)

        return theta,intensity

    def Ang2Q(self,th,deg=True):
        """
        Converts theta angles to reciprocal space positions 
        returns the absolute value of momentum transfer
        """
        if deg:
            lth = numpy.radians(th)
        else:
            lth = th

        qpos = 2*self.k0*numpy.sin(lth)
        return qpos

    def Q2Ang(self,qpos,deg=True):
        """
        Converts reciprocal space values to theta angles
        """
        th = numpy.arcsin(qpos/(2*self.k0))

        if deg:
            th= numpy.degrees(th)

        return th
    
    def __str__(self):
        """
        Prints out available information about the material and reflections
        """
        ostr = "\nPowder diffraction object \n"
        ostr += "-------------------------\n"
        ostr += "Material: "+ self.mat.name + "\n"
        ostr += "Lattice:\n" + self.mat.lattice.__str__()
        if self.qpos != None:
            max = self.data.max()
            ostr += "\nReflections: \n"
            ostr += "--------------\n"
            ostr += "      h k l     |    tth    |    |Q|    |    Int     |   Int (%)\n"
            ostr += "   ---------------------------------------------------------------\n"
            for i in range(self.qpos.size):
                ostr += "%15s   %8.4f   %8.3f   %10.2f  %10.2f\n" % (self.hkl[i].__str__(), 2*self.ang[i],self.qpos[i],self.data[i], self.data[i]/max*100.)

        return ostr
    #}}}1        

    

