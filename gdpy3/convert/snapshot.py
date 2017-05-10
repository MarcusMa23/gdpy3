# -*- coding: utf-8 -*-

# Copyright (c) 2017 shmilee

r''' Source fortran code:

v110922
=======

1. snapshot.F90:316-321, ::
    ! parameters: # of species, fields, and grids in velocity, radius, poloidal, toroidal; T_up
    write(iosnap,101)nspecies,nfield,nvgrid,mpsi+1,mtgrid+1,mtoroidal
    write(iosnap,102)1.0/emax_inv
    
    ! write out particle radial profile and pdf, and 2D field
    write(iosnap,102)profile,pdf,poloidata,fluxdata

2. profile(0:mpsi,6,nspecies), snapshot.F90:20-22:66-77

nspecies: 1=ion, 2=electron, 3=EP

radial profiles(6): density, flow, energy of fullf and delf

3. pdf(nvgrid,4,nspecies), snapshot.F90:24-25:79-82

distribution function(4): energy, pitch angle of fullf and delf

4. poloidata(0:mtgrid,0:mpsi,nfield+2), snapshot.F90:236-307

field quantities: phi, a_para, fluidne. Last two coloumn of poloidal for coordinates

5. fluxdata(0:mtgrid,mtoroidal,nfield), snapshot.F90:236-270

field quantities: phi, a_para, fluidne.
'''

import os
import numpy
from .datablock import DataBlock

__all__ = ['SnapshotBlockV110922']


class SnapshotBlockV110922(DataBlock):
    '''Snapshot data

    1) ion, electron, EP radial profiles:
       density, flow, energy of fullf and delf
    2) ion, electron, EP distribution function in:
       energy, pitch angle of fullf and delf
    3) phi, a_para, fluidne on ploidal plane
    4) phi, a_para, fluidne on flux surface

    Attributes
    ----------
        file: str
            File path of GTC ``snap("%05d" % istep).out`` to convert
        group: str of data group
        datakeys: tuple
            data keys of physical quantities in ``snap("%05d" % istep).out``
        data: dict of converted data
    '''
    __slots__ = ['file', 'group', 'datakeys', 'data']

    def __init__(self, file=None, group=None):
        if os.path.isfile(file):
            self.file = file
        else:
            raise IOError("Can't find '%s' file: '%s'!" % (group, file))
        if group:
            self.group = group
        else:
            self.group = os.path.basename(os.path.splitext(file)[0])
        self.datakeys = (
            # 1. parameters
            'nspecies', 'nfield', 'nvgrid', 'mpsi+1',
            'mtgrid+1', 'mtoroidal', 'T_up',
            # 2. profile(0:mpsi,6,nspecies)
            'ion-profile', 'electron-profile', 'fastion-profile',
            # 3. pdf(nvgrid,4,nspecies)
            'ion-pdf', 'electron-pdf', 'fastion-pdf',
            # 4. poloidata(0:mtgrid,0:mpsi,nfield+2)
            'poloidata-phi', 'poloidata-apara', 'poloidata-fluidne',
            'poloidata-x', 'poloidata-z',
            # 5. fluxdata(0:mtgrid,mtoroidal,nfield)
            'fluxdata-phi', 'fluxdata-apara', 'fluxdata-fluidne')
        self.data = dict(description='Snapshot Data:'
                         '\n1) profile 2d array is profile[r,6]\n'
                         '   6 profiles order: fullf density, delf density,'
                         'fullf flow, delf flow, fullf energy, delf energy.'
                         '\n2) pdf 2d array is pdf[nvgrid,4]\n'
                         '   4 pdf order: fullf energy, delf energy,'
                         'fullf pitch angle, delf pitch angle.'
                         '\n3) poloidata 2d array is poloidata[theta,r]'
                         '\n4) fluxdata 2d array is fluxdata[theta,zeta]')

    def convert(self):
        '''Read snap("%05d" % istep).out

        convert the .out data to self.data as a dict,
        save list in data dict as numpy.array.
        '''
        with open(self.file, 'r') as f:
            outdata = f.readlines()

        sd = self.data
        # 1. parameters
        for i, key in enumerate(self.datakeys[:6]):
            sd.update({key: int(outdata[i].strip())})
        # 1. T_up, 1.0/emax_inv
        sd.update({'T_up': float(outdata[6].strip())})

        outdata = numpy.array([float(n.strip()) for n in outdata[7:]])

        # 2. profile(0:mpsi,6,nspecies)
        tempsize = sd['mpsi+1'] * 6 * sd['nspecies']
        tempshape = (sd['mpsi+1'], 6, sd['nspecies'])
        tempdata = outdata[:tempsize].reshape(tempshape, order='F')
        sd.update({'ion-profile': tempdata[:, :, 0]})
        if sd['nspecies'] > 1:
            sd.update({'electron-profile': tempdata[:, :, 1]})
        else:
            sd.update({'electron-profile': []})
        if sd['nspecies'] > 2:
            sd.update({'fastion-profile': tempdata[:, :, 2]})
        else:
            sd.update({'fastion-profile': []})

        # 3. pdf(nvgrid,4,nspecies)
        index0 = tempsize
        tempsize = sd['nvgrid'] * 4 * sd['nspecies']
        index1 = index0 + tempsize
        tempshape = (sd['nvgrid'], 4, sd['nspecies'])
        tempdata = outdata[index0:index1].reshape(tempshape, order='F')
        sd.update({'ion-pdf': tempdata[:, :, 0]})
        if sd['nspecies'] > 1:
            sd.update({'electron-pdf': tempdata[:, :, 1]})
        else:
            sd.update({'electron-pdf': []})
        if sd['nspecies'] > 2:
            sd.update({'fastion-pdf': tempdata[:, :, 2]})
        else:
            sd.update({'fastion-pdf': []})

        # 4. poloidata(0:mtgrid,0:mpsi,nfield+2), nfield=3
        tempsize = sd['mtgrid+1'] * sd['mpsi+1'] * (sd['nfield'] + 2)
        index0, index1 = index1, index1 + tempsize
        tempshape = (sd['mtgrid+1'], sd['mpsi+1'], sd['nfield'] + 2)
        tempdata = outdata[index0:index1].reshape(tempshape, order='F')
        sd.update({'poloidata-phi': tempdata[:, :, 0]})
        sd.update({'poloidata-apara': tempdata[:, :, 1]})
        sd.update({'poloidata-fluidne': tempdata[:, :, 2]})
        sd.update({'poloidata-x': tempdata[:, :, 3]})
        sd.update({'poloidata-z': tempdata[:, :, 4]})

        # 5. fluxdata(0:mtgrid,mtoroidal,nfield)
        tempsize = sd['mtgrid+1'] * sd['mtoroidal'] * sd['nfield']
        index0, index1 = index1, index1 + tempsize
        tempshape = (sd['mtgrid+1'], sd['mtoroidal'], sd['nfield'])
        tempdata = outdata[index0:index1].reshape(tempshape, order='F')
        sd.update({'fluxdata-phi': tempdata[:, :, 0]})
        sd.update({'fluxdata-apara': tempdata[:, :, 1]})
        sd.update({'fluxdata-fluidne': tempdata[:, :, 2]})
