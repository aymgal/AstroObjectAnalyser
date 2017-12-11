__author__ = 'sibirrer'

import numpy as np
import scipy.ndimage.interpolation as interp
import copy

import astrofunc.util as util
from astrofunc.util import Util_class
util_class = Util_class()

from astroObjectAnalyser.DataAnalysis.psf_fitting import Fitting
from astroObjectAnalyser.DataAnalysis.catalogues import Catalogue


class Analysis(Catalogue):
    """
    class which analyses data and fits a psf
    """

    def get_psf(self, image, cat, mean, rms, poisson, psf_type='moffat', restrict_psf=None, kwargs_cut=None
                , cutfixed=31, symmetry=1):
        """
        fit a given psf model
        :param image: cutout image to fit a profile on
        :param mean: mean background level
        :param rms: rms value of background
        :param poisson: reduction factor for poisson noise
        :return: parameters of the psf model
        """
        if kwargs_cut is None:
            kwargs_cut = self.estimate_star_thresholds(cat)
        mask = self.find_objects(cat, kwargs_cut)
        star_list = self.get_objects_image(image, cat, mask, cut_fixed=cutfixed)
        fitting = Fitting()
        mean_list = fitting.fit_sample(star_list, mean, rms, poisson, n_walk=50, n_iter=50, threadCount=1, psf_type=psf_type)
        kernel, mean_list, restrict_psf, star_list_shift = self.stacking(star_list, mean_list, mean, psf_type
                                                                         , restrict_psf=restrict_psf, symmetry=symmetry)
        return kernel, mean_list, restrict_psf, star_list_shift

    def stacking(self, star_list, mean_list, mean, psf_type, restrict_psf=None, symmetry=1):
        """

        :param star_list:
        :return:
        """
        num_stars = len(star_list)
        if restrict_psf is None:
            restrict_psf = [True]*num_stars
        shifteds = []
        mean_list_select = []
        for i in range(num_stars):
            if restrict_psf[i] is True:
                data = star_list[i]-mean
                if psf_type == 'gaussian' or psf_type == 'pixel':
                    amp, sigma, center_x, center_y = mean_list[i]
                elif psf_type == 'moffat':
                    amp, alpha, beta, center_x, center_y = mean_list[i]
                else:
                    raise ValueError('psf type %s not valid' % psf_type)
                data[data < 0] = 0
                #shifted = interp.shift(data, [-center_y-0.5, -center_x-0.5], order=2)
                shifted = util.de_shift_kernel(data, shift_x=-center_x-0.5, shift_y=-center_y-0.5)
                sym_shifted = util_class.symmetry_average(shifted, symmetry)
                shifteds.append(sym_shifted)
                mean_list_select.append(mean_list[i])
                print('=== object ===', i, center_x, center_y)
                import matplotlib.pylab as plt
                fig, ax1 = plt.subplots()
                im = ax1.matshow(np.log10(sym_shifted), origin='lower')
                plt.axes(ax1)
                fig.colorbar(im)
                plt.show()

        combined = sum(shifteds)
        mean_list_select = np.mean(mean_list_select[:])
        """
        new = np.empty_like(combined)
        max_pix = np.max(combined)
        p = combined[combined >= max_pix/10**6]  #in the SIS regime
        new[combined < max_pix/10**6] = 0
        new[combined >= max_pix/10**6] = p
        """
        kernel = util.kernel_norm(combined)
        return kernel, mean_list_select, restrict_psf, shifteds

    def get_psf_kwargs_update(self, psf_type, image, exp_time, HDUFile, pixelScale, psf_size=None, psf_size_large=91, filter_object=None, kwargs_cut={}):
        """
        does the same as get_psf_kwargs but can also restrict itself to specially chosen objects
        :param image_name:
        :param psf_type:
        :param psf_size:
        :param filter_object:
        :return:
        """
        kernel_large, mean_list, restrict_psf, star_list = self.get_psf(HDUFile, image, exp_time, psf_type, filter_object, kwargs_cut)
        if psf_type == 'gaussian':
            sigma = mean_list[1]*pixelScale
            psf_kwargs = {'psf_type': psf_type, 'sigma': sigma}
        elif psf_type == 'moffat':
            alpha = mean_list[1]
            beta = mean_list[2]
            alpha *= pixelScale
            psf_kwargs = {'psf_type': psf_type, 'alpha': alpha, 'beta': beta}
        elif psf_type == 'pixel':
            kernel = util.cut_edges(kernel_large, psf_size)
            kernel = util.kernel_norm(kernel)
            kernel_large = util.cut_edges(kernel_large, psf_size_large)
            kernel_large = util.kernel_norm(kernel_large)
            kernel_list = []
            for i in range(len(star_list)):
                if i == 0:
                   kernel_list.append(kernel_large)
                else:
                    star = star_list[i]
                    kernel_star = util.cut_edges(star, psf_size_large)
                    kernel_star = util.kernel_norm(kernel_star)
                    kernel_list.append(kernel_star-kernel_large)
            psf_kwargs = {'psf_type': psf_type, 'kernel': kernel, 'kernel_large': kernel_large, 'kernel_list': kernel_list}
        else:
            raise ValueError('psf type %s not in list' % psf_type)
        return psf_kwargs, restrict_psf, star_list

    def get_psf_errors(self, kernel, sigma_bkg, star_list):
        """
        returns a error map of sigma prop Intensity for a stacked psf estimation
        :param psf_kwargs:
        :param star_list:
        :return:
        """
        psf_size = len(kernel)
        kernel_mean = util.image2array(kernel)
        weights = np.zeros(len(star_list))
        cov_i = np.zeros((psf_size**2,psf_size**2))
        num_stars = len(star_list)
        for i in range(0, num_stars):
            star_list_i = star_list[i].copy()
            star = util.cut_edges(star_list_i, psf_size)
            weights[i] = np.sum(star)
            rel_array = np.array([util.image2array(star)/weights[i]-kernel_mean])
            a = (rel_array.T).dot(rel_array)
            cov_i += a
        factor = 1./(num_stars)
        #weights_sum = sum(weights)
        sigma2_stack = factor*util.array2image(np.diag(cov_i))
        psf_stack = copy.deepcopy(kernel)
        sigma2_stack_new = sigma2_stack# - (data_kwargs['sigma_background']**2/weights_sum)
        sigma2_stack_new[np.where(sigma2_stack_new < 0)] = 0
        psf_stack[np.where(psf_stack < sigma_bkg)] = sigma_bkg
        error_map = sigma2_stack_new/(psf_stack)**2
        #error_map[np.where(error_map < psf_stack**2/data_kwargs['reduced_noise'])] = 0
        # n = len(error_map)
        #error_map[(n-1)/2-1:(n-1)/2+2,(n-1)/2-1:(n-1)/2+2] += 0
        #error_map = filters.gaussian_filter(error_map, sigma=0.5)
        return error_map
