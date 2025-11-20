from pathlib import Path
from itertools import filterfalse

from one.api import OneAlyx
from one.alf.spec import is_uuid_string
import one.params as oneparams

from ibllib.oneibl.data_handlers import SDSCDataHandler, DataHandler
from ibllib.oneibl.patcher import S3Patcher

S3_MOUNT_DATA_PATH = Path('/teamspace/s3_connections/ibl-brain-wide-map-private/data')
CACHE_REST = Path('/teamspace/studios/this_studio/Downloads/ONE/s3mount')
LIGHTNING_AI_PATCH_PATH = Path('/teamspace/studios/this_studio/data')


class OneLightningAI(OneAlyx):
    def __init__(self, *args, cache_dir=S3_MOUNT_DATA_PATH, cache_rest=CACHE_REST, **kwargs):
        if not kwargs.get('tables_dir'):
            # Ensure parquet tables downloaded to separate location to the dataset repo
            kwargs['tables_dir'] = oneparams.get_cache_dir()  # by default this is user downloads
        super().__init__(*args, cache_dir=cache_dir, cache_rest=str(cache_rest), **kwargs)
        # assign property here as it is set by the parent OneAlyx class at init
        self.uuid_filenames = True

    def load_object(self, *args, **kwargs):
        # call superclass method
        obj = super().load_object(*args, **kwargs)
        if isinstance(obj, list) or not self.uuid_filenames:
            return obj
        # pops the UUID in the key names
        for k in list(obj.keys()):
            new_key = '.'.join(filterfalse(is_uuid_string, k.split('.')))
            obj[new_key] = obj.pop(k)
        return obj

    def _download_datasets(self, dset, **kwargs):
        """Simply return list of None."""
        urls = self._dset2url(dset, update_cache=False)  # normalizes input to list
        return [None] * len(urls)


class LightningAIDataHandler(SDSCDataHandler):
    def __init__(self, session_path, signatures, one=None):
        super().__init__(session_path, signatures, one=one)
        self.patch_path = Path(LIGHTNING_AI_PATCH_PATH)
        self.root_path = Path(S3_MOUNT_DATA_PATH)

    def cleanUp(self, **_):
        """Symlinks are preserved until registration."""
        pass

    def uploadData(self, outputs, version, **kwargs):
        """
        Function to upload and register data of completed task via S3 patcher
        :param outputs: output files from task to register
        :param version: ibllib version
        :return: output info of registered datasets
        """
        versions = DataHandler.uploadData(self, outputs, version)
        s3_patcher = S3Patcher(one=self.one)
        return s3_patcher.patch_dataset(outputs, created_by=self.one.alyx.user, versions=versions, **kwargs)


def _test_one_sdsc():
    """
    I have put the tests here
    :return:
    """
    from brainbox.io.one import SpikeSortingLoader, SessionLoader

    one = OneLightningAI()
    pid = '069c2674-80b0-44b4-a3d9-28337512967f'
    eid, _ = one.pid2eid(pid)
    dsets = one.list_datasets(eid=eid)
    assert len(dsets) > 0
    # checks that this is indeed the short key version when using load object
    trials = one.load_object(eid, obj='trials')
    assert 'intervals' in trials
    # checks that this is indeed the short key version when using the session loader and spike sorting loader
    sl = SessionLoader(eid=eid, one=one)  # noqa
    sl.load_wheel()
    assert 'position' in sl.wheel.columns
    ssl = SpikeSortingLoader(pid=pid, one=one)
    channels = ssl.load_channels()
    assert channels['x'].size == 384
