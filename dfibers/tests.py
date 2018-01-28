import time
import unittest as ut
import numpy as np
import numerical_utilities as nu
import directional_fibers as df
import fixed_points as fx
import solvers as sv
import examples.rnn as rnn
import matplotlib.pyplot as plt

np.set_printoptions(linewidth=200)

class FixedPointsTestCase(ut.TestCase):
    def setUp(self):
        self.N = 10
        self.P = 100
        self.K = 3
        self.noise = 5
        self.E = lambda V, u: (np.fabs(V - u) < self.noise*nu.eps(V)).all(axis=0)
    def get_test_points(self):
        """
        Construct a set of P*K test points with at most K "unique" members.
        returns a numpy.array V, where V[:,p] is the p^{th} point.
        """
        # make P copies of K distinct, random points
        V = np.tile(np.random.rand(self.N,self.K),(1,self.P))
        # shuffle randomly
        V = V[:,np.random.permutation(self.K*self.P)]
        # perterb by a small multiple of machine precision
        V = V + np.floor(self.noise*np.random.rand(self.N,self.K*self.P))*nu.eps(V)
        return V
    def test_get_connected_components(self):
        """
        Sanity check for get_connected_components
        """
        V = self.get_test_points()
        components = fx.get_connected_components(V, self.E)
        self.assertTrue(len(np.unique(components)) <= self.K)
    def test_get_unique_points(self):
        """
        Sanity check for get_unique_points
        """
        V = self.get_test_points()
        U = fx.get_unique_points(V, self.E)
        self.assertTrue(U.shape[1] <= self.K)
        for p in range(V.shape[1]):
            noise = np.fabs(U - V[:,[p]]).max(axis=0)
            self.assertTrue(noise.min() < (self.noise*nu.eps(V[:,p])).max())

class RNNFixedPointsTestCase(ut.TestCase):
    def setUp(self):
        self.N = 10
        self.P = 5
        self.W, self.V = rnn.make_known_fixed_points(self.N)
        self.f = rnn.f_factory(self.W)
        self.ef = rnn.ef_factory(self.W)
        self.Df = rnn.Df_factory(self.W)
        self.noise = 5
        # self.duplicates = lambda V, u: (np.fabs(V - u) < 2*self.noise*nu.eps(V)).all(axis=0)
        self.duplicates = rnn.duplicates_factory(self.W)
    def get_test_points(self):
        """
        Construct a set of P*K test points based on K known fixed points
        returns a numpy.array V, where V[:,p] is the p^{th} point.
        """
        # make P copies of K known points
        V = np.tile(self.V, (1,self.P))
        # shuffle randomly
        V = V[:,np.random.permutation(V.shape[1])]
        # perterb by a small multiple of machine precision
        V = V + np.floor(self.noise*np.random.rand(*V.shape))*nu.eps(V)
        return V
    def test_sanitize_points(self):
        """
        Sanity check for refine_points
        """
        V = self.get_test_points()
        U = fx.sanitize_points(V, self.f, self.ef, self.Df, self.duplicates)
        print('')
        print(V.shape)
        print(U.shape)
        print(self.V.shape)
        self.assertTrue(U.shape[1] == self.V.shape[1])
        for p in range(self.V.shape[1]):
            # noise = np.fabs(U - self.V[:,[p]]).max(axis=0)
            # self.assertTrue(noise.min() < (self.noise*nu.eps(self.V[:,p])).max())
            self.assertTrue(self.duplicates(U, self.V[:,[p]]).any())

class RNNLocalSolverTestCase(ut.TestCase):
    def setUp(self):
        self.N = 3
        self.P = 5
        self.W, self.V = rnn.make_known_fixed_points(self.N)
        self.f = rnn.f_factory(self.W)
        self.ef = rnn.ef_factory(self.W)
        self.Df = rnn.Df_factory(self.W)
        self.sampler = rnn.sampler_factory(self.W)
        self.qg = rnn.qg_factory(self.W)
        self.H = rnn.H_factory(self.W)
        self.duplicates = rnn.duplicates_factory(self.W)
    def test_local_solver(self):
        result = sv.local_solver(
            self.sampler,
            self.f,
            self.qg,
            self.H,
            max_repeats=500,
        )
        V = result["Optima"]
        U = fx.sanitize_points(V, self.f, self.ef, self.Df, self.duplicates)
        print("This test should succeed with high probability")
        self.assertTrue(U.shape[1] >= self.V.shape[1])
        for p in range(self.V.shape[1]):
            self.assertTrue(self.duplicates(U, self.V[:,[p]]).any())

class RNNDirectionalFiberTestCase(ut.TestCase):
    def setUp(self):
        self.N = 2
        self.W = 1.25*np.eye(self.N,self.N) + 0.1*np.random.randn(self.N, self.N)
        self.f = rnn.f_factory(self.W)
        self.Df = rnn.Df_factory(self.W)
        self.compute_step_amount = rnn.compute_step_amount_factory(self.W)
        self.x = 0.01*np.random.randn(self.N+1,1)
        self.c = np.random.randn(self.N,1)
        self.c = self.c/np.linalg.norm(self.c)
        self.max_solve_iterations = 2**5
        self.solve_tolerance = 10**-18
        self.max_step_size = 1

    @ut.skip("")
    def test_initial(self):
        x, residuals = df.refine_initial(
            self.f, self.Df, self.x, self.c, self.max_solve_iterations, self.solve_tolerance)
        # print("Test initial:")
        print("")
        print("x, residuals")
        print(x.T)
        print(residuals)
        self.assertTrue(
            (residuals[-1] < self.solve_tolerance) or
            (len(residuals) <= self.max_solve_iterations))

    @ut.skip("")
    def test_update_tangent(self):
        x, _ = df.refine_initial(
            self.f, self.Df, self.x, self.c, self.max_solve_iterations, self.solve_tolerance)        
        DF = np.concatenate((self.Df(x[:self.N,:]), -self.c), axis=1)
        _,_,z = np.linalg.svd(DF)
        z = z[[self.N],:].T
        
        x = x + 0.001*z
        DF = np.concatenate((self.Df(x[:self.N,:]), -self.c), axis=1)
        z_new = df.compute_tangent(DF, z)
        
        # print("Test update tangent:")
        print("")
        print("z, z_new")
        print(z.T)
        print(z_new.T)
        self.assertTrue(z.T.dot(z_new) > 0)

    @ut.skip("")
    def test_compute_step_amount_size(self):
        x, _ = df.refine_initial(
            self.f, self.Df, self.x, self.c, self.max_solve_iterations, self.solve_tolerance)        
        DF = np.concatenate((self.Df(x[:self.N,:]), -self.c), axis=1)
        _,_,z = np.linalg.svd(DF)
        z = z[[self.N],:].T

        step_size, sv_min = self.compute_step_amount(x, DF, z)
        print("")
        print("step_size, sv_min")
        print(step_size, sv_min) # sometimes = 1/(2mu) if all svs of DF > 1 (z gets the = 1)

    @ut.skip("")
    def test_take_step(self):
        x, _ = df.refine_initial(
            self.f, self.Df, self.x, self.c, self.max_solve_iterations, self.solve_tolerance)        
        DF = np.concatenate((self.Df(x[:self.N,:]), -self.c), axis=1)
        _,_,z = np.linalg.svd(DF)
        z = z[[self.N],:].T
        
        step_size = self.compute_step_amount(x, DF, z)
        if self.max_step_size is not None: step_size = min(step_size, self.max_step_size)

        x_new, residuals = df.take_step(
            self.f, self.Df, self.c, z, x, step_size, self.max_solve_iterations, self.solve_tolerance)

        print("")
        print("x, x_new, residuals, num iters")
        print(x.T)
        print(x_new.T)
        print(residuals)
        print(len(residuals))
        self.assertTrue(z.T.dot(x_new-x) > 0)
        self.assertTrue(
            (len(residuals) <= self.max_solve_iterations) or
            (residuals[-1] < self.solve_tolerance))
    
    @ut.skip("")
    def test_early_term(self):
        print("")
        for max_traverse_steps in range(5):
            result = df.traverse_fiber(
                self.f,
                self.Df,
                self.compute_step_amount,
                v=self.x[:self.N,:],
                c=self.c,
                max_traverse_steps=max_traverse_steps,
                max_solve_iterations=self.max_solve_iterations,
                solve_tolerance=self.solve_tolerance,
                )
            print("max, len(X):")
            print(max_traverse_steps, result["X"].shape[1])
            self.assertTrue(result["X"].shape[1] <= max_traverse_steps+1)
        run_time = 2
        start_time = time.clock()
        result = df.traverse_fiber(
            self.f,
            self.Df,
            self.compute_step_amount,
            v=self.x[:self.N,:],
            c=self.c,
            stop_time=start_time + run_time,
            max_solve_iterations=self.max_solve_iterations,
            solve_tolerance=self.solve_tolerance,
            )
        end_time = time.clock()
        print("start, run, end")
        print(start_time, run_time, end_time)
        self.assertTrue(end_time > start_time + run_time and end_time < start_time + run_time + 1)

    @ut.skip("")
    def test_terminate(self):
        result = df.traverse_fiber(
            self.f,
            self.Df,
            self.compute_step_amount,
            v=self.x[:self.N,:],
            c=self.c,
            terminate=lambda x:True,
            max_traverse_steps=2,
            max_solve_iterations=self.max_solve_iterations,
            solve_tolerance=self.solve_tolerance,
            )
        self.assertTrue(result["status"] == "Terminated")
        result = df.traverse_fiber(
            self.f,
            self.Df,
            self.compute_step_amount,
            v=self.x[:self.N,:],
            c=self.c,
            terminate=rnn.terminate_factory(self.W, self.c),
            max_traverse_steps=10000,
            max_solve_iterations=self.max_solve_iterations,
            solve_tolerance=self.solve_tolerance,
            )
        self.assertTrue(result["status"] == "Terminated")

    @ut.skip("")
    def test_ef(self):
        ef = rnn.ef_factory(self.W)
        print()
        print("ef(0):")
        print(ef(np.zeros((self.N,1))).max())
        self.assertTrue(ef(np.zeros((self.N,1))).max() < 1**-100)
        print("ef(1):")
        print(ef(np.ones((self.N,1))).max())
        self.assertTrue(ef(np.zeros((self.N,1))).max() < 1**-10)

    @ut.skip("")
    def test_traverse_fiber(self):
        result = df.traverse_fiber(
            self.f,
            self.Df,
            self.compute_step_amount,
            v=self.x[:self.N,:],
            c=self.c,
            terminate=rnn.terminate_factory(self.W, self.c),
            max_traverse_steps=1000,
            max_solve_iterations=self.max_solve_iterations,
            solve_tolerance=self.solve_tolerance,
            )
        X = result["X"]
        V = X[:-1,:]
        C = self.f(V)
        self.assertTrue((np.fabs(X[[-1],:]*self.c - C) < 0.001).all())

def main():
    # test_suite = ut.TestLoader().loadTestsFromTestCase(RNNDirectionalFiberTestCase)
    # ut.TextTestRunner(verbosity=2).run(test_suite)
    # test_suite = ut.TestLoader().loadTestsFromTestCase(FixedPointsTestCase)
    # ut.TextTestRunner(verbosity=2).run(test_suite)
    # test_suite = ut.TestLoader().loadTestsFromTestCase(RNNFixedPointsTestCase)
    # ut.TextTestRunner(verbosity=2).run(test_suite)
    test_suite = ut.TestLoader().loadTestsFromTestCase(RNNLocalSolverTestCase)
    ut.TextTestRunner(verbosity=2).run(test_suite)
    
if __name__ == "__main__": main()