import numpy

map_ijkl2ij = {"00":0,"11":1,"22":2,
               "12":3,"20":4,"01":5,
               "21":6,"02":7,"10":8}
map_ij2ijkl = {"0":[0,0],"1":[1,1],"2":[2,2],
        "3":[1,2],"4":[2,0],"5":[0,1],
        "6":[2,1],"7":[0,2],"8":[1,0]}

def index_map_ijkl2ij(i,j):
    return map_ijkl2ij["%i%i" %(i,j)] 

def index_map_ij2ijkl(ij):
    return map_ij2ijkl["%i" %ij]


def Cij2Cijkl(cij):
    #{{{1
    """
    Cij2Cijkl(cij):
    Converts the elastic constants matrix (tensor of rank 2) to 
    the full rank 4 cijkl tensor.

    required input arguments:
    cij ................ (6,6) cij matrix as a numpy array

    return value:
    cijkl .............. (3,3,3,3) cijkl tensor as numpy array
    """

    #first have to build a 9x9 matrix from the 6x6 one
    m = numpy.zeros((9,9),dtype=numpy.double)
    m[0:6,0:6] = cij[:,:]
    m[6:9,0:6] = cij[3:6,:]
    m[0:6,6:9] = cij[:,3:6]
    m[6:9,6:9] = cij[3:6,3:6]

    #now create the full tensor
    cijkl = numpy.zeros((3,3,3,3),dtype=numpy.double)

    for i in range(0,3):
        for j in range(0,3):
            for k in range(0,3):
                for l in range(0,3):
                    mi = index_map_ijkl2ij(i,j)
                    mj = index_map_ijkl2ij(k,l)
                    cijkl[i,j,k,l] = m[mi,mj]
    return cijkl
    #}}}1

def Cijkl2Cij(cijkl):
    #{{{1
    """
    Cijkl2Cij(cijkl):
    Converts the full rank 4 tensor of the elastic constants to 
    the (6,6) matrix of elastic constants.

    required input arguments:
    cijkl .............. (3,3,3,3) cijkl tensor as numpy array

    return value:
    cij ................ (6,6) cij matrix as a numpy array
    """
    
    #build the temporary 9x9 matrix
    m = numpy.zeros((9,9),dtype=numpy.double)

    for i in range(0,9):
        for j in range(0,9):
            ij = index_map_ij2ijkl(i)
            kl = index_map_ij2ijkl(j)
            m[i,j] = cijkl[ij[0],ij[1],kl[0],kl[1]]

    cij = m[0:6,0:6]

    return cij
    #}}}1


class Transform(object):
    def __init__(self,matrix):
        self.matrix = matrix
        try:
            self.imatrix = numpy.linalg.inv(matrix)
        except:
            print "matrix cannot be inverted - seems to be singular"
            self.imatrix = None

    def __call__(self,*args,**keyargs):
        """
        transforms a vector, matrix or tensor of rank 4 (e.g. elasticity tensor)

        Parameters
        ----------
         *args:     object to transform, list or numpy array of shape
                    (n,) (n,n), (n,n,n,n) where n is the rank of the 
                    transformation matrix
         **keyargs: optional keyword arguments:
          inverse:  flag telling if the inverse transformation should be applied 
                    (default: False)
        """

        m = self.matrix
        # parse keyword arguments
        if keyargs.has_key("inverse"):
            if keyargs["inverse"]:
                m = self.imatrix
        
        olist = []
        for a in args:
            if isinstance(a,list):
                p = numpy.array(a,dtype=numpy.double)
            elif isinstance(a,numpy.ndarray):
                p = a
            else:
                raise TypeError,"Argument must be a list or numpy array!"

            #matrix product in pure array notation
            if len(p.shape)==1:
                #argument is a vector
                print "transform a vector ..."
                #b = (self.matrix*p[numpy.newaxis,:]).sum(axis=1)
                b = numpy.dot(m,p)
                olist.append(b)
            elif len(p.shape)==2 and p.shape[0]==3 and p.shape[1]==3:
                #argument is a matrix
                print "transform a matrix ..."
                b = numpy.zeros(p.shape,dtype=numpy.double)
                # b_ij = m_ik * m_jl * p_kl
                for i in range(3):
                    for j in range(3):
                        #loop over the sums
                        for k in range(3):
                            for l in range(3):
                                b[i,j] += m[i,k] * m[j,l] * p[k,l]

                olist.append(b)

            elif len(p.shape)==4 and p.shape[0]==3 and p.shape[1]==3 and\
                 p.shape[2] == 3 and p.shape[3] == 3:
                print "transform a tensor"
                # transformation of a 
                cp = numpy.zeros(p.shape,dtype=numpy.double)
                # cp_ikkl = m_ig * m_jh * m_kr * m_ls * p_ghrs 
                for i in range(0,3):
                    for j in range(0,3):
                        for k in range(0,3):
                            for l in range(0,3):
                                #run over the double sums
                                for g in range(0,3):
                                    for h in range(0,3):
                                        for r in range(0,3):
                                            for s in range(0,3):
                                                cp[i,j,k,l] += m[i,g]*m[j,h]*m[k,r]*m[l,s]*p[g,h,r,s]

                olist.append(cp)
    
        if len(args) == 1:
            return olist[0]
        else:
            return olist

    def __str__(self):
        ostr = ""
        ostr += "Transformation matrix:\n"
        ostr += "%f %f %f\n" %(self.matrix[0,0],self.matrix[0,1],self.matrix[0,2])
        ostr += "%f %f %f\n" %(self.matrix[1,0],self.matrix[1,1],self.matrix[1,2])
        ostr += "%f %f %f\n" %(self.matrix[2,0],self.matrix[2,1],self.matrix[2,2])

        return ostr

def CoordinateTransform(v1,v2,v3):
    """
    CoordinateTransform(v1,v2,v3):
    Create a Transformation object which transforms a point into a new 
    coordinate frame. The new frame is determined by the three vectors
    v1, v2 and v3.

    required input arguments:
    v1 ............. list or numpy array with new base vector 1
    v2 ............. list or numpy array with new base vector 2 
    v2 ............. list or numpy array with new base vector 3

    return value:
    An instance of a Transform class
    """

    if isinstance(v1,list):
        e1 = numpy.array(v1,dtype=numpy.double)
    elif isinstance(v1,numpy.ndarray):
        e1 = v1
    else:
        raise TypeError,"vector must be a list or numpy array"
    
    if isinstance(v2,list):
        e2 = numpy.array(v2,dtype=numpy.double)
    elif isinstance(v2,numpy.ndarray):
        e2 = v2
    else:
        raise TypeError,"vector must be a list or numpy array"
    
    if isinstance(v3,list):
        e3 = numpy.array(v3,dtype=numpy.double)
    elif isinstance(v3,numpy.ndarray):
        e3 = v3
    else:
        raise TypeError,"vector must be a list or numpy array"

    #normalize base vectors
    e1 = e1/numpy.linalg.norm(e1)
    e2 = e2/numpy.linalg.norm(e2)
    e3 = e3/numpy.linalg.norm(e3)

    #assemble the transformation matrix
    m = numpy.array([e1,e2,e3])
    
    return Transform(m)

def XRotation(alpha,deg=True):
    """
    XRotation(alpha,deg=True):
    Returns a transform that represents a rotation about the x-axis 
    by an angle alpha. If deg=True the angle is assumed to be in 
    degree, otherwise the function expects radiants.
    """

    if deg:
        sina = numpy.sin(numpy.pi*alpha/180.)
        cosa = numpy.cos(numpy.pi*alpha/180.)
    else:
        sina = numpy.sin(alpha)
        cosa = numpy.cos(alpha)

    m = numpy.array([[1,0,0],[0,cosa,-sina],[0,sina,cosa]],dtype=numpy.double)
    return Transform(m)

def YRotation(alpha,deg=True):
    """
    YRotation(alpha,deg=True):
    Returns a transform that represents a rotation about the y-axis 
    by an angle alpha. If deg=True the angle is assumed to be in 
    degree, otherwise the function expects radiants.
    """

    if deg:
        sina = numpy.sin(numpy.pi*alpha/180.)
        cosa = numpy.cos(numpy.pi*alpha/180.)
    else:
        sina = numpy.sin(alpha)
        cosa = numpy.cos(alpha)

    m = numpy.array([[cosa,0,sina],[0,1,0],[-sina,0,cosa]],dtype=numpy.double)
    return Transform(m)

def ZRotation(alpha,deg=True):
    """
    ZRotation(alpha,deg=True):
    Returns a transform that represents a rotation about the z-axis 
    by an angle alpha. If deg=True the angle is assumed to be in 
    degree, otherwise the function expects radiants.
    """

    if deg:
        sina = numpy.sin(numpy.pi*alpha/180.)
        cosa = numpy.cos(numpy.pi*alpha/180.)
    else:
        sina = numpy.sin(alpha)
        cosa = numpy.cos(alpha)

    m = numpy.array([[cosa,-sina,0],[sina,cosa,0],[0,0,1]],dtype=numpy.double)
    return Transform(m)


