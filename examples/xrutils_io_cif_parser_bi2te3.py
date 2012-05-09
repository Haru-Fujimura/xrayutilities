import xrutils as xu
import numpy

# parse cif file to get unit cell structure
ciff = xu.io.CIFFile("cif_files/bi2te3.cif")

#create material
bite = xu.materials.Material("Bi2Te3",ciff.Lattice(),numpy.zeros((6,6),dtype=numpy.double))

#structure factor calculation
# bite= bite.StructureFactor(bite.Q(h,k,l),energy)
