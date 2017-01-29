


"""
Tests for `lenstronomy` module.
"""
from __future__ import print_function, division, absolute_import

import os

import pytest
from mock import patch
from darkskysync.DataSourceFactory import DataSourceFactory

from astroObjectAnalyser.data_collection.data_manager import DataManager


class TestDataManager(object):

    @patch.object(DataSourceFactory, "fromConfig", autospec=False)
    def setup(self, dsf_object):
        #prepare unit test. Load data etc
        print("setting up " + __name__)
        test_dir = os.path.dirname(__file__)
        sysdata_filepath = os.path.join(test_dir, 'Test_data', 'RXJ1131_1231.sysdata')
        self.fits_example = os.path.join(test_dir, 'Test_data', 'RXJ1131_1231_74010_cutout.fits')
        self.files = [sysdata_filepath, sysdata_filepath]
        self.datamanager = DataManager()

    def test_from_sysdata_files(self):
        data_list = self.datamanager._from_sysdata_files(self.files)
        assert len(data_list) == 2
        RXJ1131 = data_list[0]
        assert len(RXJ1131.data_cat) == 6
        assert RXJ1131.data_cat.name == 'RXJ1131-1231'
        assert RXJ1131.data_cat.ra_str == '11:31:51.4'
        assert RXJ1131.data_cat.dec_str == '-12:31:59'
        assert RXJ1131.data_cat.radius_est == '1.7'
        assert RXJ1131.data_cat.z_source == '0.658'
        assert RXJ1131.data_cat.z_lens == '0.295'

    def test_get_data(self):

        data_list = self.datamanager.get_data(self.files,datatype='sysdata_file')
        data_list2 = self.datamanager._from_sysdata_files(self.files)
        assert data_list == data_list2

    def teardown(self):
        #tidy up
        print("tearing down " + __name__)
        pass

if __name__ == '__main__':
    pytest.main("-k TestDataManager")

