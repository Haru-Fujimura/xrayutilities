# This file is part of xrayutilities.
#
# xrayutilities is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
#
# Copyright (C) 2009 Eugen Wintersberger <eugen.wintersberger@desy.de>
# Copyright (C) 2009-2012 Dominik Kriegner <dominik.kriegner@gmail.com>
# Copyright (C) 2012 Tanja Etzelstorfer <tanja.etzelstorfer@jku.at>

"""
class module implements a certain material
"""

import copy
import numpy
import scipy.optimize
import warnings

from . import lattice
from . import elements
from .. import math
from .. import utilities
from .. import config
from ..exception import InputError

map_ijkl2ij = {"00":0,"11":1,"22":2,
               "12":3,"20":4,"01":5,
               "21":6,"02":7,"10":8}
map_ij2ijkl = {"0":[0,0],"1":[1,1],"2":[2,2],
        "3":[1,2],"4":[2,0],"5":[0,1],
        "6":[2,1],"7":[0,2],"8":[1,0]}

_epsilon = 1e-7 # small number (should be saved somewhere more global but is needed)

def index_map_ijkl2ij(i,j):
    return map_ijkl2ij["%i%i" %(i,j)]

def index_map_ij2ijkl(ij):
    return map_ij2ijkl["%i" %ij]


def Cij2Cijkl(cij):
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

def Cijkl2Cij(cijkl):
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

class Material(object):
    def __init__(self,name,lat,cij=None,thetaDebye=None):
        if cij==None:
            self.cij = numpy.zeros((6,6),dtype=numpy.double)
        elif isinstance(cij,list):
            self.cij = numpy.array(cij,dtype=numpy.double)
        elif isinstance(cij,numpy.ndarray):
            self.cij = cij
        else:
            raise TypeError("Elastic constants must be a list or numpy array!")

        self.name = name
        self.lattice = lat
        self.rlattice = lat.ReciprocalLattice()
        self.cijkl = Cij2Cijkl(self.cij)
        self.transform = None
        if numpy.isscalar(thetaDebye):
            self.thetaDebye = float(thetaDebye)
        else:
            self.thetaDebye = thetaDebye


    def __getattr__(self,name):
        if name.startswith("c"):
            index = name[1:]
            if len(index)>2:
                raise AttributeError("Cij indices must be between 1 and 6")

            i=int(index[0])
            j=int(index[1])

            if i>6 or i<1 or j>6 or j<1:
                raise AttributeError("Cij indices must be between 1 and 6")

            if self.transform:
                cij = self.transform(self.cij)
            else:
                cij = self.cij

            return cij[i-1,j-1]

    def _getmu(self):
        return self.cij[3,3]

    def _getlam(self):
        return self.cij[0,1]

    def _getnu(self):
        return self.lam/2./(self.mu+self.lam)

    def _geta1(self):
        return self.lattice.a1

    def _geta2(self):
        return self.lattice.a2

    def _geta3(self):
        return self.lattice.a3

    def _getb1(self):
        return self.rlattice.a1

    def _getb2(self):
        return self.rlattice.a2

    def _getb3(self):
        return self.rlattice.a3

    mu  = property(_getmu)
    lam = property(_getlam)
    nu  = property(_getnu)
    a1 = property(_geta1)
    a2 = property(_geta2)
    a3 = property(_geta3)
    b1 = property(_getb1)
    b2 = property(_getb2)
    b3 = property(_getb3)


    def Q(self,*hkl):
        """
        Q(hkl):
        Return the Q-space position for a certain material.

        required input arguments:
        hkl ............. list or numpy array with the Miller indices
                          ( or Q(h,k,l) is also possible)

        """
        if len(hkl)<3:
            hkl = hkl[0]
            if len(hkl)<3:
                raise InputError("need 3 indices for the lattice point")

        p = self.rlattice.GetPoint(hkl[0],hkl[1],hkl[2])
        if self.transform: p = self.transform(p)

        return p

    def delta(self,en="config"):
        """
        function to calculate the real part of the deviation of the
        refractive index from 1 (n=1-delta+i*beta)

        Parameter
        ---------
         en:    x-ray energy eV,
                if omitted the value from the xrutils configuration is used

        Returns
        -------
         delta (float)
        """

        r_e = 2.8179402894e-15 * 1e10 # angstrom (classical electron radius) r_e = 1/(4pi*eps_0)*e^2/(m_e*c^2)

        if en=="config":
            en = utilities.energy(config.ENERGY)

        lam = utilities.lam2en(en)
        delta = 0.

        for atpos in self.lattice.base:
            at = atpos[0]
            delta += numpy.real(at.f(0.,en))

        delta *= r_e/(2*numpy.pi)*lam**2/self.lattice.UnitCellVolume()
        return delta

    def beta(self,en="config"):
        """
        function to calculate the imaginary part of the deviation
        of the refractive index from 1 (n=1-delta+i*beta)

        Parameter
        ---------
         en:    x-ray energy eV,
                if omitted the value from the xrutils configuration is used

        Returns
        -------
         beta (float)
        """

        r_e = 1/(4*numpy.pi*scipy.constants.epsilon_0)*scipy.constants.e**2/(scipy.constants.electron_mass*scipy.constants.speed_of_light**2)*1e10
        # angstrom (classical electron radius) r_e = 1/(4pi*eps_0)*e^2/(m_e*c^2)
        if en=="config":
            en = utilities.energy(config.ENERGY)

        lam = utilities.lam2en(en)
        beta = 0.

        for atpos in self.lattice.base:
            at = atpos[0]
            beta += numpy.imag(at.f(0.,en))

        beta *= r_e/(2*numpy.pi)*lam**2/self.lattice.UnitCellVolume()
        return beta

    def chih(self,q,en="config",temp=0,polarization='S'):
        """
        calculates the complex polarizability of a material for a certain
        momentum transfer and energy

        Parameter
        ---------
         q:     momentum transfer in (1/A)
         en:    xray energy in eV,
                if omitted the value from the xrutils configuration is used
         temp:  temperature used for Debye-Waller-factor calculation
         polarization:  either 'S' (default) sigma or 'P' pi polarization

        Returns
        -------
         (abs(chih_real),abs(chih_imag)) complex polarizability
        """

        if isinstance(q,(list,tuple)):
            q = numpy.array(q,dtype=numpy.double)
        elif isinstance(q,numpy.ndarray):
            pass
        else:
            raise TypeError("q must be a list or numpy array!")

        if en=="config":
            en = utilities.energy(config.ENERGY)

        if self.lattice.base==None:
            return (0,0)

        #Debye Waller factor calculation
        if temp!=0 and self.thetaDebye:
            # W(q) = 3/2* hbar^2*q^2/(m*kB*tD) * (D1(tD/T)/(tD/T) + 1/4)
            # DWF = exp(-W(q)) consistent with Vaclav H. and several books
            # -> do not trust Wikipedia!?
            hbar = scipy.constants.hbar
            kb = scipy.constants.Boltzmann
            x = self.thetaDebye/float(temp)
            m = 0.
            for a,p,o,b in self.lattice.base:
                m += a.weight
            m = m/len(self.lattice.base)
            exponentf = 3/2.*hbar**2*1.0e20/(m*kb*self.thetaDebye) * ( math.Debye1(x)/x + 0.25)
            if config.VERBOSITY >= config.DEBUG:
                print("XU.materials.StructureFactor: DWF = exp(-W*q**2) W= %g"%exponentf)
            dwf = numpy.exp(-exponentf*math.VecNorm(q)**2)
        else:
            dwf = 1.0

        sr = 0.+0.j
        si = 0.+0.j
        for a,p,o,b in self.lattice.base: # a: atom, p: position, o: occupancy, b: temperatur-factor
            r = self.lattice.GetPoint(p)
            if temp==0:
                dwf = numpy.exp(-b*math.VecNorm(q)**2/(4*numpy.pi)**2)
            fr = numpy.real(a.f(q,en))*o
            fi = numpy.imag(a.f(q,en))*o
            sr += fr*numpy.exp(-1.j*math.VecDot(q,r))*dwf
            si += fi*numpy.exp(-1.j*math.VecDot(q,r))*dwf


        #classical electron radius
        r_e = 1/(4*numpy.pi*scipy.constants.epsilon_0)*scipy.constants.e**2/(scipy.constants.electron_mass*scipy.constants.speed_of_light**2)*1e10
        lam = utilities.lam2en(en)

        f = -lam**2*r_e/(numpy.pi*self.lattice.UnitCellVolume())
        rchi = numpy.abs(f*sr)
        ichi = numpy.abs(f*si)

        return rchi,ichi

    def chi0(self,en="config"):
        """
        calculates the complex chi_0 values often needed in simulations.
        They are closely related to delta and beta
        (n = 1 + chi_r0/2 + i*chi_i0/2   vs.  n = 1 - delta + i*beta)
        """
        return (-2*self.delta(en)+2j*self.beta(en))

    def idx_refraction(self,en="config"):
        """
        function to calculate the complex index of refraction of a material
        in the x-ray range

        Parameter
        ---------
         en:    energy of the x-rays,
                if omitted the value from the xrutils configuration is used

        Returns
        -------
         n (complex)
        """
        n = 1. - self.delta(en) + 1.j*self.beta(en)
        return n

    def critical_angle(self,en="config",deg=True):
        """
        calculate critical angle for total external reflection

        Parameter
        ---------
         en:    energy of the x-rays,
                if omitted the value from the xrutils configuration is used
         deg:   return angle in degree if True otherwise radians (default:True)

        Returns
        -------
         Angle of total external reflection

        """
        rn = 1. - self.delta(en)

        alphac = numpy.arccos(rn)
        if deg:
            alphac = numpy.degrees(alphac)

        return alphac

    def dTheta(self,Q,en="config"):
        """
        function to calculate the refractive peak shift

        Parameter
        ---------
         Q:     momentum transfer (1/A)
         en:    x-ray energy (eV),
                if omitted the value from the xrutils configuration is used

        Returns
        -------
         deltaTheta: peak shift in degree
        """

        if en=="config":
            en = utilities.energy(config.ENERGY)
        lam = utilities.lam2en(en)
        dth = numpy.degrees(2*self.delta(en)/numpy.sin(2*numpy.arcsin(lam*numpy.linalg.norm(Q)/(4*numpy.pi))))
        return dth

    def __str__(self):
        ostr ="Material: %s\n" %self.name
        ostr += "Elastic constants:\n"
        ostr += "c11 = %e\n" %self.c11
        ostr += "c12 = %e\n" %self.c12
        ostr += "c44 = %e\n" %self.c44
        ostr += "mu  = %e\n" %self.mu
        ostr += "lam = %e\n" %self.lam
        ostr += "nu  = %e\n" %self.nu
        ostr += "Lattice:\n"
        ostr += self.lattice.__str__()
        ostr += "Reciprocal lattice:\n"
        ostr += self.rlattice.__str__()

        return ostr

    def StructureFactor(self,q,en="config",temp=0):
        """
        caluclates the structure factor of a material
        for a certain momentum transfer and energy
        at a certain temperature of the material

        Parameter
        ---------
         q:     vectorial momentum transfer (vectors as list,tuple
                or numpy array are valid)
         en:    energy in eV,
                if omitted the value from the xrutils configuration is used
         temp:  temperature used for Debye-Waller-factor calculation

        Returns
        -------
         the complex structure factor
        """

        if isinstance(q,(list,tuple)):
            q = numpy.array(q,dtype=numpy.double)
        elif isinstance(q,numpy.ndarray):
            pass
        else:
            raise TypeError("q must be a list or numpy array!")

        if en=="config":
            en = utilities.energy(config.ENERGY)

        if self.lattice.base==None: return 1.

        #Debye Waller factor calculation
        if temp!=0 and self.thetaDebye:
            # W(q) = 3/2* hbar^2*q^2/(m*kB*tD) * (D1(tD/T)/(tD/T) + 1/4)
            # DWF = exp(-W(q)) consistent with Vaclav H. and several books
            # -> do not trust Wikipedia!?
            hbar = scipy.constants.hbar
            kb = scipy.constants.Boltzmann
            x = self.thetaDebye/float(temp)
            m = 0.
            for a,p,o,b in self.lattice.base:
                m += a.weight
            m = m/len(self.lattice.base)
            exponentf = 3/2.*hbar**2*1.0e20/(m*kb*self.thetaDebye) * ( math.Debye1(x)/x + 0.25)
            if config.VERBOSITY >= config.DEBUG:
                print("XU.materials.StructureFactor: DWF = exp(-W*q**2) W= %g"%exponentf)
            dwf = numpy.exp(-exponentf*math.VecNorm(q)**2)
        else:
            dwf = 1.0

        s = 0.+0.j
        for a,p,o,b in self.lattice.base: # a: atom, p: position, o: occupancy, b: temperatur-factor
            r = self.lattice.GetPoint(p)
            if temp==0:
                dwf = numpy.exp(-b*math.VecNorm(q)**2/(4*numpy.pi)**2)
            f = a.f(q,en)*o
            s += f*numpy.exp(-1.j*math.VecDot(q,r))*dwf

        return s

    def StructureFactorForEnergy(self,q0,en,temp=0):
        """
        caluclates the structure factor of a material
        for a certain momentum transfer and a bunch of energies

        Parameter
        ---------
         q0:    vectorial momentum transfer (vectors as list,tuple
                or numpy array are valid)
         en:    list, tuple or array of energy values in eV
         temp:  temperature used for Debye-Waller-factor calculation

        Returns
        -------
         complex valued structure factor array
        """
        if isinstance(q0,(list,tuple)):
            q = numpy.array(q0,dtype=numpy.double)
        elif isinstance(q0,numpy.ndarray):
            q = q0
        else:
            raise TypeError("q must be a list or numpy array!")
        qnorm = math.VecNorm(q)

        if isinstance(en,(list,tuple)):
            en = numpy.array(en,dtype=numpy.double)
        elif isinstance(en,numpy.ndarray):
            pass
        else:
            raise TypeError("Energy data must be provided as a list or numpy array!")

        if self.lattice.base==None: return numpy.ones(len(en))

        #Debye Waller factor calculation
        if temp!=0 and self.thetaDebye:
            # W(q) = 3/2* hbar^2*q^2/(m*kB*tD) * (D1(tD/T)/(tD/T) + 1/4)
            # DWF = exp(-W(q)) consistent with Vaclav H. and several books
            # -> do not trust Wikipedia!?
            hbar = scipy.constants.hbar
            kb = scipy.constants.Boltzmann
            x = self.thetaDebye/float(temp)
            m = 0.
            for a,p,o,b in self.lattice.base:
                m += a.weight
            m = m/len(self.lattice.base)
            exponentf = 3/2.*hbar**2*1.0e20/(m*kb*self.thetaDebye) * ( math.Debye1(x)/x + 0.25)
            if config.VERBOSITY >= config.DEBUG:
                print("XU.materials.StructureFactor: DWF = exp(-W*q**2) W= %g"%exponentf)
            dwf = numpy.exp(-exponentf*qnorm**2)
        else:
            dwf = 1.0

         # create list of different atoms and buffer the scattering factors
        atoms = []
        f = []
        types = []
        for at in self.lattice.base:
            try:
                idx = atoms.index(at[0])
                types.append(idx)
            except ValueError:
                #add atom type to list and calculate the scattering factor
                types.append(len(atoms))
                f.append( at[0].f(qnorm,en) )
                atoms.append(at[0])

        s = 0.+0.j
        for i in range(len(self.lattice.base)):
            a,p,o,b = self.lattice.base[i]
            if temp==0:
                dwf = numpy.exp(-b*qnorm**2/(4*numpy.pi)**2)
            r = self.lattice.GetPoint(p)
            s += f[types[i]]*o*dwf*numpy.exp(-1.j*math.VecDot(q,r))

        return s

    def StructureFactorForQ(self,q,en0="config",temp=0):
        """
        caluclates the structure factor of a material
        for a bunch of momentum transfers and a certain energy

        Parameter
        ---------
         q:     vectorial momentum transfers;
                list of vectores (list, tuple or array) of length 3
                e.g.: (Si.Q(0,0,4),Si.Q(0,0,4.1),...) or
                 numpy.array([Si.Q(0,0,4),Si.Q(0,0,4.1)])
         en0:   energy value in eV,
                if omitted the value from the xrutils configuration is used
         temp:  temperature used for Debye-Waller-factor calculation

        Returns
        -------
         complex valued structure factor array
        """
        if isinstance(q,(list,tuple)):
            q = numpy.array(q,dtype=numpy.double)
        elif isinstance(q,numpy.ndarray):
            pass
        else:
            raise TypeError("q must be a list or numpy array!")
        if len(q.shape) != 2:
            raise ValueError("q does not have the correct shape (shape = %s)" %str(q.shape))
        qnorm = numpy.zeros(len(q))
        for j in range(len(q)):
            qnorm[j] = numpy.linalg.norm(q[j])

        if en0=="config":
            en0 = utilities.energy(config.ENERGY)

        if self.lattice.base==None: return numpy.ones(len(q))

        #Debye Waller factor calculation
        if temp!=0 and self.thetaDebye:
            # W(q) = 3/2* hbar^2*q^2/(m*kB*tD) * (D1(tD/T)/(tD/T) + 1/4)
            # DWF = exp(-W(q)) consistent with Vaclav H. and several books
            # -> do not trust Wikipedia!?
            hbar = scipy.constants.hbar
            kb = scipy.constants.Boltzmann
            x = self.thetaDebye/float(temp)
            m = 0.
            for a,p,o,b in self.lattice.base:
                m += a.weight
            m = m/len(self.lattice.base)
            exponentf = 3/2.*hbar**2*1.0e20/(m*kb*self.thetaDebye) * ( math.Debye1(x)/x + 0.25)
            if config.VERBOSITY >= config.DEBUG:
                print("XU.materials.StructureFactor: DWF = exp(-W*q**2) W= %g"%exponentf)
        else:
            exponentf = 1.0

        # create list of different atoms and buffer the scattering factors
        atoms = []
        f = []
        types = []
        for at in self.lattice.base:
            try:
                idx = atoms.index(at[0])
                types.append(idx)
            except ValueError:
                #add atom type to list and calculate the scattering factor
                types.append(len(atoms))
                f_q = at[0].f0(qnorm)
                f.append( (f_q + at[0].f1(en0) +1.j*at[0].f2(en0)) )
                atoms.append(at[0])

        s = 0.+0.j
        for i in range(len(self.lattice.base)):
            a,p,o,b = self.lattice.base[i]

            if temp!=0 and self.thetaDebye:
                dwf = numpy.exp(-exponentf*qnorm**2)
            else:
                dwf = numpy.exp(-b*qnorm**2/(4*numpy.pi)**2)

            r = self.lattice.GetPoint(p)
            s += f[types[i]]*o*numpy.exp(-1.j*numpy.dot(q,r))*dwf

        return s
        # still a lot of overhead, because normally we do have 2 different types of atoms in a 8 atom base, but we calculate all 8 times which is obviously not necessary. One would have to reorganize the things in the LatticeBase class, and introduce something like an atom type and than only store the type in the List.

    def ApplyStrain(self,strain,**keyargs):
        #let strain act on the base vectors
        self.lattice.ApplyStrain(strain)
        #recalculate the reciprocal lattice
        self.rlattice = self.lattice.ReciprocalLattice()

    def GetMismatch(self,mat):
        """
        Calculate the mismatch strain between the material and a second
        material
        """
        raise NotImplementedError("XU.material.GetMismatch: not implemented yet")


def CubicElasticTensor(c11,c12,c44):
    """
    Assemble the 6x6 matrix of elastic constants for a cubic material from the
    three independent components of a cubic crystal

    Parameter
    ---------
     c11,c12,c44:   independent components of the elastic tensor of cubic materials

    Returns
    -------
     6x6 materix with elastic constants
    """
    m = numpy.zeros((6,6),dtype=numpy.double)
    m[0,0] = c11; m[1,1] = c11; m[2,2] = c11
    m[3,3] = c44; m[4,4] = c44; m[5,5] = c44
    m[0,1] = m[0,2] = c12
    m[1,0] = m[1,2] = c12
    m[2,0] = m[2,1] = c12

    return m

def HexagonalElasticTensor(c11,c12,c13,c33,c44):
    """
    Assemble the 6x6 matrix of elastic constants for a hexagonal material from
    the five independent components of a hexagonal crystal

    Parameter
    ---------
     c11,c12,c13,c33,c44:   independent components of the elastic tensor of
                            a hexagonal material

    Returns
    -------
     6x6 materix with elastic constants

    """
    m = numpy.zeros((6,6),dtype=numpy.double)
    m[0,0] = m[1,1] = c11
    m[2,2] = c33
    m[3,3] = m[4,4] = c44
    m[5,5] = 0.5*(c11-c12)
    m[0,1] = m[1,0] = c12
    m[0,2] = m[1,2] = m[2,0] = m[2,1] = c12

    return m


# define general material usefull for peak position calculations
def GeneralUC(a=4,b=4,c=4,alpha=90,beta=90,gamma=90,name="General"):
    return Material(name,GeneralBasicLattice(a,b,c,alpha,beta,gamma))  

#calculate some predefined materials
# PLEASE use N/m^2 as unit for cij for newly entered material ( 1 dyn/cm^2 = 0.1 N/m^2 = 0.1 GPa)
# Use Kelvin as unit for the Debye temperature
Si = Material("Si",lattice.DiamondLattice(elements.Si,5.43104),
                   CubicElasticTensor(165.77e+9,63.93e+9,79.62e+9),thetaDebye=640)
Ge = Material("Ge",lattice.DiamondLattice(elements.Ge,5.65785),
                   CubicElasticTensor(128.5e+9,48.3e+9,66.8e+9),thetaDebye=374)
InAs = Material("InAs",lattice.ZincBlendeLattice(elements.In,elements.As,6.0583),
                   CubicElasticTensor(8.34e+10,4.54e+10,3.95e+10),thetaDebye=280)
InP  = Material("InP",lattice.ZincBlendeLattice(elements.In,elements.P,5.8687),
                   CubicElasticTensor(10.11e+10,5.61e+10,4.56e+10),thetaDebye=425)
InSb  = Material("InSb",lattice.ZincBlendeLattice(elements.In,elements.Sb,6.47937),
                   CubicElasticTensor(6.66e+10,3.65e+10,3.02e+10),thetaDebye=160)
GaP  = Material("GaP",lattice.ZincBlendeLattice(elements.Ga,elements.P,5.4505),
                   CubicElasticTensor(14.05e+10,6.20e+10,7.03e+10),thetaDebye=445)
GaAs = Material("GaAs",lattice.ZincBlendeLattice(elements.Ga,elements.As,5.65325),
                   CubicElasticTensor(11.9e+10,5.34e+10,5.96e+10),thetaDebye=360)
GaSb = Material("GaSb",lattice.ZincBlendeLattice(elements.Ga,elements.Sb,6.09593),
                   CubicElasticTensor(8.83e+10,4.02e+10,4.32e+10),thetaDebye=266)
CdTe = Material("CdTe",lattice.ZincBlendeLattice(elements.Cd,elements.Te,6.482),
                   CubicElasticTensor(53.5,36.7,19.9)) # ? Unit of elastic constants
CdSe = Material("CdSe",lattice.WurtziteLattice(elements.Cd,elements.Se,4.300,7.011),
                   HexagonalElasticTensor(7.490e10,4.609e10,3.926e10,8.451e10,1.315e10))
CdSe_ZB = Material("CdSe ZB",lattice.ZincBlendeLattice(elements.Cd,elements.Se,6.052))
HgSe = Material("HgSe",lattice.ZincBlendeLattice(elements.Hg,elements.Se,6.085),
                   CubicElasticTensor(6.1e10,4.4e10,2.2e10))
PbTe = Material("PbTe",lattice.RockSalt_Cubic_Lattice(elements.Pb,elements.Te,6.464),
                   CubicElasticTensor(93.6,7.7,13.4))
PbSe = Material("PbSe",lattice.RockSalt_Cubic_Lattice(elements.Pb,elements.Se,6.128),
                   CubicElasticTensor(123.7,19.3,15.9))
GaN = Material("GaN",lattice.WurtziteLattice(elements.Ga,elements.N,3.189,5.186),
                   HexagonalElasticTensor(390.e9,145.e9,106.e9,398.e9,105.e9),thetaDebye=600)
BaF2 = Material("BaF2",lattice.CubicFm3mBaF2(elements.Ba,elements.F,6.2001))
Al = Material("Al",lattice.FCCLattice(elements.Al,4.04958))
Au = Material("Au",lattice.FCCLattice(elements.Au,4.0782))
V = Material("V",lattice.BCCLattice(elements.V,3.024))
Ag2Se = Material("Ag2Se",lattice.NaumanniteLattice(elements.Ag,elements.Se,4.333,7.062,7.764))
VO2_Rutile = Material("VO_2",lattice.RutileLattice(elements.V,elements.O,4.55,2.88,0.305))
VO2_Baddeleyite = Material("VO_2",lattice.BaddeleyiteLattice(elements.V,elements.O,5.75,5.42,5.38,122.6))
SiO2 = Material("SiO_2",lattice.QuartzLattice(elements.Si,elements.O,4.916,4.916,5.4054))
In = Material("In",lattice.TetragonalIndiumLattice(elements.In,3.2523,4.9461))
Sb = Material("Sb",lattice.TrigonalR3mh(elements.Sb,4.307,11.273))
Sn = Material("Sn",lattice.TetragonalTinLattice(elements.Sn,5.8197,3.17488))
SnAlpha = Material("Sn-alpha",lattice.DiamondLattice(elements.Sn,6.4912))
Cu = Material("Cu",lattice.FCCLattice(elements.Cu,3.61496))
CuMnAs = Material("CuMnAs",lattice.CuMnAsLattice(elements.Cu,elements.Mn,elements.As,3.82,3.82,6.30))
CaTiO3 = Material("CaTiO3",lattice.PerovskiteTypeRhombohedral(elements.Ca,elements.Ti,elements.O,3.795,90))
BiFeO3 = Material("BiFeO3",lattice.PerovskiteTypeRhombohedral(elements.Bi,elements.Fe,elements.O,3.965,89.3))

class Alloy(Material):
    def __init__(self,matA,matB,x):
        Material.__init__(self,"None",copy.copy(matA.lattice),matA.cij)
        self.matA = matA
        self.matB = matB
        self.xb = 0
        self._setxb(x)

    def lattice_const_AB(self, latA, latB, x):
        return (latB-latA)*x + latA

    def _getxb(self):
        return self.xb

    def _setxb(self,x):
        self.xb = x
        self.name = "%s(%2.2f)%s(%2.2f)" %(self.matA.name,1.-x,self.matB.name,x)
        #modify the lattice
        self.lattice.a1 = self.lattice_const_AB(self.matA.lattice.a1, self.matB.lattice.a1, x)
        self.lattice.a2 = self.lattice_const_AB(self.matA.lattice.a2, self.matB.lattice.a2, x)
        self.lattice.a3 = self.lattice_const_AB(self.matA.lattice.a3, self.matB.lattice.a3, x)
        self.rlattice = self.lattice.ReciprocalLattice()

        #set elastic constants
        self.cij = (self.matB.cij-self.matA.cij)*x+self.matA.cij
        self.cijkl = (self.matB.cijkl-self.matA.cijkl)*x+self.matA.cijkl

    x = property(_getxb,_setxb)

    def RelaxationTriangle(self,hkl,sub,exp):
        """
        function which returns the relaxation trianlge for a
        Alloy of given composition. Reciprocal space coordinates are
        calculated using the user-supplied experimental class

        Parameter
        ---------
        hkl : Miller Indices
        sub : substrate material or lattice constant (Instance of Material class or float)
        exp : Experiment class from which the Transformation object and ndir are needed

        Returns
        -------
        qy,qz : reciprocal space coordinates of the corners of the relaxation triangle

        """
        if isinstance(hkl,(list,tuple,numpy.ndarray)):
            hkl = numpy.array(hkl,dtype=numpy.double)
        else:
            raise TypeError("First argument (hkl) must be of type list, tuple or numpy.ndarray")
        #if not isinstance(exp,xrutils.Experiment):
        #    raise TypeError("Third argument (exp) must be an instance of xrutils.Experiment")
        transform =exp.Transform
        ndir =exp.ndir/numpy.linalg.norm(exp.ndir)

        if isinstance(sub,Material):
            asub = numpy.linalg.norm(sub.lattice.a1)
        elif isinstance(sub,float):
            asub = sub
        else:
            raise TypeError("Second argument (sub) must be of type float or an instance of xrutils.materials.Material")

        # test if inplane direction of hkl is the same as the one for the experiment otherwise warn the user
        hklinplane = numpy.cross(numpy.cross(exp.ndir,hkl),exp.ndir)
        if (numpy.linalg.norm(numpy.cross(hklinplane,exp.idir)) > _epsilon):
            warnings.warn("Alloy: given hkl differs from the geometry of the Experiment instance in the azimuthal direction")

        # calculate relaxed points for matA and matB as general as possible:
        a1 = lambda x: self.lattice_const_AB(self.matA.lattice.a1, self.matB.lattice.a1, x)
        a2 = lambda x: self.lattice_const_AB(self.matA.lattice.a2, self.matB.lattice.a2, x)
        a3 = lambda x: self.lattice_const_AB(self.matA.lattice.a3, self.matB.lattice.a3, x)
        V = lambda x: numpy.dot(a3(x),numpy.cross(a1(x),a2(x)))
        b1 = lambda x: 2*numpy.pi/V(x)*numpy.cross(a2(x),a3(x))
        b2 = lambda x: 2*numpy.pi/V(x)*numpy.cross(a3(x),a1(x))
        b3 = lambda x: 2*numpy.pi/V(x)*numpy.cross(a1(x),a2(x))
        qhklx = lambda x: hkl[0]*b1(x)+hkl[1]*b2(x)+hkl[2]*b3(x)

        qr_i = numpy.abs(transform(qhklx(self.x))[1])
        qr_p = numpy.abs(transform(qhklx(self.x))[2])
        qs_i = 2*numpy.pi/asub * numpy.linalg.norm(numpy.cross(ndir,hkl))
        qs_p = 2*numpy.pi/asub * numpy.abs(numpy.dot(ndir,hkl))

        # calculate pseudomorphic points for A and B
        # transform elastic constants to correct coordinate frame
        cijA = Cijkl2Cij(transform(self.matA.cijkl))
        cijB = Cijkl2Cij(transform(self.matB.cijkl))
        abulk = lambda x: numpy.linalg.norm(a1(x))
        frac = lambda x: ((cijB[0,2]+cijB[1,2]+cijB[2,0]+cijB[2,1] - (cijA[0,2]+cijA[1,2]+cijA[2,0]+cijA[2,1]))*x  + (cijA[0,2]+cijA[1,2]+cijA[2,0]+cijA[2,1]))/(2*((cijB[2,2]-cijA[2,2])*x + cijA[2,2]))
        aperp = lambda x: abulk(self.x)*( 1 + frac(x)*(1 - asub/abulk(self.x)) )

        qp_i = 2*numpy.pi/asub * numpy.linalg.norm(numpy.cross(ndir,hkl))
        qp_p = 2*numpy.pi/aperp(self.x) * numpy.abs(numpy.dot(ndir,hkl))

        #assembly return values
        qy= numpy.array([qr_i,qp_i,qs_i,qr_i],dtype=numpy.double)
        qz= numpy.array([qr_p,qp_p,qs_p,qr_p],dtype=numpy.double)

        return qy,qz

class CubicAlloy(Alloy):

#    def __init__(self,matA,matB,x):
#            #check if material is really cubic!!

    def ContentBsym(self,q_perp,hkl,inpr,asub,relax):
        """
        function that determines the content of B
        in the alloy from the reciprocal space position
        of a symetric peak. As an additional input the substrates
        lattice parameter and the degree of relaxation must be given

        Parameter
        ---------
        q_perp : perpendicular peak position of the reflection
                 hkl of the alloy in reciprocal space
        hkl : Miller indices of the measured symmetric reflection (also defines the
              surface normal
        inpr : Miller indices of a Bragg peak defining the inplane reference direction
        asub:   substrate lattice constant
        relax:  degree of relaxation (needed to obtain the content from
                symmetric reciprocal space position)

        Returns
        -------
        content : the content of B in the alloy determined from the input variables

        """

        # check input parameters
        if isinstance(q_perp,numpy.ScalarType) and numpy.isfinite(q_perp):
            q_perp = float(q_perp)
        else:
            raise TypeError("First argument (q_perp) must be a scalar!")
        if isinstance(hkl,(list,tuple,numpy.ndarray)):
            hkl = numpy.array(hkl,dtype=numpy.double)
        else:
            raise TypeError("Second argument (hkl) must be of type list, tuple or numpy.ndarray")
        if isinstance(inpr,(list,tuple,numpy.ndarray)):
            inpr = numpy.array(inpr,dtype=numpy.double)
        else:
            raise TypeError("Third argument (inpr) must be of type list, tuple or numpy.ndarray")
        if isinstance(asub,numpy.ScalarType) and numpy.isfinite(asub):
            asub = float(asub)
        else:
            raise TypeError("Fourth argument (asub) must be a scalar!")
        if isinstance(relax,numpy.ScalarType) and numpy.isfinite(relax):
            relax = float(relax)
        else:
            raise TypeError("Fifth argument (relax) must be a scalar!")

        # calculate lattice constants from reciprocal space positions
        n = self.rlattice.GetPoint(hkl)/numpy.linalg.norm(self.rlattice.GetPoint(hkl))
        q_hkl = self.rlattice.GetPoint(hkl)
        # the following line is not generally true! only cubic materials
        aperp = 2*numpy.pi/q_perp * numpy.abs(numpy.dot(n,hkl))

        # transform the elastic tensors to a coordinate frame attached to the surface normal
        inp1 = numpy.cross(n,inpr)/numpy.linalg.norm(numpy.cross(n,inpr))
        inp2 = numpy.cross(n,inp1)
        trans = math.CoordinateTransform(inp1,inp2,n)

        if config.VERBOSITY >= config.DEBUG:
            print("XU.materials.Alloy.ContentB: inp1/inp2: ",inp1,inp2)
        cijA = Cijkl2Cij(trans(self.matA.cijkl))
        cijB = Cijkl2Cij(trans(self.matB.cijkl))

        # define lambda functions for all things in the equation to solve
        a1 = lambda x: self.lattice_const_AB(self.matA.lattice.a1, self.matB.lattice.a1, x)
        a2 = lambda x: self.lattice_const_AB(self.matA.lattice.a2, self.matB.lattice.a2, x)
        a3 = lambda x: self.lattice_const_AB(self.matA.lattice.a3, self.matB.lattice.a3, x)
        V = lambda x: numpy.dot(a3(x),numpy.cross(a1(x),a2(x)))
        b1 = lambda x: 2*numpy.pi/V(x)*numpy.cross(a2(x),a3(x))
        b2 = lambda x: 2*numpy.pi/V(x)*numpy.cross(a3(x),a1(x))
        b3 = lambda x: 2*numpy.pi/V(x)*numpy.cross(a1(x),a2(x))
        qhklx = lambda x: hkl[0]*b1(x)+hkl[1]*b2(x)+hkl[2]*b3(x)

        # the following line is not generally true! only cubic materials
        abulk_perp = lambda x: numpy.abs(2*numpy.pi/numpy.inner(qhklx(x),n) * numpy.inner(n,hkl))
        ainp = lambda x: asub + relax * (abulk_perp(x) - asub) # can we use abulk_perp here? for cubic materials this should work?!

        if config.VERBOSITY >= config.DEBUG:
            print("XU.materials.Alloy.ContentB: abulk_perp: %8.5g" %(abulk_perp(0.)))

        frac = lambda x: ((cijB[0,2]+cijB[1,2]+cijB[2,0]+cijB[2,1] - (cijA[0,2]+cijA[1,2]+cijA[2,0]+cijA[2,1]))*x  + (cijA[0,2]+cijA[1,2]+cijA[2,0]+cijA[2,1]))/(2*((cijB[2,2]-cijA[2,2])*x + cijA[2,2]))

        equation = lambda x: (aperp-abulk_perp(x)) + (ainp(x) - abulk_perp(x))*frac(x)

        x = scipy.optimize.brentq(equation,-0.1,1.1)

        return x

    def ContentBasym(self,q_inp,q_perp,hkl,sur):
        """
        function that determines the content of B
        in the alloy from the reciprocal space position
        of an asymmetric peak and also sets the content
        in the current material

        Parameter
        ---------
        q_inp : inplane peak position of reflection hkl of
                the alloy in reciprocal space
        q_perp : perpendicular peak position of the reflection
                 hkl of the alloy in reciprocal space
        hkl : Miller indices of the measured asymmetric reflection
        sur : Miller indices of the surface (determines the perpendicular
              direction)

        Returns
        -------
        content,[a_inplane,a_perp,a_bulk_perp(x), eps_inplane, eps_perp] :
                the content of B in the alloy determined from the input
                variables and the lattice constants calculated from the
                reciprocal space positions as well as the strain (eps) of
                the layer
        """

        # check input parameters
        if isinstance(q_inp,numpy.ScalarType) and numpy.isfinite(q_inp):
            q_inp = float(q_inp)
        else:
            raise TypeError("First argument (q_inp) must be a scalar!")
        if isinstance(q_perp,numpy.ScalarType) and numpy.isfinite(q_perp):
            q_perp = float(q_perp)
        else:
            raise TypeError("Second argument (q_perp) must be a scalar!")
        if isinstance(hkl,(list,tuple,numpy.ndarray)):
            hkl = numpy.array(hkl,dtype=numpy.double)
        else:
            raise TypeError("Third argument (hkl) must be of type list, tuple or numpy.ndarray")
        if isinstance(sur,(list,tuple,numpy.ndarray)):
            sur = numpy.array(sur,dtype=numpy.double)
        else:
            raise TypeError("Fourth argument (sur) must be of type list, tuple or numpy.ndarray")

        # check if reflection is asymmetric
        if numpy.linalg.norm(numpy.cross(self.rlattice.GetPoint(hkl),self.rlattice.GetPoint(sur))) < 1.e-8:
            raise InputError("Miller indices of a symmetric reflection were given where an asymmetric reflection is needed")

        # calculate lattice constants from reciprocal space positions
        n = self.rlattice.GetPoint(sur)/numpy.linalg.norm(self.rlattice.GetPoint(sur))
        q_hkl = self.rlattice.GetPoint(hkl)
        # the following two lines are not generally true! only cubic materials
        ainp = 2*numpy.pi/q_inp * numpy.linalg.norm(numpy.cross(n,hkl))
        aperp = 2*numpy.pi/q_perp * numpy.abs(numpy.dot(n,hkl))

        # transform the elastic tensors to a coordinate frame attached to the surface normal
        inp1 = numpy.cross(n,q_hkl)/numpy.linalg.norm(numpy.cross(n,q_hkl))
        inp2 = numpy.cross(n,inp1)
        trans = math.CoordinateTransform(inp1,inp2,n)

        cijA = Cijkl2Cij(trans(self.matA.cijkl))
        cijB = Cijkl2Cij(trans(self.matB.cijkl))

        # define lambda functions for all things in the equation to solve
        a1 = lambda x: self.lattice_const_AB(self.matA.lattice.a1, self.matB.lattice.a1, x)
        a2 = lambda x: self.lattice_const_AB(self.matA.lattice.a2, self.matB.lattice.a2, x)
        a3 = lambda x: self.lattice_const_AB(self.matA.lattice.a3, self.matB.lattice.a3, x)
        V = lambda x: numpy.dot(a3(x),numpy.cross(a1(x),a2(x)))
        b1 = lambda x: 2*numpy.pi/V(x)*numpy.cross(a2(x),a3(x))
        b2 = lambda x: 2*numpy.pi/V(x)*numpy.cross(a3(x),a1(x))
        b3 = lambda x: 2*numpy.pi/V(x)*numpy.cross(a1(x),a2(x))
        qsurx = lambda x: sur[0]*b1(x)+sur[1]*b2(x)+sur[2]*b3(x)
        qhklx = lambda x: hkl[0]*b1(x)+hkl[1]*b2(x)+hkl[2]*b3(x)

        # the following two lines are not generally true! only cubic materials
        abulk_inp = lambda x: numpy.abs(2*numpy.pi/numpy.inner(qhklx(x),inp2) * numpy.linalg.norm(numpy.cross(n,hkl)))
        abulk_perp = lambda x: numpy.abs(2*numpy.pi/numpy.inner(qhklx(x),n) * numpy.inner(n,hkl))
        if config.VERBOSITY >= config.DEBUG:
            print("XU.materials.Alloy.ContentB: abulk_inp/perp: %8.5g %8.5g" %(abulk_inp(0.), abulk_perp(0.)))

        frac = lambda x: ((cijB[0,2]+cijB[1,2]+cijB[2,0]+cijB[2,1] - (cijA[0,2]+cijA[1,2]+cijA[2,0]+cijA[2,1]))*x  + (cijA[0,2]+cijA[1,2]+cijA[2,0]+cijA[2,1]))/(2*((cijB[2,2]-cijA[2,2])*x + cijA[2,2]))

        equation = lambda x: (aperp-abulk_perp(x)) + (ainp - abulk_inp(x))*frac(x)

        x = scipy.optimize.brentq(equation,-0.1,1.1)

        #self._setxb(x)

        eps_inplane = (ainp-abulk_perp(x))/abulk_perp(x)
        eps_perp = (aperp-abulk_perp(x))/abulk_perp(x)

        return x,[ainp,aperp,abulk_perp(x), eps_inplane, eps_perp]

class SiGe(CubicAlloy):
    def __init__(self,x):
        CubicAlloy.__init__(self,Si,Ge,x)

    def lattice_const_AB(self, latA, latB, x):
        return latA+ (0.2*x+0.027*x**2)*latA/numpy.linalg.norm(latA)

    def _setxb(self,x):
        if config.VERBOSITY >= config.DEBUG: print("XU.materials.SiGe._setxb: jump to base class")
        CubicAlloy._setxb(self,x)
        if config.VERBOSITY >= config.DEBUG: print("back from base class")
        #the lattice parameters need to be done in a different way
        a = self.lattice_const_AB(self.matA.lattice.a1[0], self.matB.lattice.a1[0], x)
        self.lattice = lattice.CubicLattice(a)
        self.rlattice = self.lattice.ReciprocalLattice()

    x = property(CubicAlloy._getxb,_setxb)

def PseudomorphicMaterial(submat,layermat):
    """
    PseudomprohicMaterial(submat,layermat):
    This function returns a material whos lattice is pseudomorphic on a
    particular substrate material.
    This function works meanwhile only for cubic materials.

    required input arguments:
    submat .................... substrate material
    layermat .................. bulk material of the layer

    return value:
    An instance of Material holding the new pseudomorphically strained
    material.
    """

    a1 = submat.lattice.a1
    a2 = submat.lattice.a2

    #calculate the normal lattice parameter

    abulk = layermat.lattice.a1[0]
    ap    = a1[0]
    c11 = layermat.cij[0,0]
    c12 = layermat.cij[0,1]
    a3 = numpy.zeros(3,dtype=numpy.double)
    a3[2] =  abulk-2.0*c12*(ap-abulk)/c11
    #create the pseudomorphic lattice
    pmlatt = lattice.Lattice(a1,a2,a3)

    #create the new material
    pmat = Material("layermat.name",pmlatt,layermat.cij)

    return pmat

