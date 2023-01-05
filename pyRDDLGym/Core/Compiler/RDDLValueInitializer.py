import numpy as np
from typing import Dict, Union

from pyRDDLGym.Core.ErrorHandling.RDDLException import RDDLInvalidObjectError
from pyRDDLGym.Core.ErrorHandling.RDDLException import RDDLTypeError

from pyRDDLGym.Core.Compiler.RDDLModel import PlanningModel
from pyRDDLGym.Core.Debug.Logger import Logger


class RDDLValueInitializer:
    '''Compiles all initial values in pvariables scope and init-fluents scope
    in a RDDL domain + instance to scalars or numpy arrays.
    '''
    
    INT = np.int64
    REAL = np.float64
        
    NUMPY_TYPES = {
        'int': INT,
        'real': REAL,
        'bool': bool
    }
    
    DEFAULT_VALUES = {
        'int': 0,
        'real': 0.0,
        'bool': False
    }
        
    def __init__(self, rddl: PlanningModel, logger: Logger=None) -> None:
        self.rddl = rddl
        self.logger = logger
    
    def initialize(self) -> Dict[str, Union[np.ndarray, INT, REAL, bool]]:
        rddl = self.rddl
                
        # initial values consists of non-fluents, state and action fluents
        init_values = {}
        init_values.update(rddl.nonfluents)
        init_values.update(rddl.init_state)
        init_values.update(rddl.actions)

        # enum literals are converted to integers
        for (var, values) in init_values.items():
            prange = rddl.variable_ranges[var]
            if prange in rddl.enum_types:
                init_values[var] = self._enum_literals_to_ints(values, prange, var)
        
        # create a tensor for each pvar with the init_values
        # if the init_values are missing use the default value of range
        np_init_values = {}
        for (var, prange) in rddl.variable_ranges.items():
            
            # enum types are treated as int
            if prange in rddl.enum_types:
                prange = 'int'
            
            # get default value and dtype
            default = RDDLValueInitializer.DEFAULT_VALUES.get(prange, None)
            dtype = RDDLValueInitializer.NUMPY_TYPES.get(prange, None)
            if default is None or dtype is None:
                raise RDDLTypeError(
                    f'Type <{prange}> of variable <{var}> is not valid, '
                    f'must be an enum type in {self.rddl.enum_types} '
                    f'or one of {set(RDDLValueInitializer.DEFAULT_VALUES.keys())}.')
            
            # scalar value is just cast to the desired type
            # list values are converted to numpy arrays and reshaped such that 
            # number of axes matches number of pvariable arguments
            ptypes = rddl.param_types[var]
            if ptypes:
                shape = rddl.object_counts(ptypes)
                if var in init_values:
                    values = [default if v is None else v for v in init_values[var]]
                    values = np.asarray(values, dtype=dtype)
                    values = np.reshape(values, newshape=shape, order='C')
                else:
                    values = np.full(shape=shape, fill_value=default)
            else:
                values = dtype(init_values.get(var, default))   
            np_init_values[var] = values
        
        # log shapes of initial values
        if self.logger is not None:
            tensor_info = '\n\t'.join((
                f'{k}{rddl.param_types[k]}, '
                f'shape={v.shape if type(v) is np.ndarray else ()}, '
                f'dtype={v.dtype if type(v) is np.ndarray else type(v).__name__}'
            ) for (k, v) in np_init_values.items())
            message = (f'initializing pvariable tensors:' 
                       f'\n\t{tensor_info}\n')
            self.logger.log(message)
        
        return np_init_values
    
    def _enum_literals_to_ints(self, literals, prange, var):
        rddl = self.rddl
        is_scalar = isinstance(literals, str)
        if is_scalar:
            literals = [literals]
        indices = []
        for literal in literals:
            if literal is None:
                indices.append(0)
            elif rddl.objects_rev.get(literal, None) == prange:
                index = rddl.index_of_object[literal]
                indices.append(index)
            else:
                raise RDDLInvalidObjectError(
                    f'Literal <{literal}> assigned to variable <{var}> '
                    f'does not belong to enum <{prange}>, '
                    f'must be one of {set(rddl.objects[prange])}.')
        if is_scalar:
            indices = indices[0]
        return indices
    
