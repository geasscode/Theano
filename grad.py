import gof
import core

class Grad(object):
    """A dictionary-like class, into which derivative expressions may be added.

    This class maps keys to their ids to deal with the ndarray, which is not
    hashable.
    
    Attributes: None

    Methods:

    add()
    bprop()
    __call__()
    __getitem__()
    """
    def __init__(self, dct={}):
        self.map = {}
        self.outputs = []
        for key,val in dct.items():
            self.add_output(key,val)

    def __contains__(self, item):
        return id(item) in self.map

    def __getitem__(self, item):
        """Map item to its id and retrieve it."""
        return self.map[id(item)]

    def __setitem__(self, item, val):
        """Map item to its id and store internally."""
        self.map[id(item)] = val

    def add_output(self, r, dr):
        self.add(r, dr)
        self.outputs.append(r)
        
    def add(self, r, dr):
        """Add dr to the sum of gradients associated with r.
        
        This function should be fed as follows:

        if dr is UNDEFINED:
            r could be anything
        else dr might be core.UNCOMPUTED:
            r may be uncomputed or NumpyR
        else dr will be isinstance(NumpyR):
            r may be uncomputed or NumpyR

        """

        if dr is core.UNDEFINED:
            # nothing to do
            pass
        else:
            if r.data is core.UNCOMPUTED or dr.data is core.UNCOMPUTED:
                pass
            else: # try some hacky checks to catch obvious mistakes
                if not hasattr(r.data, 'shape'):
                    raise ValueError(('Grad::add r lacks shape: type=',
                        type(r.data)))
                if not hasattr(dr.data, 'shape'):
                    raise ValueError(('Grad::add dr lacks shape: type=',
                        type(dr.data)))
                if r.data.shape != dr.data.shape:
                    raise ValueError(('Grad::add r, dr shape mismatch',
                        v.data.shape, dv.datashape))

            # add dr to self[r]
            if r in self:
                self[r] = self[r] + dr
            else:
                self[r] = dr

    def bprop(self):
        """Build a backpropagation graph.

        The gradient associated with each value is stored in <self> which
        inherits from dictionary.  The idea is that when we call
        op.update_gradient(self), that the op's update_gradient function calls
        back into <self>.add(), and says what gradient term goes with each of
        its inputs.  Most of the time, the gradients of the op's outputs are
        necessary for the op to compute the gradient wrt its inputs, so
        op.update_gradient will usually call <self>.__getitem__, (via the
        [] notation). 
        
        It is essential that the gradient of an op's outputs be fully computed
        before op.update_gradient is called, or else key errors may be raised
        and incorrect gradients will be computed.

        bprop sets the omega evaluation mode to be 'build', so no computations
        or allocations are done by bprop.
        """
        core.build_mode()
        try:
            outputs = self.outputs
            inputs = gof.graph.inputs(outputs)
            for op in gof.graph.io_toposort(inputs, outputs).__reversed__():
                op.update_gradient(self)
        finally:
            core.pop_mode()

    def __call__(self, item):
        """Return a derivative term.

        If the current omega evaluation mode is 'build_eval' then the node is
        computed if necessary.
        """
        rval = self[item]
        if core.current_mode() == 'build_eval':
            rval.compute()
        return rval

def grad(cost, param=None, cost_grad = 1.0):
    """Return symbolic expression of gradient of <cost> wrt <param>.

    If <param> is None, then return a Grad instance, from which the gradients of
    multiple objects can be retrieved using the __getitem__ or __call__ methods
    (as in function currying in languages such as scheme and OCaML).

    If <param> is not None, then return the gradient expression for 
    d cost / d param.

    """
    if core.current_mode() == 'eval':
        raise NotImplementedError('Gradient-related functions are not available in eval mode')

    rval = Grad({cost:core.wrap(cost_grad)})
    rval.bprop()
    if param is None:
        return rval
    else:
        return rval(param)

#
# UNIT TEST
#
import unittest
import numpy
import compile

class _testCase (unittest.TestCase):
    def setUp(self):
        numpy.random.seed(1)
        core.build_eval_mode()

    def matinv(self,dim):
        w = core.wrap(numpy.random.rand(dim,dim))
        wi = core.wrap(numpy.random.rand(dim,dim))
        ident = core.wrap(numpy.identity(dim))

        for i in xrange(300):
            wwi = core.dot(w, wi)
            diff = wwi - ident
            ssdiff = core.sum((diff**2))
            if i == 0:
                str0 = str_ssdiff = str(ssdiff)

            #print ssdiff
            g = grad(ssdiff)
            gw = g(w)
            w.data += -0.4 * gw.data

        return str0, str(ssdiff)

    def matinv_compiled(self, dim):
        w = core.wrap(numpy.random.rand(dim,dim))
        wi = core.wrap(numpy.random.rand(dim,dim))
        ident = core.wrap(numpy.identity(dim))

        wwi = core.dot(w, wi)
        diff = wwi - ident
        ssdiff = core.sum((diff**2))
        str0 = str_ssdiff = str(ssdiff)

        #print ssdiff
        g = grad(ssdiff)
        gw = g(w)

        prog = compile.single(g(w),ssdiff)

        for i in xrange(300):
            prog()
            w.data += -0.4 * gw.data

        return str0, str(ssdiff)

    def test0(self):
        self.assertEqual(('2.67327580893', '0.000438649434819'), self.matinv(3))

    def test1(self):
        self.assertEqual(('2.67327580893', '0.000438649434819'),
                self.matinv_compiled(3))

    def tearDown(self):
        core.pop_mode()

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(_testCase)
    unittest.TextTestRunner(verbosity=3).run(suite)

