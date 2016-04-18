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


def alpha_i(qx, qz):
    th = arcsin(sqrt(qx**2 + qz**2) / (4 * pi) * xu.en2lam(en))
    return degrees(arctan2(qx, qz) + th)

en = 8500  # eV
resol = 0.0004  # resolution in q
h, k, l = (1, 1, 1)
qz = linspace(1.8, 2.2, 5e3)
Si = xu.materials.Si
hxrd = xu.HXRD(Si.Q(1, 1, -2), Si.Q(1, 1, 1), en=en)

sub = xu.simpack.Layer(Si, inf)
lay = xu.simpack.Layer(xu.materials.SiGe(0.6), 150)
ls = sub + lay  # relaxed layers

# calculate incidence angle for dynamical diffraction models
qx = hxrd.Transform(Si.Q(h, k, l))[1]
ai = alpha_i(qx, qz)
resolai = abs(alpha_i(qx, mean(qz) + resol) - alpha_i(qx, mean(qz)))

# comparison of different diffraction models
# simplest kinematical diffraction model
mk = xu.simpack.KinematicalModel(ls, experiment=hxrd, resolution_width=resol)
Ikin = mk.simulate(qz, hkl=(h, k, l), refraction=True)

# simplified dynamical diffraction model
mds = xu.simpack.SimpleDynamicalCoplanarModel(ls, experiment=hxrd,
                                              resolution_width=resolai)
Idynsub = mds.simulate(ai, hkl=(h, k, l), idxref=0)
Idynlay = mds.simulate(ai, hkl=(h, k, l), idxref=1)

# general 2-beam theory based dynamical diffraction model
md = xu.simpack.DynamicalModel(ls, experiment=hxrd, resolution_width=resolai)
Idyn = md.simulate(ai, hkl=(h, k, l))

# plot of calculated intensities
figure('XU-simpack SiGe(111)')
clf()
semilogy(qz, Ikin, label='kinematical')
semilogy(qz, Idynsub, label='simpl. dynamical(S)')
semilogy(qz, Idynlay, label='simpl. dynamical(L)')
semilogy(qz, Idyn, label='full dynamical')
vlines([sqrt(3)*2*pi/l.material.a3[-1] for l in ls], 1e-9, 1,
       linestyles='dashed')
legend(fontsize='small')
xlim(qz.min(), qz.max())
xlabel('Qz ($1/\AA$)')
ylabel('Intensity (arb.u.)')
tight_layout()
show()
