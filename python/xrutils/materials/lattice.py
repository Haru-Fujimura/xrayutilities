#module handling crystall lattice structures
#

import numpy
import database
from numpy.linalg import norm
from . import __path__
import atexit

_db = database.DataBase(__path__[0]+"/data/test.db")
_db.Open()

def _db_cleanup():
    _db.Close()

atexit.register(_db_cleanup)

class Atom(object):
    def __init__(self,name):
        self.name = name
        
        
    def f0(self,q):
        _db.SetMaterial(self.name)
        
        if isinstance(q,numpy.ndarray) or isinstance(q,list):
            d = numpy.zeros((len(q)),dtype=numpy.double)
            for i in range(len(q)):
                d[i] = _db.GetF0(q[i])
                
            return d
        else:
            return _db.GetF0(q)
                
    def f1(self,en):
        _db.SetMaterial(self.name)
        
        if isinstance(en,numpy.ndarray) or isinstance(en,list):
            d = numpy.zeros((len(en)),dtype=numpy.double)
            for i in range(len(en)):
                d[i] = _db.GetF1(en[i])
                
            return d
        else:
            return _db.GetF1(en)
        
    def f2(self,en):
        _db.SetMaterial(self.name)
        
        if isinstance(en,numpy.ndarray) or isinstance(en,list):
            d = numpy.zeros((len(en)),dtype=numpy.double)
            for i in range(len(en)):
                d[i] = _db.GetF2(en[i])
                
            return d
        else:
            return _db.GetF2(en)
        
    def __str__(self):
        return self.name
        



class LatticeBase(list):
    """
    The LatticeBase class implements a container for a set of 
    points that form the base of a crystal lattice. An instance of this class
    can be treated as a simple container object. 
    """
    def __init__(self,*args,**keyargs):
       list.__init__(self,*args,**keyargs) 

    def append(self,atom,pos):
        if not isinstance(atom,Atom):           
            raise TypeError,"atom must be an instance of class Atom"
            
        if isinstance(pos,list):
            pos = numpy.array(pos,dtype=numpy.double)
        elif isinstance(pos,numpy.ndarray):
            pos = pos
        else:
            raise TypeError,"Atom position must be array or list!"

        list.append(self,(atom,pos))


    def __setitem__(self,key,data):
        (atom,pos) = data
        if not isinstance(atom,Atom):
            raise TypeError,"atom must be an instance of class Atom!"
            
        if isinstance(pos,list):
            p = numpy.array(pos,dtype=numpy.double)
        elif isinstance(pos,numpy.ndarray):
            p = pos
        else:
            raise TypeError,"point must be a list or numpy array of shape (3)"

        list.__setitem__(self,key,(atom,p))

    def __str__(self):
        ostr = ""
        for i in range(list.__len__(self)):
            (atom,p) = list.__getitem__(self,i)
            
            ostr += "Base point %i: %s (%f %f %f)\n" %(i,atom.__str__(),p[0],p[1],p[2])

        return ostr
        
        
    

class Lattice(object):
    """
    class Lattice:
    This object represents a Bravais lattice. A lattice consists of a 
    base 
    """
    def __init__(self,a1,a2,a3,base=None):
        if isinstance(a1,list):
            self.a1 = numpy.array(a1,dtype=numpy.double)
        elif isinstance(a1,numpy.ndarray):
            self.a1 = a1
        else:
            raise TypeError,"a1 must be a list or a numpy array"

        if isinstance(a2,list):
            self.a2 = numpy.array(a2,dtype=numpy.double)
        elif isinstance(a1,numpy.ndarray):
            self.a2 = a2
        else:
            raise TypeError,"a2 must be a list or a numpy array"
        
        if isinstance(a3,list):
            self.a3 = numpy.array(a3,dtype=numpy.double)
        elif isinstance(a3,numpy.ndarray):
            self.a3 = a3
        else:
            raise TypeError,"a3 must be a list or a numpy array"
            
        if base!=None:
            if not isinstance(base,LatticeBase):
                raise TypeError,"lattice base must be an instance of class LatticeBase"
            else:
                self.base = base
        else:
            self.base = None

    def ApplyStrain(self,eps):
        """
        ApplyStrain(eps):
        Applies a certain strain on a lattice. The result is a change 
        in the base vectors. 

        requiered input arguments:
        eps .............. a 3x3 matrix independent strain components
        """

        if isinstance(eps,list):
            eps = numpy.array(eps,dtype=numpy.double)
        
        u1 = (eps*self.a1[numpy.newaxis,:]).sum(axis=1)
        self.a1 = self.a1 + u1
        u2 = (eps*self.a2[numpy.newaxis,:]).sum(axis=1)
        self.a2 = self.a2 + u2
        u3 = (eps*self.a3[numpy.newaxis,:]).sum(axis=1)
        self.a3 = self.a3 + u3


    def ReciprocalLattice(self):
        V = self.UnitCellVolume()
        p = 2.*numpy.pi/V
        b1 = p*numpy.cross(self.a2,self.a3)
        b2 = p*numpy.cross(self.a3,self.a1)
        b3 = p*numpy.cross(self.a1,self.a2)

        return Lattice(b1,b2,b3)

    def UnitCellVolume(self):
        V = numpy.dot(self.a3,numpy.cross(self.a1,self.a2))
        return V

    def GetPoint(self,*args):
        if len(args)<3:
            raise IndexError,"need 3 indices for the lattice point"

        return args[0]*self.a1+args[1]*self.a2+args[2]*self.a3

    def __str__(self):
        ostr = ""
        ostr += "a1 = (%f %f %f)\n" %(self.a1[0],self.a1[1],self.a1[2])
        ostr += "a2 = (%f %f %f)\n" %(self.a2[0],self.a2[1],self.a2[2])
        ostr += "a3 = (%f %f %f)\n" %(self.a3[0],self.a3[1],self.a3[2])
        
        if self.base:
            ostr += "Lattice base:\n"
            ostr += self.base.__str__()

        return ostr
            
    def StructureFactor(self,en,q):
        if isinstance(q,list):
            q = numpy.array(q,dtype=numpy.double)
        elif isinstance(q,numpy.ndarray):
            pass
        else:
            raise TypeError,"q must be a list or numpy array!"
            
        s = 0.+0.j
        for a,p in self.base:
            r = p[0]*self.a1+p[1]*self.a2+p[2]*self.a3
            f = a.f0(norm(q))+a.f1(en)+1.j*a.f2(en)                    
            s += f*numpy.exp(-1.j*numpy.dot(q,r))
            
        return s
        
    def StructureFactorForEnergy(self,en,q0):
        #for constant q
        if isinstance(q0,list):
            q = numpy.array(q0,dtype=numpy.double)
        elif isinstance(q,numpy.ndarray):
            q = q0
        else:
            raise TypeError,"q must be a list or numpy array!"
            
        if isinstance(en,list):
            en = numpy.array(en,dtype=numpy.double)
        elif isinstance(en,numpy.ndarray):
            pass
        else:
            raise TypeError,"Energy data must be provided as a list or numpy array!"
            
         # create list of different atoms and buffer the scattering factors
        atoms = []
        f = []
        types = []
        for at in self.base:
            try: 
                idx = atoms.index(at[0])
                types.append(idx)
            except ValueError:
                #add atom type to list and calculate the scattering factor
                types.append(len(atoms))
                f.append( at[0].f0(norm(q)) + at[0].f1(en) +1.j*at[0].f2(en) )
                atoms.append(at[0])
        
        s = 0.+0.j                
        for i in range(len(self.base)):
            p = self.base[i][1]
            r = p[0]*self.a1+p[1]*self.a2+p[2]*self.a3
            s += f[types[i]]*numpy.exp(-1.j*numpy.dot(q,r))
            
        return s
        
    def StructureFactorForQ(self,en0,q):
        #for constant energy
        if isinstance(q,list):
            q = numpy.array(q,dtype=numpy.double)
        elif isinstance(q,numpy.ndarray):
            pass
        else:
            raise TypeError,"q must be a list or numpy array!"
            
        # create list of different atoms and buffer the scattering factors
        atoms = []
        f = []
        types = []
        for at in self.base:
            try: 
                idx = atoms.index(at[0])
                types.append(idx)
            except ValueError:
                #add atom type to list and calculate the scattering factor
                types.append(len(atoms))
                f_q = numpy.zeros(len(q))
                for j in range(len(q)):
                    f_q[j] = at[0].f0(norm(q[j]))
                f.append( f_q + at[0].f1(en0) +1.j*at[0].f2(en0) )
                atoms.append(at[0])
        
        s = 0.+0.j                
        for i in range(len(self.base)):
            p = self.base[i][1]
            r = p[0]*self.a1+p[1]*self.a2+p[2]*self.a3
            s += f[types[i]]*numpy.exp(-1.j*numpy.dot(q,r))
            
        return s

# still a lot of overhead, because normaly we do have 2 different types of atoms in a 8 atom base, but we calculate all 8 times which is obviously not necessary. One would have to reorganize the things in the LatticeBase class, and introduce something like an atom type and than only store the type in the List.        
    
    
#some idiom functions to simplify lattice creation

def CubicLattice(a):
    """
    CubicLattice(a):
    Returns a Lattice object representing a simple cubic lattice.
    
    required input arguments:
    a ................ lattice parameter

    return value:
    an instance of  Lattice class
    """

    return Lattice([a,0,0],[0,a,0],[0,0,a])

#some lattice related functions

def ZincBlendeLattice(aa,ab,a):
    #{{{1 
    #create lattice base
    lb = LatticeBase()
    lb.append(aa,[0,0,0])
    lb.append(aa,[0.5,0.5,0])
    lb.append(aa,[0.5,0,0.5])
    lb.append(aa,[0,0.5,0.5])
    lb.append(ab,[0.25,0.25,0.25])
    lb.append(ab,[0.75,0.75,0.25])
    lb.append(ab,[0.75,0.25,0.75])
    lb.append(ab,[0.25,0.75,0.75])
    
    #create lattice vectors
    a1 = [a,0,0]
    a2 = [0,a,0]
    a3 = [0,0,a]
    
    l = Lattice(a1,a2,a3,base=lb)    
    
    return l
    #}}}1

def DiamondLattice(aa,a):
    #{{{1
    # Diamond is ZincBlende with two times the same atom
    return ZincBlendeLattice(aa,aa,a)
    #}}}1
    
def FCCLattice(aa,a):
    #{{{1
    #create lattice base
    lb = LatticeBase()
    lb.append(aa,[0,0,0])
    lb.append(aa,[0.5,0.5,0])
    lb.append(aa,[0.5,0,0.5])
    lb.append(aa,[0,0.5,0.5])
    
    #create lattice vectors
    a1 = [a,0,0]
    a2 = [0,a,0]
    a3 = [0,0,a]
    
    l = Lattice(a1,a2,a3,base=lb)

    return l
    #}}}1
    
def BCCLattice(aa,a):
    #{{{1
    #create lattice base
    lb = LatticeBase()
    lb.append(aa,[0,0,0])
    lb.append(aa,[0.5,0.5,0.5])

    #create lattice vectors
    a1 = [a,0,0]
    a2 = [0,a,0]
    a3 = [0,0,a]

    l = Lattice(a1,a2,a3,base=lb)

    return l
    #}}}1

def RockSaltLattice(aa,ab,a):
    #{{{1
    #create lattice base; data from http://cst-www.nrl.navy.mil/lattice/index.html
    print("Warning: NaCl lattice is not using a cubic lattice structure") 
    lb = LatticeBase()
    lb.append(aa,[0,0,0])
    lb.append(ab,[0.5,0.5,0.5])

    #create lattice vectors
    a1 = [0,0.5*a,0.5*a]
    a2 = [0.5*a,0,0.5*a]
    a3 = [0.5*a,0.5*a,0]

    l = Lattice(a1,a2,a3,base=lb)

    return l
    #}}}1

def RockSalt_Cubic_Lattice(aa,ab,a):
    #{{{1
    lb = LatticeBase()
    lb.append(aa,[0,0,0])
    lb.append(aa,[0.5,0.5,0])
    lb.append(aa,[0,0.5,0.5])
    lb.append(aa,[0.5,0,0.5])

    lb.append(ab,[0.5,0,0])
    lb.append(ab,[0,0.5,0])
    lb.append(ab,[0,0,0.5])
    lb.append(ab,[0.5,0.5,0.5])

    #create lattice vectors
    a1 = [a,0,0]
    a2 = [0,a,0]
    a3 = [0,0,a]

    l = Lattice(a1,a2,a3,base=lb)

    return l
    #}}}1

def RutileLattice(aa,ab,a,c,u):
    #{{{1
    #create lattice base; data from http://cst-www.nrl.navy.mil/lattice/index.html
    # P4_2/mmm(136) aa=2a,ab=4f; x \approx 0.305 (VO_2)
    lb = LatticeBase()
    lb.append(aa,[0,0,0])
    lb.append(aa,[0.5,0.5,0.5])
    lb.append(ab,[u,u,0.])
    lb.append(ab,[-u,-u,0.])
    lb.append(ab,[0.5+u,0.5-u,0.5])
    lb.append(ab,[0.5-u,0.5+u,0.5])

    #create lattice vectors
    a1 = [a,0.,0.]
    a2 = [0.,a,0.]
    a3 = [0.,0.,c]

    l = Lattice(a1,a2,a3,base=lb)

    return l
    #}}}1

def BaddeleyiteLattice(aa,ab,a,b,c,beta,deg=True):
    #{{{1
    #create lattice base; data from http://cst-www.nrl.navy.mil/lattice/index.html
    # P2_1/c(14), aa=4e,ab=2*4e  
    lb = LatticeBase()
    lb.append(aa,[0.242,0.975,0.025])
    lb.append(aa,[-0.242,0.975+0.5,-0.025+0.5])
    lb.append(aa,[-0.242,-0.975,-0.025])
    lb.append(aa,[0.242,-0.975+0.5,0.025+0.5])
    
    lb.append(ab,[0.1,0.21,0.20])
    lb.append(ab,[-0.1,0.21+0.5,-0.20+0.5])
    lb.append(ab,[-0.1,-0.21,-0.20])
    lb.append(ab,[0.1,-0.21+0.5,0.20+0.5])

    lb.append(ab,[0.39,0.69,0.29])
    lb.append(ab,[-0.39,0.69+0.5,-0.29+0.5])
    lb.append(ab,[-0.39,-0.69,-0.29])
    lb.append(ab,[0.39,-0.69+0.5,0.29+0.5])

    #create lattice vectors
    d2r= numpy.pi/180.
    if deg: beta=beta*d2r
    a1 = numpy.array([a,0.,0.],dtype=numpy.double)
    a2 = numpy.array([0.,b,0.],dtype=numpy.double)
    a3 = numpy.array([c*numpy.cos(beta),0.,c*numpy.sin(beta)],dtype=numpy.double)
    l = Lattice(a1,a2,a3,base=lb)

    return l
    #}}}1



