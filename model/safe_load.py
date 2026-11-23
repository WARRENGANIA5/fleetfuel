"""Load an uploaded .joblib model without running arbitrary code.

A .joblib file is a pickle, and unpickling can call any Python function.
This loader only lets the file name the classes a FleetFuel model is made
of (scikit-learn Pipeline, the two model.preprocess steps, numpy arrays and
joblib's array wrapper). Anything else is refused before it is created,
including inside arrays of Python objects (such as the feature names), which
joblib would otherwise read with the plain, unrestricted pickle module.
"""
import io
import pickle

from joblib.numpy_pickle import NumpyArrayWrapper, NumpyUnpickler
from joblib.numpy_pickle_utils import _read_fileobject

# (module, name) pairs a FleetFuel pipeline needs. numpy 1.x uses numpy.core,
# numpy 2.x (Google Colab) uses numpy._core.
ALLOWED_GLOBALS = {
    ("sklearn.pipeline", "Pipeline"),
    ("model.preprocess", "TermEncoder"),
    ("model.preprocess", "WeightedLinearRegression"),
    ("sklearn.linear_model._base", "LinearRegression"),
    ("joblib.numpy_pickle", "NumpyArrayWrapper"),
    ("numpy", "dtype"),
    ("numpy", "ndarray"),
    ("numpy.core.multiarray", "scalar"),
    ("numpy._core.multiarray", "scalar"),
    ("numpy.core.multiarray", "_reconstruct"),
    ("numpy._core.multiarray", "_reconstruct"),
    ("_codecs", "encode"),  # how pickle protocol 2 stores bytes (string -> bytes only)
}


class UnsafeModelFile(ValueError):
    """The file names something a FleetFuel model never contains."""


def _check_global(module, name):
    if (module, name) not in ALLOWED_GLOBALS:
        raise UnsafeModelFile(f"The model file refers to {module}.{name}, which a FleetFuel model never contains.")


class _SafePlainUnpickler(pickle.Unpickler):
    """For the object arrays (e.g. the feature names) joblib stores as a plain pickle."""

    def find_class(self, module, name):
        _check_global(module, name)
        if (module, name) == ("joblib.numpy_pickle", "NumpyArrayWrapper"):
            raise UnsafeModelFile("The model file has a nested array wrapper.")
        return pickle.Unpickler.find_class(self, module, name)


class _SafeArrayWrapper(NumpyArrayWrapper):
    def read_array(self, unpickler):
        if self.dtype.hasobject:
            # joblib would use the unrestricted pickle.load here
            array = _SafePlainUnpickler(unpickler.file_handle).load()
            if not isinstance(array, unpickler.np.ndarray):
                raise UnsafeModelFile("The model file has an invalid array.")
            return array
        return NumpyArrayWrapper.read_array(self, unpickler)


class _SafeUnpickler(NumpyUnpickler):
    def find_class(self, module, name):
        _check_global(module, name)
        if (module, name) == ("joblib.numpy_pickle", "NumpyArrayWrapper"):
            return _SafeArrayWrapper
        return NumpyUnpickler.find_class(self, module, name)


def safe_load_joblib(data):
    """Unpickle `data` (bytes) with the allowlist above."""
    with _read_fileobject(io.BytesIO(data), "", None) as fobj:
        if isinstance(fobj, str):  # joblib < 0.10 format: loaded another way
            raise UnsafeModelFile("The model file uses an old joblib format.")
        return _SafeUnpickler("", fobj, mmap_mode=None).load()
