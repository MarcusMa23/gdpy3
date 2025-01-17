# -*- coding: utf-8 -*-

# Copyright (c) 2019-2021 shmilee

'''
Source fortran code:

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

import numpy as np
from .. import tools
from ..cores.converter import Converter, clog
from ..cores.digger import Digger, dlog
from .gtc import Ndigits_tstep

_all_Converters = ['SnapshotConverter']
_all_Diggers = [
    'SnapshotProfileDigger', 'SnapshotPdfDigger',
    'SnapshotFieldFluxDigger', 'SnapshotFieldFluxTileDigger',
    'SnapshotFieldFluxCorrLenDigger', 'SnapshotFieldPoloidalDigger',
    'SnapshotFieldSpectrumDigger', 'SnapshotTimeFieldSpectrumDigger',
    'SnapshotFieldProfileDigger',
    'SnapshotFieldmDigger', 'SnapshotFieldmkthetaDigger']
__all__ = _all_Converters + _all_Diggers


class SnapshotConverter(Converter):
    '''
    Snapshot Data

    1) ion, electron, EP radial profiles.
       Profile 2d array is profile[r,6].
       6 profiles order:
       fullf density, delf density, fullf flow,
       delf flow, fullf energy, delf energy.
    2) ion, electron, EP distribution function in:
       energy, pitch angle of fullf and delf.
       pdf 2d array is pdf[nvgrid,4].
       4 pdf order: fullf in energy, delf in energy,
       fullf in pitch angle, delf in pitch angle.
    3) phi, a_para, fluidne on poloidal plane
       poloidata 2d array is poloidata[theta,r].
    4) phi, a_para, fluidne on flux surface
       fluxdata 2d array is fluxdata[theta,zeta].
    '''
    __slots__ = []
    nitems = '?'
    itemspattern = ['^(?P<section>snap\d{5,7})\.out$',
                    '.*/(?P<section>snap\d{5,7})\.out$']
    _datakeys = (
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

    def _convert(self):
        '''Read 'snap%05d.out' % istep.'''
        with self.rawloader.get(self.files) as f:
            clog.debug("Read file '%s'." % self.files)
            outdata = f.readlines()

        sd = {}
        # 1. parameters
        clog.debug("Filling datakeys: %s ..." % str(self._datakeys[:7]))
        for i, key in enumerate(self._datakeys[:6]):
            sd.update({key: int(outdata[i].strip())})
        # 1. T_up, 1.0/emax_inv
        sd.update({'T_up': float(outdata[6].strip())})

        outdata = np.array([float(n.strip()) for n in outdata[7:]])

        # 2. profile(0:mpsi,6,nspecies)
        tempsize = sd['mpsi+1'] * 6 * sd['nspecies']
        tempshape = (sd['mpsi+1'], 6, sd['nspecies'])
        tempdata = outdata[:tempsize].reshape(tempshape, order='F')
        clog.debug("Filling datakey: %s ..." % 'ion-profile')
        sd.update({'ion-profile': tempdata[:, :, 0]})
        if sd['nspecies'] > 1:
            clog.debug("Filling datakey: %s ..." % 'electron-profile')
            sd.update({'electron-profile': tempdata[:, :, 1]})
        if sd['nspecies'] > 2:
            clog.debug("Filling datakey: %s ..." % 'fastion-profile')
            sd.update({'fastion-profile': tempdata[:, :, 2]})

        # 3. pdf(nvgrid,4,nspecies)
        index0 = tempsize
        tempsize = sd['nvgrid'] * 4 * sd['nspecies']
        index1 = index0 + tempsize
        tempshape = (sd['nvgrid'], 4, sd['nspecies'])
        tempdata = outdata[index0:index1].reshape(tempshape, order='F')
        clog.debug("Filling datakey: %s ..." % 'ion-pdf')
        sd.update({'ion-pdf': tempdata[:, :, 0]})
        if sd['nspecies'] > 1:
            clog.debug("Filling datakey: %s ..." % 'electron-pdf')
            sd.update({'electron-pdf': tempdata[:, :, 1]})
        if sd['nspecies'] > 2:
            clog.debug("Filling datakey: %s ..." % 'fastion-pdf')
            sd.update({'fastion-pdf': tempdata[:, :, 2]})

        # 4. poloidata(0:mtgrid,0:mpsi,nfield+2), nfield=3 or 5
        clog.debug("Filling datakeys: %s ..." % str(self._datakeys[13:18]))
        tempsize = sd['mtgrid+1'] * sd['mpsi+1'] * (sd['nfield'] + 2)
        index0, index1 = index1, index1 + tempsize
        tempshape = (sd['mtgrid+1'], sd['mpsi+1'], sd['nfield'] + 2)
        tempdata = outdata[index0:index1].reshape(tempshape, order='F')
        sd.update({'poloidata-phi': tempdata[:, :, 0]})
        sd.update({'poloidata-apara': tempdata[:, :, 1]})
        sd.update({'poloidata-fluidne': tempdata[:, :, 2]})
        sd.update({'poloidata-x': tempdata[:, :, -2]})
        sd.update({'poloidata-z': tempdata[:, :, -1]})
        if sd['nfield'] == 5:
            clog.debug("Filling datakeys: %s ..." % str(
                ('poloidata-densityi', 'poloidata-densitye')))
            sd.update({'poloidata-densityi': tempdata[:, :, 3]})
            sd.update({'poloidata-densitye': tempdata[:, :, 4]})

        # 5. fluxdata(0:mtgrid,mtoroidal,nfield)
        clog.debug("Filling datakeys: %s ..." % str(self._datakeys[18:]))
        tempsize = sd['mtgrid+1'] * sd['mtoroidal'] * sd['nfield']
        index0, index1 = index1, index1 + tempsize
        tempshape = (sd['mtgrid+1'], sd['mtoroidal'], sd['nfield'])
        tempdata = outdata[index0:index1].reshape(tempshape, order='F')
        sd.update({'fluxdata-phi': tempdata[:, :, 0]})
        sd.update({'fluxdata-apara': tempdata[:, :, 1]})
        sd.update({'fluxdata-fluidne': tempdata[:, :, 2]})
        if sd['nfield'] == 5:
            clog.debug("Filling datakeys: %s ..." % str(
                ('fluxdata-densityi', 'fluxdata-densitye')))
            sd.update({'fluxdata-densityi': tempdata[:, :, 3]})
            sd.update({'fluxdata-densitye': tempdata[:, :, 4]})

        return sd


def _snap_get_timestr(snapgroup, pckloader):
    istep = int(snapgroup.replace('snap', ''))
    tstep = pckloader.get('gtc/tstep')
    tstep = round(tstep, Ndigits_tstep)
    return r'istep=%d, time=%s$R_0/c_s$' % (istep, istep * tstep)


class SnapshotProfileDigger(Digger):
    '''ion, electron, fastion radial profiles.'''
    __slots__ = []
    nitems = '+'
    itemspattern = ['^(?P<section>snap\d{5,7})'
                    + '/(?P<particle>(?:ion|electron|fastion))-profile$',
                    '^(?P<s>snap\d{5,7})/mpsi\+1']
    commonpattern = ['gtc/tstep']
    post_template = 'tmpl_sharextwinx'

    def _set_fignum(self, numseed=None):
        self._fignum = '%s_profile' % self.section[1]

    def _dig(self, kwargs):
        title = '%s %s, %s' % (self.section[1], 'profile',
                               _snap_get_timestr(self.group, self.pckloader))
        data, x1 = self.pckloader.get_many(*self.srckeys)
        data = data.T
        return dict(
            ipsi=np.arange(x1),
            density=data[0],
            densitydf=data[1],
            flow=data[2],
            flowdf=data[3],
            energy=data[4],
            energydf=data[5],
            title=title,
            xlabel='r (mpsi)'), {}

    def _post_dig(self, results):
        r = results
        YINFO = [{'left': [(r['density'], 'density f')],
                  'right': [(r['densitydf'], r'density $\delta f$')],
                  'lylabel': '$f$', 'rylabel': r'$\delta f$'},
                 {'left': [(r['flow'], 'flow f')],
                  'right': [(r['flowdf'], r'flow $\delta f$')],
                  'lylabel': '$f$', 'rylabel': r'$\delta f$'},
                 {'left': [(r['energy'], 'energy f')],
                  'right': [(r['energydf'], r'energy $\delta f$')],
                  'lylabel': '$f$', 'rylabel': r'$\delta f$'}]
        return dict(X=r['ipsi'], YINFO=YINFO, title=r['title'],
                    xlabel=r['xlabel'], xlim=[0, np.max(r['ipsi'])])


class SnapshotPdfDigger(Digger):
    '''ion, electron, fastion pdf in E or pitch angle.'''
    __slots__ = []
    nitems = '+'
    itemspattern = ['^(?P<section>snap\d{5,7})'
                    + '/(?P<particle>(?:ion|electron|fastion))-pdf$',
                    '^(?P<s>snap\d{5,7})/nvgrid',
                    '^(?P<s>snap\d{5,7})/T_up']
    commonpattern = ['gtc/tstep']
    post_template = ('tmpl_z111p', 'tmpl_sharextwinx')

    def _set_fignum(self, numseed=None):
        self._fignum = '%s_pdf' % self.section[1]

    def _dig(self, kwargs):
        title = '%s %s, %s' % (self.section[1], 'distribution function',
                               _snap_get_timestr(self.group, self.pckloader))
        data, nvgrid, T_up = self.pckloader.get_many(*self.srckeys)
        dE = T_up / nvgrid
        xE = np.linspace(0.0+dE/2.0, T_up-dE/2.0, nvgrid)
        dpitch = 2.0 / nvgrid
        xpitch = np.linspace(-1.0+dpitch/2.0, 1.0-dpitch/2.0, nvgrid)
        data = data.T
        return dict(
            xE=xE, T_up=T_up, efullf=data[0], edf=data[1],
            xpitch=xpitch, pafullf=data[2], padf=data[3],
            title=title), {}

    def _post_dig(self, results):
        r = results
        ax1_calc = dict(X=r['xE'], YINFO=[
                        {'left': [(r['efullf'], '$f$')],
                         'right': [(r['edf'], r'$\delta f$')],
                         'lylabel': '$f$', 'rylabel': r'$\delta f$'}],
                        xlabel=r'$E/T_{%s0}$' % self.section[1][0],
                        xlim=[0, r['T_up']])
        ax2_calc = dict(X=r['xpitch'], YINFO=[
                        {'left': [(r['pafullf'], '$f$')],
                         'right': [(r['padf'], r'$\delta f$')],
                            'lylabel': '$f$', 'rylabel': r'$\delta f$'}],
                        xlabel=r'pitch angle $\zeta=v_{\parallel}/v$',
                        xlim=[-1.0, 1.0])
        return dict(zip_results=[('tmpl_sharextwinx', 211, ax1_calc),
                                 ('tmpl_sharextwinx', 212, ax2_calc)],
                    suptitle=r['title'])


field_tex_str = {
    'phi': r'\phi',
    'apara': r'A_{\parallel}',
    'fluidne': r'fluid n_e',
    'densityi': r'\delta n_i',
    'densitye': r'\delta n_e',
}


class SnapshotFieldFluxDigger(Digger):
    '''phi, a_para, fluidne, or densityi, densitye on flux surface.'''
    __slots__ = []
    nitems = '?'
    itemspattern = [
        '^(?P<section>snap\d{5,7})'
        + '/fluxdata-(?P<field>(?:phi|apara|fluidne|densityi|densitye))']
    commonpattern = ['gtc/tstep']
    post_template = 'tmpl_contourf'

    def _set_fignum(self, numseed=None):
        self._fignum = '%s_flux' % self.section[1]

    def _dig(self, kwargs):
        title = _snap_get_timestr(self.group, self.pckloader)
        fstr = field_tex_str[self.section[1]]
        data = self.pckloader.get(self.srckeys[0])
        y, x = data.shape  # 0-mtgrid; 1-mtoroidal
        return dict(
            zeta=np.arange(1, x+1) / x * 2 * np.pi,  # (0,2pi]
            theta=np.arange(0, y) / (y-1) * 2 * np.pi,  # [0,2pi]
            field=data,
            title=r'$%s$ on flux surface, %s' % (fstr, title)), {}

    def _post_dig(self, results):
        r = results
        return dict(X=r['zeta'], Y=r['theta'], Z=r['field'],
                    title=r['title'], xlabel=r'$\zeta$',
                    ylabel=r'$\theta$', aspect='equal')


class SnapshotFieldFluxTileDigger(SnapshotFieldFluxDigger):
    '''Tiled phi, a_para etc. on flux surface.'''
    __slots__ = []
    commonpattern = ['gtc/tstep', 'gtc/qiflux']

    def _set_fignum(self, numseed=None):
        self._fignum = '%s_flux_tiled' % self.section[1]
        self.kwoptions = None

    def _dig(self, kwargs):
        '''
        kwargs
        ------
        *N*: int, >=2, default 3
            how many zeta(2pi) will be tiled
        '''
        res, _ = super(SnapshotFieldFluxTileDigger, self)._dig(kwargs)
        title, field = res['title'], res['field'][1:, :]  # all (0, 2pi]
        zeta, theta = res['zeta'], res['theta'][1:]
        q = self.pckloader.get('gtc/qiflux')
        sep = int(field.shape[0]*(1.0-1.0/q))  # q>1
        N = kwargs.get('N', 3)
        if not (isinstance(N, int) and N >= 2):
            N = 3
        if self.kwoptions is None:
            self.kwoptions = dict(
                N=dict(widget='IntSlider',
                       rangee=(2, 6, 1),
                       value=3,
                       description='zeta N_2pi:'))
        acckwargs = dict(N=N)
        c1, c2 = field, field
        zeta1, theta1 = zeta, theta
        for i in range(1, N):
            h1 = c1[sep*(i-1):sep*i]
            t2 = c2[-sep:] if i == 1 else c2[-sep*i:-sep*(i-1)]
            c1, c2 = np.row_stack((c1, h1)), np.row_stack((t2, c2))
            c1 = np.column_stack((c1, c2))
            zeta1 = np.append(zeta1, zeta+2*np.pi*i)
            theta1 = np.append(theta1, theta1[sep*(i-1):sep*i]+2*np.pi)
        return dict(title=title, field=c1, zeta=zeta1, theta=theta1), acckwargs

    def _post_dig(self, results):
        r = results
        return dict(X=r['zeta'], Y=r['theta'], Z=r['field'],
                    title=r['title'], xlabel=r'$\zeta$', ylabel=r'$\theta$')


class SnapshotFieldFluxCorrLenDigger(SnapshotFieldFluxTileDigger):
    '''Get field correlation(d_zeta, d_theta) from tiled flux surface.'''
    __slots__ = []
    post_template = ('tmpl_z111p', 'tmpl_contourf', 'tmpl_line')

    def _set_fignum(self, numseed=None):
        self._fignum = '%s_flux_corrlen' % self.section[1]
        self.kwoptions = None

    def _dig(self, kwargs):
        '''*dzeta*: float
            set dzeta range, default 2*pi (6.3), max N*pi
        *dtheta*: float
            set dtheta range, default 0.1 (0.10), max 1.5
        '''
        res, acckws = super(SnapshotFieldFluxCorrLenDigger, self)._dig(kwargs)
        title, field = res['title'], res['field']
        zeta, theta = res['zeta'], res['theta']
        title = r'CorrLen$(\Delta\zeta, \Delta\theta)$ of ' + title
        N = zeta[-1]/np.pi/2
        maxdzeta, maxdtheta = round(N*np.pi, 1), 1.5
        dzeta, dtheta = kwargs.get('dzeta', None), kwargs.get('dtheta', None)
        if not (isinstance(dzeta, (int, float)) and 0 < dzeta <= maxdzeta):
            dzeta = round(2*np.pi, 1)
        if not (isinstance(dtheta, (int, float)) and 0 < dtheta <= maxdtheta):
            dtheta = 0.1
        if 'dzeta' not in self.kwoptions:
            self.kwoptions.update(dict(
                dzeta=dict(widget='FloatSlider',
                           rangee=(0.2, round(6*np.pi, 1), 0.1),
                           value=round(2*np.pi, 1),
                           description='dzeta:'),
                dtheta=dict(widget='FloatSlider',
                            rangee=(0.05, maxdtheta, 0.05),
                            value=0.1,
                            description='dtheta:')))
        acckws.update(dzeta=round(dzeta, 1), dtheta=round(dtheta, 2))
        y, x = field.shape
        dlog.parm('Data shape of fflux(theta,zeta) is %s.' % ((y, x),))
        mdzeta = int(dzeta/(zeta[1]-zeta[0]))
        mdtheta = int(dtheta/(theta[1]-theta[0]))
        dlog.parm("Use dzeta=%s, dtheta=%s, mdzeta=%s, mdtheta=%s. "
                  "Maximal maxdzeta=%s, maxdtheta=%s"
                  % (dzeta, dtheta, mdzeta, mdtheta, maxdzeta, maxdtheta))
        tau, cdt, vdz = tools.correlation(field, 0, y, 0, x, mdtheta, mdzeta)
        mdzeta, mdtheta = np.arange(1, mdzeta+1), np.arange(1, mdtheta+1)
        dzeta, dtheta = mdzeta*(zeta[1]-zeta[0]), mdtheta*(theta[1]-theta[0])
        mtau, Cx = [], []
        for n, X, Y in [(0, dzeta, tau.max(axis=0)), (1, dzeta, tau[0, :]),
                        (2, dtheta, tau.max(axis=1)), (3, dtheta, tau[:, 0])]:
            index = np.where(Y <= 1.0/np.e)[0]
            if index.size > 0:
                i, j = index[0] - 1,  index[0]
                Xm, y = tools.intersection_4points(
                    X[i], Y[i], X[j], Y[j],
                    X[i], 1.0/np.e, X[j], 1.0/np.e)
            else:
                Xm = X[-1]
                dlog.info("Increase dzeta/dtheta to find correlation %d!" % n)
            mtau.append(Y)
            Cx.append(Xm)
        dlog.parm("Get correlation: dzeta=%.6f, dtheta=%.6f" % (Cx[0], Cx[2]))
        return dict(title=title, dzeta=dzeta, dtheta=dtheta, tau=tau,
                    zetatau=mtau[0], zetatau0=mtau[1], thetatau=mtau[2],
                    thetatau0=mtau[3], zetaC=Cx[0], zetaC0=Cx[1],
                    thetaC=Cx[2], thetaC0=Cx[3]), acckws

    def _post_dig(self, results):
        r = results
        ax1_calc = dict(
            X=r['dzeta'], Y=r['dtheta'], Z=r['tau'], clabel_levels=[1/np.e],
            title=r['title'], xlabel=r'$\Delta\zeta$', ylabel=r'$\Delta\theta$')
        ax2_calc = dict(
            LINE=[
                (r['dzeta'], r['zetatau'], r'$maxC(\Delta\zeta)$'),
                (r['dzeta'], r['zetatau0'], r'$C(\Delta\zeta,\Delta\theta=0)$'),
                ([r['dzeta'][0], r['dzeta'][-1]], [1/np.e, 1/np.e], '1/e'),
            ],
            title=r'$maxC(\Delta\zeta=%.3f)=C(\Delta\zeta=%.3f,\Delta\theta=0)=1/e$' % (
                r['zetaC'], r['zetaC0']),
            xlabel=r'$\Delta\zeta$',
            xlim=[r['dzeta'][0], r['dzeta'][-1]],
            ylim=[min(0, r['zetatau'].min()), 1])
        ax3_calc = dict(
            LINE=[
                (r['dtheta'], r['thetatau'], r'$maxC(\Delta\theta)$'),
                (r['dtheta'], r['thetatau0'], r'$C(\Delta\zeta=0,\Delta\theta)$'),
                ([r['dtheta'][0], r['dtheta'][-1]], [1/np.e, 1/np.e], '1/e'),
            ],
            title=r'$maxC(\Delta\theta=%.6f)=C(\Delta\zeta=0,\Delta\theta=%.6f)=1/e$' % (
                r['thetaC'], r['thetaC0']),
            xlabel=r'$\Delta\theta$',
            xlim=[r['dtheta'][0], r['dtheta'][-1]],
            ylim=[min(0, r['thetatau'].min()), 1])
        return dict(zip_results=[
            ('tmpl_contourf', 211, ax1_calc),
            ('tmpl_line', 223, ax2_calc),
            ('tmpl_line', 224, ax3_calc),
        ])


class SnapshotFieldPoloidalDigger(Digger):
    '''phi, a_para, fluidne or densityi, densitye on poloidal plane.'''
    __slots__ = []
    nitems = '+'
    itemspattern = [
        '^(?P<section>snap\d{5,7})'
        + '/poloidata-(?P<field>(?:phi|apara|fluidne|densityi|densitye))',
        '^(?P<s>snap\d{5,7})/poloidata-(?:x|z)']
    commonpattern = ['gtc/tstep', 'gtc/mpsi', 'gtc/arr2', 'gtc/a_minor']
    neededpattern = itemspattern + commonpattern[:-2]
    post_template = ('tmpl_z111p', 'tmpl_contourf', 'tmpl_line')

    def _set_fignum(self, numseed=None):
        self._fignum = '%s_poloi' % self.section[1]
        self.kwoptions = None

    def _dig(self, kwargs):
        '''
        kwargs
        ------
        *circle_iflux*: int, default mpsi//2
            when iflux=[1,mpsi-1], add a circle for r(iflux)
            when iflux=0,mpsi, donot add circle
        '''
        title = _snap_get_timestr(self.group, self.pckloader)
        fstr = field_tex_str[self.section[1]]
        data, X, Z = self.pckloader.get_many(*self.srckeys)
        mpsi = self.pckloader.get('gtc/mpsi')
        circle_iflux = kwargs.get('circle_iflux', mpsi//2)
        if isinstance(circle_iflux, int) and 0 < circle_iflux < mpsi:
            dlog.parm("Add circle for iflux=%s on poloidal plane." %
                      circle_iflux)
        else:
            circle_iflux = 0
        acckwargs = dict(circle_iflux=circle_iflux)
        circle_r = 0
        if circle_iflux:
            try:
                arr2, a = self.pckloader.get_many(*self.common[-2:])
                rr = arr2[:, 1] / a  # arr2 [1,mpsi-1]
                circle_r = np.round(rr[circle_iflux-1], decimals=3)
            except Exception:
                pass
        if self.kwoptions is None:
            self.kwoptions = dict(
                circle_iflux=dict(
                    widget='IntSlider',
                    rangee=(0, mpsi, 1),
                    value=circle_iflux,
                    description='circle_iflux:'))
        return dict(
            X=X, Z=Z, field=data, circle_iflux=circle_iflux, circle_r=circle_r,
            title=r'$%s$ on poloidal plane, %s' % (fstr, title)), acckwargs

    def _post_dig(self, results):
        # ?TODO? kwargs['circle_iflux '] to postkwargs ?kwoptions?
        r = results
        zip_results = [('tmpl_contourf', 111, dict(
            X=r['X'], Y=r['Z'], Z=r['field'], title=r['title'],
            xlabel=r'$R(R_0)$', ylabel=r'$Z(R_0)$', aspect='equal'))]
        if r['circle_iflux']:
            X, Z = r['X'][:, r['circle_iflux']], r['Z'][:, r['circle_iflux']]
            if r['circle_r']:
                label = r'r(iflux=%d)=%ga' % (r['circle_iflux'], r['circle_r'])
            else:
                label = r'iflux=%d' % r['circle_iflux']
            zip_results.append(('tmpl_line', 111, dict(LINE=[
                ([], []), (X, Z, label)])))
        return dict(zip_results=zip_results)


class SnapshotFieldSpectrumDigger(Digger):
    '''field or density poloidal and parallel spectra.'''
    __slots__ = []
    nitems = '+'
    itemspattern = [
        '^(?P<section>snap\d{5,7})'
        + '/fluxdata-(?P<field>(?:phi|apara|fluidne|densityi|densitye))',
        '^(?P<s>snap\d{5,7})/mtgrid\+1',
        '^(?P<s>snap\d{5,7})/mtoroidal']
    commonpattern = ['gtc/tstep']
    post_template = ('tmpl_z111p', 'tmpl_line')

    def _set_fignum(self, numseed=None):
        self._fignum = '%s_spectrum' % self.section[1]
        self.kwoptions = None

    def _get_spectrum(self, mmode, pmode, fluxdata, mtgrid, mtoroidal,
                      smooth, norm):
        Y1, Y2 = np.zeros(mmode), np.zeros(pmode)
        for i in range(mtoroidal):
            yy = np.fft.fft(fluxdata[:, i])
            Y1[0] = Y1[0] + (abs(yy[0]))**2
            for j in range(1, mmode):
                Y1[j] = Y1[j] + (abs(yy[j]))**2 + (abs(yy[mtgrid - j]))**2
        Y1 = np.sqrt(Y1 / mtoroidal) / mtgrid
        for i in range(mtgrid):
            yy = np.fft.fft(fluxdata[i, :])
            Y2[0] = Y2[0] + (abs(yy[0]))**2
            for j in range(1, pmode):
                Y2[j] = Y2[j] + (abs(yy[j]))**2 + (abs(yy[mtoroidal - j]))**2
        Y2 = np.sqrt(Y2 / mtgrid) / mtoroidal
        if smooth:
            Y1 = tools.savgolay_filter(Y1, info='spectrum')
            Y2 = tools.savgolay_filter(Y2, info='spectrum')
        if norm:
            Y1, Y2 = Y1/Y1.max(), Y2/Y2.max()
        idx1, idx2 = np.argmax(Y1), np.argmax(Y2)
        return Y1, Y2, idx1, idx2

    def _set_params(self, kwargs, mtgrid, mtoroidal,
                    mkey='mmode', pkey='pmode',
                    mtext='Poloidal', ptext='parallel'):
        maxmmode = int(mtgrid / 2 + 1)
        maxpmode = int(mtoroidal / 2 + 1)
        mmode, pmode = kwargs.get(mkey, None), kwargs.get(pkey, None)
        if not (isinstance(mmode, int) and mmode <= maxmmode):
            mmode = mtgrid // 5
        if not (isinstance(pmode, int) and pmode <= maxpmode):
            pmode = mtoroidal // 3
        dlog.parm("%s and %s range: %s=%s, %s=%s. Maximal %s=%s, %s=%s"
                  % (mtext, ptext, mkey, mmode, pkey, pmode,
                     mkey, maxmmode, pkey, maxpmode))
        smooth, norm = kwargs.get('smooth', False), kwargs.get('norm', False)
        acckwargs = {mkey: mmode, pkey: pmode,
                     'smooth': bool(smooth), 'norm': bool(norm)}
        if self.kwoptions is None:
            self.kwoptions = {
                mkey: dict(widget='IntSlider',
                           rangee=(1, maxmmode, 1),
                           value=mmode,
                           description='%s:' % mkey),
                pkey: dict(widget='IntSlider',
                           rangee=(1, maxpmode, 1),
                           value=pmode,
                           description='%s:' % pkey),
                'smooth': dict(widget='Checkbox',
                               value=bool(smooth),
                               description='smooth spectrum:'),
                'norm': dict(widget='Checkbox',
                             value=bool(norm),
                             description='normalize spectrum:')}
        return acckwargs

    def _dig(self, kwargs):
        '''
        kwargs
        ------
        *mmode*, *pmode*: int
            set poloidal or parallel range
        *smooth*: bool, default False
            smooth spectrum results or not
        *norm*: bool, default False
            normalize spectrum results or not
        '''
        fluxdata, mtgrid1, mtoroidal = self.pckloader.get_many(*self.srckeys)
        if fluxdata.shape != (mtgrid1, mtoroidal):
            dlog.error("Invalid fluxdata shape!")
            return {}, {}
        mtgrid = mtgrid1 - 1
        acckwargs = self._set_params(kwargs, mtgrid, mtoroidal)
        mmode, pmode = acckwargs['mmode'], acckwargs['pmode']
        X1, X2 = np.arange(1, mmode + 1), np.arange(1, pmode + 1)
        smooth, norm = acckwargs['smooth'], acckwargs['norm']
        Y1, Y2, idx1, idx2 = self._get_spectrum(
            mmode, pmode, fluxdata, mtgrid, mtoroidal, smooth, norm)
        m, p = X1[idx1], X2[idx2]
        fstr = field_tex_str[self.section[1]]
        timestr = _snap_get_timestr(self.group, self.pckloader)
        return dict(
            mX=X1, poloidal_spectrum=Y1, mmode=mmode, m=m,
            pX=X2, parallel_spectrum=Y2, pmode=pmode, p=p,
            title=r'$%s$, %s' % (fstr, timestr),
        ), acckwargs

    def _post_dig(self, results):
        r = results
        max_p = 1.05 * r['poloidal_spectrum'].max()
        ax1_calc = dict(LINE=[
            (r['mX'], r['poloidal_spectrum']),
            ([r['m'], r['m']], [0, max_p], r'$m_{pmax}=%d$' % r['m'])],
            xlabel='m', ylabel='poloidal spectrum',
            xlim=[0, r['mmode']])
        max_p = 1.05 * r['parallel_spectrum'].max()
        ax2_calc = dict(LINE=[
            (r['pX'], r['parallel_spectrum']),
            ([r['p'], r['p']], [0, max_p], r'$p_{pmax}=%d$' % r['p'])],
            xlabel='ktoroidal', ylabel='parallel spectrum',
            xlim=[0, r['pmode']])
        return dict(zip_results=[
            ('tmpl_line', 211, ax1_calc),
            ('tmpl_line', 212, ax2_calc),
        ], suptitle=r'%s, m=%d, p=%d' % (r['title'], r['m'], r['p']))


class SnapshotTimeFieldSpectrumDigger(SnapshotFieldSpectrumDigger):
    '''field or density poloidal and parallel spectra as time varied.'''
    __slots__ = []
    itemspattern = [
        '^(?P<section>snap)\d{5,7}'
        + '/fluxdata-(?P<field>(?:phi|apara|fluidne|densityi|densitye))',
        '^(?P<s>snap)\d{5,7}/mtgrid\+1',
        '^(?P<s>snap)\d{5,7}/mtoroidal']
    post_template = ('tmpl_z111p', 'tmpl_contourf', 'tmpl_line')

    def _dig(self, kwargs):
        '''*tcutoff*: [t0,t1], t0 t1 float
            t0<=time[x0:x1]<=t1
        '''
        assert len(self.srckeys) % 3 == 0
        index = len(self.srckeys) // 3
        mtgrid1, mtoroidal = self.pckloader.get_many(
            self.srckeys[index], self.srckeys[2*index])
        mtgrid = mtgrid1 - 1
        acckwargs = self._set_params(kwargs, mtgrid, mtoroidal)
        mmode, pmode = acckwargs['mmode'], acckwargs['pmode']
        X1, X2 = np.arange(1, mmode + 1), np.arange(1, pmode + 1)
        # rm first item in fluxdata
        all_fluxdata = self.pckloader.get_many(*self.srckeys[1:index])
        tstep = self.pckloader.get('gtc/tstep')
        tstep = round(tstep, Ndigits_tstep)
        time = [self.srckeys[idx].split('/')[0] for idx in range(index)]
        time = np.around(np.array(  # rm first item in time
            [int(t.replace('snap', '')) * tstep for t in time[1:]]), 5)
        if len(time) < 2:
            dlog.error("Less than 3 snapshots!")
            return {}, {}
        dt = time[-1] - time[-2]
        if 'tcutoff' not in self.kwoptions:
            self.kwoptions['tcutoff'] = dict(
                widget='FloatRangeSlider',
                rangee=[time[0], time[-1], dt],
                value=[time[0], time[-1]],
                description='time cutoff:')
        acckwargs['tcutoff'] = [time[0], time[-1]]
        i0, i1 = 0, time.size
        if 'tcutoff' in kwargs:
            t0, t1 = kwargs['tcutoff']
            idx = np.where((time >= t0) & (time < t1 + dt))[0]
            if idx.size > 0:
                i0, i1 = idx[0], idx[-1]+1
                acckwargs['tcutoff'] = [time[i0], time[i1-1]]
                time = time[i0:i1]
            else:
                dlog.warning('Cannot cutoff: %s <= time <= %s!' % (t0, t1))
        YT1, YT2, mY, pY = [], [], [], []
        dlog.info('%d snapshot fluxdata to do ...' % (i1 - i0))
        _idxlog = max(1, (i1 - i0) // 10)
        for idx in range(i0, i1):
            if idx % _idxlog == 0 or idx == i1 - 1:
                dlog.info('Calculating [%d/%d] %s' % (
                    idx+1-i0, i1 - i0, self.srckeys[idx]))
            fluxdata = all_fluxdata[idx]
            if fluxdata.shape != (mtgrid1, mtoroidal):
                dlog.error("Invalid fluxdata shape!")
                return {}, {}
            Y1, Y2, idx1, idx2 = self._get_spectrum(
                mmode, pmode, fluxdata, mtgrid, mtoroidal,
                acckwargs['smooth'], acckwargs['norm'])
            YT1.append(Y1)
            YT2.append(Y2)
            mY.append(X1[idx1])
            pY.append(X2[idx2])
        YT1, YT2 = np.array(YT1).T, np.array(YT2).T
        mY, pY = np.array(mY), np.array(pY)
        fstr = field_tex_str[self.section[1]]
        return dict(
            mX=X1, mY=mY, poloidal_spectrum=YT1, mmode=mmode,
            pX=X2, pY=pY, parallel_spectrum=YT2, pmode=pmode,
            time=time, fstr=r'$%s$' % fstr,
        ), acckwargs

    def _post_dig(self, results):
        r = results
        ax1_calc = dict(X=r['time'], Y=r['mX'], Z=r['poloidal_spectrum'],
                        xlabel=r'time($R_0/c_s$)', ylabel='m',
                        title=r'poloidal spectrum of %s' % r['fstr'],
                        xlim=[r['time'][0], r['time'][-1]])
        ax2_calc = dict(X=r['time'], Y=r['pX'], Z=r['parallel_spectrum'],
                        xlabel=r'time($R_0/c_s$)', ylabel='n',
                        title=r'parallel spectrum of %s' % r['fstr'],
                        xlim=[r['time'][0], r['time'][-1]])
        return dict(zip_results=[
            ('tmpl_contourf', 211, ax1_calc),
            ('tmpl_line', 211, dict(LINE=[(r['time'], r['mY'], 'max m')])),
            ('tmpl_contourf', 212, ax2_calc),
            ('tmpl_line', 212, dict(LINE=[(r['time'], r['pY'], 'max n')])),
        ])


class SnapshotFieldProfileDigger(Digger):
    '''field and rms or density radius poloidal profile'''
    __slots__ = []
    nitems = '+'
    itemspattern = [
        '^(?P<section>snap\d{5,7})'
        + '/poloidata-(?P<field>(?:phi|apara|fluidne|densityi|densitye))',
        '^(?P<s>snap\d{5,7})/mpsi\+1',
        '^(?P<s>snap\d{5,7})/mtgrid\+1']
    commonpattern = ['gtc/tstep']
    post_template = ('tmpl_z111p', 'tmpl_sharextwinx')

    def _set_fignum(self, numseed=None):
        self._fignum = '%s_profile' % self.section[1]
        self.kwoptions = None

    def _dig(self, kwargs):
        '''
        kwargs
        ------
        *jtgrid*, *ipsi*: int
            set poloidal and radius cut
        '''
        pdata, mpsi1, mtgrid1 = self.pckloader.get_many(*self.srckeys)
        if pdata.shape != (mtgrid1, mpsi1):
            dlog.error("Invalid poloidata shape!")
            return {}, {}
        jtgrid, ipsi = kwargs.get('jtgrid', None), kwargs.get('ipsi', None)
        if not (isinstance(jtgrid, int) and jtgrid < mtgrid1):
            jtgrid = 0
        if not (isinstance(ipsi, int) and ipsi < mpsi1):
            ipsi = (mpsi1 - 1) // 2
        acckwargs = dict(jtgrid=jtgrid, ipsi=ipsi)
        dlog.parm("Poloidal and radius cut: jtgrid=%s, ipsi=%s. "
                  "Maximal jtgrid=%s, ipsi=%s."
                  % (jtgrid, ipsi, mtgrid1 - 1, mpsi1 - 1))
        if self.kwoptions is None:
            self.kwoptions = dict(
                jtgrid=dict(
                    widget='IntSlider',
                    rangee=(0, mtgrid1 - 1, 1),
                    value=jtgrid,
                    description='jtgrid:'),
                ipsi=dict(
                    widget='IntSlider',
                    rangee=(0, mpsi1 - 1, 1),
                    value=ipsi,
                    description='ipsi:'))
        X1, Y11 = np.arange(0, mpsi1), pdata[jtgrid, :]
        X2 = np.arange(0, mtgrid1) / mtgrid1 * 2 * np.pi
        Y21 = pdata[:, ipsi]
        # f*f [ f[i,j]*f[i,j] ]; np.sum, axis=0, along col
        Y12 = np.sqrt(np.sum(pdata * pdata, axis=0) / mtgrid1)
        Y22 = np.sqrt(np.sum(pdata * pdata, axis=1) / mpsi1)
        fstr = field_tex_str[self.section[1]]
        timestr = _snap_get_timestr(self.group, self.pckloader)
        return dict(
            ipsi=X1, radius_profile=Y11, rms_radius_profile=Y12,
            title1=r'radius profile: jtgrid=%d ($\theta=%.2f=%.2f\degree$)' % (
                jtgrid, X2[jtgrid], jtgrid / mtgrid1 * 360),
            theta=X2, poloidal_profile=Y21, rms_poloidal_profile=Y22,
            title2='poloidal profile: ipsi=%d' % ipsi,
            suptitle=r'$%s$, %s' % (fstr, timestr)), acckwargs

    def _post_dig(self, results):
        r = results
        ax1_calc = dict(
            X=r['ipsi'], xlabel='r(mpsi)',
            YINFO=[{'left': [(r['radius_profile'], 'point value')],
                    'right': [(r['rms_radius_profile'], 'rms')],
                    'lylabel': 'point value', 'rylabel': 'RMS'}],
            title=r['title1'])
        ax2_calc = dict(
            X=r['theta'], xlabel=r'$\theta$',
            YINFO=[{'left': [(r['poloidal_profile'], 'point value')],
                    'right': [(r['rms_poloidal_profile'], 'rms')],
                    'lylabel': 'point value', 'rylabel': 'RMS'}],
            title=r['title2'])
        return dict(zip_results=[
            ('tmpl_sharextwinx', 211, ax1_calc),
            ('tmpl_sharextwinx', 212, ax2_calc),
        ], suptitle=r['suptitle'])


class SnapshotFieldmDigger(Digger):
    '''profile of field_m or density_m'''
    __slots__ = []
    nitems = '+'
    itemspattern = [
        '^(?P<section>snap\d{5,7})'
        + '/poloidata-(?P<field>(?:phi|apara|fluidne|densityi|densitye))',
        '^(?P<s>snap\d{5,7})/mpsi\+1',
        '^(?P<s>snap\d{5,7})/mtgrid\+1']
    commonpattern = ['gtc/tstep', 'gtc/arr2', 'gtc/a_minor']
    post_template = 'tmpl_line'

    def _set_fignum(self, numseed=None):
        self._fignum = '%s_fieldm' % self.section[1]
        self.kwoptions = None

    def _dig(self, kwargs):
        timestr = _snap_get_timestr(self.group, self.pckloader)
        fstr = field_tex_str[self.section[1]]
        pdata, mpsi1, mtgrid1, dt, arr2, a = self.pckloader.get_many(
            *self.srckeys, *self.common)
        if pdata.shape != (mtgrid1, mpsi1):
            dlog.error("Invalid poloidata shape!")
            return {}, {}
        rr = arr2[:, 1] / a
        fieldm = []
        for ipsi in range(1, mpsi1 - 1):
            y = pdata[:, ipsi]
            dy_ft = np.fft.fft(y)/mtgrid1 * 2  # why /mtgrid1 * 2
            fieldm.append(abs(dy_ft[:mtgrid1//2]))
        fieldm = np.array(fieldm).T
        jlist, acckwargs, rr_s, Y_s, dr, dr_fwhm, envY, envXp, envYp, envXmax, envYmax = \
            self._remove_add_some_lines(fieldm, rr, kwargs)
        return dict(rr=rr, fieldm=fieldm, jlist=jlist,
                    rr_s=rr_s, Y_s=Y_s, dr=dr, dr_fwhm=dr_fwhm,
                    envY=envY, envXp=envXp, envYp=envYp,
                    envXmax=envXmax, envYmax=envYmax,
                    title=r'$\left|{%s}_m(r)\right|$, %s' % (fstr, timestr)
                    ), acckwargs

    def _remove_add_some_lines(self, fieldm, rr, kwargs):
        '''
        kwargs
        ------
        *ymaxlimit*: float, default 0
            if (ymax of line) < ymaxlimit * (ymax of lines), then remove it.
        *ymaxselect*: int, default 0
            when *ymaxlimit* is not set, select the *ymaxselect*th biggest ymax lines
        *cal_dr*: bool,  default False
            calculate Delta r of mode structure for the select lines
        *envelope*: bool
            add high envelope or not, default False
        *kind*: str or odd int
            the kind of interpolation for envelope, default 'cubic'
            see class scipy.interpolate.interpolate.interp1d
        '''
        if self.kwoptions is None:
            self.kwoptions = dict(
                ymaxlimit=dict(widget='FloatSlider',
                               rangee=(0, 1, 0.05),
                               value=0.0,
                               description='ymaxlimit:'),
                ymaxselect=dict(widget='IntSlider',
                                rangee=[0, fieldm.shape[0], 1],
                                value=0,
                                description='ymaxselect:'),
                cal_dr=dict(widget='Checkbox',
                            value=False,
                            description='cal_dr of mode structure'),
                envelope=dict(widget='Checkbox',
                              value=False,
                              description='add envelope'),
                kind=dict(widget='Dropdown',
                          options=['linear', 'quadratic', 'cubic', 5, 7, 11],
                          value='cubic',
                          description='interp kind:'))
        ymaxlimit = kwargs.get('ymaxlimit', 0.0)
        ymaxselect = kwargs.get('ymaxselect', 0)
        cal_dr = False
        if isinstance(ymaxlimit, float) and 0 < ymaxlimit < 1:
            maxlimit = fieldm.max() * ymaxlimit
            jpass = fieldm.max(axis=1) >= maxlimit
            jlist = [i for i, j in enumerate(jpass) if j]
        elif isinstance(ymaxselect, int) and ymaxselect > 0:
            indices1 = fieldm.argmax(axis=1)
            data = fieldm[np.arange(fieldm.shape[0]), indices1]
            indices0 = data.argsort()[-ymaxselect:]  # index of select lines
            rr_s = rr[indices1[indices0]]
            # sort by rr
            jlist = list(indices0[rr_s.argsort()])  # 0 -> ymaxselect-1
            cal_dr = bool(kwargs.get('cal_dr', False))
        else:
            jlist = 'all'
        if cal_dr:
            rr_s.sort()
            Y_s = data[jlist]
            dr = np.average(np.diff(rr_s))
            # dr by fwhm
            _drs = []
            for j in jlist:
                _X, _Y = tools.near_peak(
                    fieldm[j], X=rr, intersection=True,
                    lowerlimit=1.0/2.0, select='1')
                _drs.append(_X[-1]-_X[0])
            dr_fwhm = np.average(_drs)
        else:
            rr_s, Y_s, dr, dr_fwhm = 'n', 'n', 'n', 'n'
        envelope = kwargs.get('envelope', False)
        kind = kwargs.get('kind', 'cubic')
        if envelope:
            maxfm = fieldm.max(axis=0)
            tmp = np.gradient(maxfm, rr)
            zerolimit = tmp.max()*1e-6
            add_indexs = []
            # increase
            for i in range(len(tmp)//2):
                if tmp[i] >= - zerolimit:
                    add_indexs.append(i)
                else:
                    break
            # decrease
            for i in range(len(tmp)-1, len(tmp)//2, -1):
                if tmp[i] <= zerolimit:
                    add_indexs.append(i)
                else:
                    break
            Y = tools.high_envelope(
                maxfm, X=rr, kind=kind, add_indexs=add_indexs)
            newX, newY = tools.near_peak(
                Y, X=rr, intersection=True, lowerlimit=1.0/np.e, select='1')
            idxmax = np.argmax(newY)
            Xmax, Ymax = newX[idxmax], newY[idxmax]
        else:
            Y, newX, newY, Xmax, Ymax = 'n', 'n', 'n', 'n', 'n'
        acckwargs = dict(ymaxlimit=ymaxlimit,
                         ymaxselect=ymaxselect, cal_dr=cal_dr,
                         envelope=envelope, kind=kind)
        return jlist, acckwargs, rr_s, Y_s, dr, dr_fwhm, Y, newX, newY, Xmax, Ymax

    _dig.__doc__ = _remove_add_some_lines.__doc__

    def _post_dig(self, results):
        r = results
        if r['jlist'] == 'all':
            mt, _ = r['fieldm'].shape
            jlist = range(mt)
        else:
            jlist = r['jlist']
        LINE = [(r['rr'], r['fieldm'][j, :]) for j in jlist]
        if r['dr'] != 'n':
            LINE.append(
                (r['rr_s'], r['Y_s'], r'$\delta r/a(gap,fwhm)=%.6f,%.6f$'
                 % (r['dr'], r['dr_fwhm'])))
        if type(r['envY']) is np.ndarray and type(r['envYp']) is np.ndarray:
            LINE.append((r['rr'], r['envY'],
                         'envelope, $r/a(max)=%.6f$' % r['envXmax']))
            dx = r['envXp'][-1] - r['envXp'][0]
            halfY = r['envYmax'] / np.e
            flatYp = np.linspace(halfY, halfY, len(r['envXp']))
            LINE.append((r['envXp'], flatYp, r'$\Delta r/a(1/e) = %.6f$' % dx))
        r0, r1 = np.round(r['rr'][[0, -1]], decimals=2)
        return dict(LINE=LINE, title=r['title'],
                    xlabel=r'$r/a$', xlim=[r0, r1])


class BreakDigDoc(Digger):
    pass


class SnapshotFieldmkthetaDigger(BreakDigDoc, SnapshotFieldmDigger):
    '''contour/average profile of field_m or density_m'''
    __slots__ = []
    post_template = ('tmpl_z111p', 'tmpl_contourf', 'tmpl_line')

    def _set_fignum(self, numseed=None):
        self._fignum = '%s_fieldmktheta' % self.section[1]
        self.kwoptions = None

    def _dig(self, kwargs):
        '''
        kwargs
        ------
        *m_max*: int, default mtgrid1//5
        *mean_weight_order*: int
            use fieldm^mean_weight_order as weight to average(m), default 4
        '''
        if self.kwoptions is None:
            self.kwoptions = dict(
                mean_weight_order=dict(widget='IntSlider',
                                       rangee=(2, 8, 2),
                                       value=4,
                                       description='mean m weight order:'))
        data, _ = super(SnapshotFieldmkthetaDigger, self)._dig(kwargs)
        rr, fieldm, title = data['rr'], data['fieldm'], data['title']
        maxmmode = fieldm.shape[0]*2//5  # (mtgrid1//2)*2//5
        m_max = kwargs.get('m_max', None)
        if not (isinstance(m_max, int) and m_max <= maxmmode):
            m_max = maxmmode
        m = np.arange(1, m_max + 1)
        fieldm = fieldm[:m_max, :]
        order = kwargs.get('mean_weight_order', 2)
        rho0, a = self.pckloader.get_many('gtc/rho0', 'gtc/a_minor')
        m2_r = np.array([np.average(m**order, weights=fieldm[:, i]**order)
                         for i in range(rr.size)])
        mean_m = np.power(m2_r, 1.0/order)
        ktrho0 = mean_m/(rr*a)*rho0
        dlog.parm("at r=0.5a, mean m=%.1f." % mean_m[rr.size//2])
        if 'm_max' not in self.kwoptions:
            self.kwoptions['m_max'] = dict(widget='IntSlider',
                                           rangee=(10, maxmmode, 10),
                                           value=maxmmode,
                                           description='m max limit:')
        acckwargs = dict(m_max=m_max, mean_weight_order=order)
        return dict(rr=rr, m=m, fieldm=fieldm, title=title,
                    mean_m=mean_m, ktrho0=ktrho0), acckwargs

    def _post_dig(self, results):
        r = results
        zip_results = [
            ('tmpl_contourf', 211, dict(
                X=r['rr'], Y=r['m'], Z=r['fieldm'], title=r['title'],
                xlabel=r'$r/a$', ylabel=r'm')),
            ('tmpl_line', 211, dict(LINE=[(r['rr'], r['mean_m'], 'mean m')])),
            ('tmpl_line', 212, dict(
                LINE=[(r['rr'], r['ktrho0'], r'mean m')],
                xlabel='r/a', ylabel=r'$k_{\theta}\rho_0$')),
        ]
        return dict(zip_results=zip_results)
