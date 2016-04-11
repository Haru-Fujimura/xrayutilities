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
# Copyright (C) 2016 Dominik Kriegner <dominik.kriegner@gmail.com>

from matplotlib.pylab import *
import xrayutilities as xu
mpl.rcParams['font.size'] = 16.0

en = 'CuKa1'
Ts = 1e5  # substrate thickness for kinematical simulation
resol = 0.001  # resolution in degree

sub = xu.simpack.Layer(xu.materials.GaAs, Ts)
lay = xu.simpack.Layer(xu.materials.AlGaAs(0.75), 1000, relaxation=0.0)
# pseudomorphic stack -> adjusts lattice parameters!
pls = xu.simpack.PseudomorphicStack001('pseudo', sub, lay)

qz = linspace(4.40, 4.50, 2e3)
ai = degrees(arcsin(xu.en2lam(en)*qz/(4*pi)))

# comparison of different diffraction models
# simplest kinematical diffraction model
mk = xu.simpack.KinematicalModel(pls, energy=en, resolution_width=0.0004)
Ikin = mk.simulate(qz, hkl=(0, 0, 4))

# simplified dynamical diffraction model
mds = xu.simpack.SimpleDynamicalCoplanarModel(pls, energy=en,
                                              resolution_width=resol)
Idynsub = mds.simulate(ai, hkl=(0, 0, 4), idxref=0)
Idynlay = mds.simulate(ai, hkl=(0, 0, 4), idxref=1)

# dynamical diffraction model for substrate and kinematical for the layer(s)
mdk = xu.simpack.DynamicalSKinematicalLModel(pls, energy=en,
                                             resolution_width=resol)
Idynkin = mdk.simulate(ai, hkl=(0, 0, 4), layerpos='dyn')

# general 2-beam theory based dynamical diffraction model
md = xu.simpack.DynamicalModel(pls, energy=en, resolution_width=resol)
Idyn = md.simulate(ai, hkl=(0, 0, 4))

# plot of calculated intensities
figure('XU-simpack AlGaAs')
clf()
semilogy(qz, Ikin, label='kinematical')
semilogy(qz, Idynsub, label='simpl. dynamical(S)')
semilogy(qz, Idynlay, label='simpl. dynamical(L)')
semilogy(qz, Idynkin, label='dyn. S/kin. L')
semilogy(qz, Idyn, label='full dynamical')
vlines([4*2*pi/l.material.a3[-1] for l in pls], 1e-6, 1, linestyles='dashed')
legend(fontsize='small')
xlim(qz.min(), qz.max())
xlabel('Qz ($1/\AA$)')
ylabel('Intensity (arb.u.)')
tight_layout()
show()
