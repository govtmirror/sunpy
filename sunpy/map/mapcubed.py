"""A Python MapCube Object"""
from __future__ import absolute_import, division, print_function
#pylint: disable=W0401,W0614,W0201,W0212,W0404

from copy import deepcopy

import numpy as np
import matplotlib.animation

from sunpy.map import GenericMap
from sunpy.map.map_factory import Map
from sunpy.visualization.mapcubeanimator import MapCubeAnimator
from sunpy.visualization import wcsaxes_compat
from sunpy.util import expand_list
from sunpy.extern.six.moves import range
import astropy.units as u

from sunpy import config
TIME_FORMAT = config.get("general", "time_format")

__all__ = ['MapCubed']


class MapCubed(object):
    """
    MapCube

    A series of spatially aligned Maps of the same size.

    Parameters
    ----------
    args : {List}
        A list of Map instances
    sortby : {"date", None}
        Method by which the MapCube should be sorted along the z-axis.
    derotate : {None}
        Apply a derotation to the data (Not Implemented)

    To coalign a mapcube so that solar features remain on the same pixels,
    please see the "Coalignment of mapcubes" note below.

    Attributes
    ----------
    maps : {List}
        This attribute holds the list of Map instances obtained from parameter args.

    Examples
    --------
    >>> import sunpy.map
    >>> mapcube = sunpy.map.Map('images/*.fits', cube=True)   # doctest: +SKIP

    Mapcubes can be co-aligned using the routines in sunpy.image.coalignment.
    """
    #pylint: disable=W0613,E1101
    def __init__(self, *args, **kwargs):
        """Creates a new Map instance"""

        # Hack to get around Python 2.x not backporting PEP 3102.
        sortby = kwargs.pop('sortby', 'date')
        derotate = kwargs.pop('derotate', False)

        maps = expand_list(args)

        for m in maps:
            if not isinstance(m, GenericMap):
                raise ValueError(
                           'MapCubed expects pre-constructed map objects.')

        maps.sort(key=self._sort_by_date())

        # test if all maps have the same shape
        if not np.all([m.data.shape == maps[0].data.shape for m in maps]):
            raise ValueError("All Map data must have the same dimensions")

        # test if all maps have the same scale
        if not np.all([m.scale == maps[0].scale for m in maps]):
            raise ValueError("All Map data must have the same scale")

        self.data = np.zeros((maps[0].data.shape[0], maps[0].data.shape[1], len(maps)), dtype=maps[0].data.dtype)
        self._meta = []
        for i, m in enumerate(maps):
            self.data[:,:,i] = m.data
            self._meta.append(m.meta)

        self._maps = maps

    def __getitem__(self, key):
        """Overriding indexing operation.  If the key results in a single map,
        then a map object is returned.  This allows functions like enumerate to
        work.  Otherwise, a mapcube is returned."""

        if isinstance(self._maps[key], GenericMap):
            return self._maps[key]
        else:
            return MapCube(self._maps[key])

    def __len__(self):
        """Return the number of maps in a mapcube."""
        return len(self._maps)

    def __repr__(self):
        if not self.observatory:
            return self.data.__repr__()
        return (
"""SunPy {dtype!s}
---------
Observatory:\t {obs}
Instrument:\t {inst}
Detector:\t {det}
Measurement:\t {meas}
Wavelength:\t {wave}
Obs Date:\t {date:{tmf}}
dt:\t\t {dt:f}
Dimension:\t {dim}
scale:\t\t {scale}

""".format(dtype=self.__class__.__name__,
           obs=self.observatory, inst=self.instrument, det=self.detector,
           meas=self.measurement, wave=self.wavelength, date=self.date, dt=self.exposure_time,
           dim=u.Quantity(self.dimensions),
           scale=u.Quantity(self.scale),
           tmf=TIME_FORMAT)
+ self.data.__repr__())

    # Sorting methods
    @classmethod
    def _sort_by_date(cls):
        return lambda m: m.date # maps.sort(key=attrgetter('date'))

    def _derotate(self):
        """Derotates the layers in the MapCube"""
        pass

    @property
    def instrument(self):
        """Instrument name"""
        return self._maps[0].meta.get('instrume', "").replace("_", " ")

    @property
    def measurement(self):
        """Measurement name, defaults to the wavelength of image"""
        return u.Quantity(self._maps[0].meta.get('wavelnth', 0), self._maps[0].meta.get('waveunit', ""))

    @property
    def wavelength(self):
        """wavelength of the observation"""
        return u.Quantity(self._maps[0].meta.get('wavelnth', 0), self._maps[0].meta.get('waveunit', ""))

    @property
    def observatory(self):
        """Observatory or Telescope name"""
        return self._maps[0].meta.get('obsrvtry', self._maps[0].meta.get('telescop', "")).replace("_", " ")

    @property
    def detector(self):
        """Detector name"""
        return self._maps[0].meta.get('detector', "")

    @property
    def dimensions(self):
        """
        The dimensions of the array (x axis first, y axis second).
        """
        return self._maps[0].dimensions

    @property
    def dtype(self):
        """
        The `numpy.dtype` of the array of the map.
        """
        return self.data.dtype

    @property
    def date(self):
        """Observation time"""
        time = []
        for m in self._maps:
            time.append(m.date)
        return time

    @property
    def scale(self):
        """Image scale along the x and y axes in units/pixel (i.e. cdelt1, cdelt2)"""
        #TODO: Fix this if only CDi_j matrix is provided
        return self._maps[0].scale

    @property
    def units(self):
        """Image coordinate units along the x and y axes (i.e. cunit1, cunit2)."""
        return self._maps[0].units

    @property
    def exposure_time(self):
        """Exposure time of the image in seconds."""
        return self.meta('exptime') * u.s

    def meta(self, key):
        """The Meta."""
        result = [meta[key] for meta in self._meta]
        # check to see if they are all the same if so just return one value
        if np.all([r == result[0] for r in result]):
            result = result[0]
        return result

    @property
    def rotation_matrix(self):
        return self._maps[0].rotation_matrix

    def submap(self, range_a, range_b):
        """
        """
        new_maps = []
        for m in self._maps:
            new_map = deepcopy(m)
            new_maps.append(new_map.submap(range_a, range_b))
        return MapCubed(new_maps)

    @u.quantity_input(dimensions=u.pixel)
    def superpixel(self, dimensions, method='sum'):
        """
        """
        new_maps = []
        for m in self._maps:
            new_map = deepcopy(m)
            new_maps.append(new_map.superpixel(dimensions, method=method))
        return MapCubed(new_maps)

    @u.quantity_input(dimensions=u.pixel)
    def resample(self, dimensions, method='linear'):
        """Returns a new Map that has been resampled up or down"""
        new_maps = []
        for m in self._maps:
            new_maps.append(m.resample(dimensions, method=method))
        return self.__init__(new_maps)

    def std(self):
        """
        Calculate the standard deviation of the data array.
        """
        return Map((np.std(self.data, axis=2), self._meta[0]))

    def mean(self, *args, **kwargs):
        """
        Calculate the mean of the data array.
        """
        return Map((np.mean(self.data, axis=2), self._meta[0]))

    def min(self, *args, **kwargs):
        """
        Calculate the minimum value of the data array.
        """
        return Map((np.min(self.data, axis=2), self._meta[0]))

    def max(self, *args, **kwargs):
        """
        Calculate the maximum value of the data array.
        """
        return Map((np.max(self.data, axis=2), self._meta[0]))

    def plot(self, axes=None, resample=None, annotate=True,
             interval=200, plot_function=None, **kwargs):
        """
        A animation plotting routine that animates each element in the
        MapCube

        Parameters
        ----------
        gamma: float
            Gamma value to use for the color map

        axes: mpl axes
            axes to plot the animation on, if none uses current axes

        resample: list or False
            Draws the map at a lower resolution to increase the speed of
            animation. Specify a list as a fraction i.e. [0.25, 0.25] to
            plot at 1/4 resolution.
            [Note: this will only work where the map arrays are the same size]

        annotate: bool
            Annotate the figure with scale and titles

        interval: int
            Animation interval in ms

        plot_function : function
            A function to be called as each map is plotted. Any variables
            returned from the function will have their ``remove()`` method called
            at the start of the next frame so that they are removed from the plot.

        Examples
        --------
        >>> import matplotlib.pyplot as plt
        >>> import matplotlib.animation as animation
        >>> from sunpy.map import Map

        >>> cube = Map(files, cube=True)   # doctest: +SKIP
        >>> ani = cube.plot(colorbar=True)   # doctest: +SKIP
        >>> plt.show()   # doctest: +SKIP

        Plot the map at 1/2 original resolution

        >>> cube = Map(files, cube=True)   # doctest: +SKIP
        >>> ani = cube.plot(resample=[0.5, 0.5], colorbar=True)   # doctest: +SKIP
        >>> plt.show()   # doctest: +SKIP

        Save an animation of the MapCube

        >>> cube = Map(res, cube=True)   # doctest: +SKIP

        >>> ani = cube.plot()   # doctest: +SKIP

        >>> Writer = animation.writers['ffmpeg']   # doctest: +SKIP
        >>> writer = Writer(fps=10, metadata=dict(artist='SunPy'), bitrate=1800)   # doctest: +SKIP

        >>> ani.save('mapcube_animation.mp4', writer=writer)   # doctest: +SKIP

        Save an animation with the limb at each time step

        >>> def myplot(fig, ax, sunpy_map):
        ...    p = sunpy_map.draw_limb()
        ...    return p
        >>> cube = Map(files, cube=True)   # doctest: +SKIP
        >>> ani = cube.peek(plot_function=myplot)   # doctest: +SKIP
        >>> plt.show()   # doctest: +SKIP

        """
        if not axes:
            axes = wcsaxes_compat.gca_wcs(self._maps[0].wcs)
        fig = axes.get_figure()

        if not plot_function:
            plot_function = lambda fig, ax, smap: []
        removes = []

        # Normal plot
        def annotate_frame(i):
            axes.set_title("{s.name}".format(s=self[i]))

            # x-axis label
            if self[0].coordinate_system.x == 'HG':
                xlabel = 'Longitude [{lon}'.format(lon=self[i].units.x)
            else:
                xlabel = 'X-position [{xpos}]'.format(xpos=self[i].units.x)

            # y-axis label
            if self[0].coordinate_system.y == 'HG':
                ylabel = 'Latitude [{lat}]'.format(lat=self[i].units.y)
            else:
                ylabel = 'Y-position [{ypos}]'.format(ypos=self[i].units.y)

            axes.set_xlabel(xlabel)
            axes.set_ylabel(ylabel)

        if resample:
            # This assumes that the maps are homogeneous!
            # TODO: Update this!
            resample = np.array(len(self._maps)-1) * np.array(resample)
            ani_data = [x.resample(resample) for x in self._maps]
        else:
            ani_data = self._maps

        im = ani_data[0].plot(axes=axes, **kwargs)

        def updatefig(i, im, annotate, ani_data, removes):
            while removes:
                removes.pop(0).remove()

            im.set_array(ani_data[i].data)
            im.set_cmap(self._maps[i].plot_settings['cmap'])

            norm = deepcopy(self._maps[i].plot_settings['norm'])
            # The following explicit call is for bugged versions of Astropy's ImageNormalize
            norm.autoscale_None(ani_data[i].data)
            im.set_norm(norm)

            if wcsaxes_compat.is_wcsaxes(axes):
                im.axes.reset_wcs(self._maps[i].wcs)
                wcsaxes_compat.default_wcs_grid(axes)
            else:
                im.set_extent(np.concatenate((self._maps[i].xrange.value,
                                              self._maps[i].yrange.value)))

            if annotate:
                annotate_frame(i)
            removes += list(plot_function(fig, axes, self._maps[i]))

        ani = matplotlib.animation.FuncAnimation(fig, updatefig,
                                                frames=list(range(0, len(self._maps))),
                                                fargs=[im, annotate, ani_data, removes],
                                                interval=interval,
                                                blit=False)

        return ani

    def peek(self, resample=None, **kwargs):
        """
        A animation plotting routine that animates each element in the
        MapCube

        Parameters
        ----------
        fig: mpl.figure
            Figure to use to create the explorer

        resample: list or False
            Draws the map at a lower resolution to increase the speed of
            animation. Specify a list as a fraction i.e. [0.25, 0.25] to
            plot at 1/4 resolution.
            [Note: this will only work where the map arrays are the same size]

        annotate: bool
            Annotate the figure with scale and titles

        interval: int
            Animation interval in ms

        colorbar: bool
            Plot colorbar

        plot_function : function
            A function to call to overplot extra items on the map plot.
            For more information see `sunpy.visualization.MapCubeAnimator`.

        Returns
        -------
        mapcubeanim : `sunpy.visualization.MapCubeAnimator`
            A mapcube animator instance.

        See Also
        --------
        sunpy.visualization.mapcubeanimator.MapCubeAnimator

        Examples
        --------
        >>> import matplotlib.pyplot as plt
        >>> from sunpy.map import Map

        >>> cube = Map(files, cube=True)   # doctest: +SKIP
        >>> ani = cube.peek(colorbar=True)   # doctest: +SKIP
        >>> plt.show()   # doctest: +SKIP

        Plot the map at 1/2 original resolution

        >>> cube = Map(files, cube=True)   # doctest: +SKIP
        >>> ani = cube.peek(resample=[0.5, 0.5], colorbar=True)   # doctest: +SKIP
        >>> plt.show()   # doctest: +SKIP

        Plot the map with the limb at each time step

        >>> def myplot(fig, ax, sunpy_map):
        ...    p = sunpy_map.draw_limb()
        ...    return p
        >>> cube = Map(files, cube=True)   # doctest: +SKIP
        >>> ani = cube.peek(plot_function=myplot)   # doctest: +SKIP
        >>> plt.show()   # doctest: +SKIP

        Decide you want an animation:

        >>> cube = Map(files, cube=True)   # doctest: +SKIP
        >>> ani = cube.peek(resample=[0.5, 0.5], colorbar=True)   # doctest: +SKIP
        >>> mplani = ani.get_animation()   # doctest: +SKIP
        """

        if resample:
            if self.all_maps_same_shape():
                resample = np.array(len(self._maps) - 1) * np.array(resample)
                for amap in self._maps:
                    amap.resample(resample)
            else:
                raise ValueError('Maps in mapcube do not all have the same shape.')

        return MapCubeAnimator(self, **kwargs)

    def all_maps_same_shape(self):
        """
        Tests if all the maps have the same number pixels in the x and y
        directions.
        """
        return np.all([m.data.shape == self._maps[0].data.shape for m in self._maps])

    def as_array(self):
        """
        If all the map shapes are the same, their image data is copied
        into a single single ndarray. The ndarray is ordered as (ny, nx, nt).
        Otherwise, a ValueError is thrown.
        """
        if self.all_maps_same_shape():
            return np.swapaxes(np.swapaxes(np.asarray([m.data for m in self._maps]), 0, 1).copy(), 1, 2).copy()
        else:
            raise ValueError('Not all maps have the same shape.')

    def all_meta(self):
        """
        Return all the meta objects as a list.
        """
        return [m.meta for m in self._maps]