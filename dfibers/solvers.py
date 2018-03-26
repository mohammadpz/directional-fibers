import time
import itertools as it
import numpy as np
import scipy.optimize as so
import numerical_utilities as nu
import fixed_points as fx
import traversal as tv

def local_solver(
    sampler,
    f,
    qg,
    H,
    stop_time=None,
    max_repeats=None,
    max_updates=0,
    logfile=None
    ):
    """
    A fixed point solver using local optimization (Sussillo and Barak 2013)
    Locally optimizes an objective function with minima at fixed points.
    Finds multiple fixed points with repeated local optimization of seeds along random trajectories.
    
    User provides function handle sampler
        sampler() returns random v in state space, an (N,1) ndarray
    User provides function handle f, which accepts (N,1) ndarray v
        f(v) returns change in v after one update
    User provides function handles qg and H, which accept (N,) ndarray v
    qg and H conform to scipy.optimize.minimize first parameter and "hess" parameter
        qg(v) returns
            q: the objective at v (a scalar)
            g: the gradient of the objective (a (N,) ndarray)
        H(v) returns
            H: an approximate Hessian of q at v (a (N,N) ndarray)
    If provided, the solver terminates at the clock time stop_time.
    If provided, the solver terminates after max_repeats samples.
    The solver iterates each sample under the system dynamics at most max_updates times before optimizing.

    A dictionary with the following entries is returned:
    "Seeds": ndarray where the n^th column is the n^th seed
    "Updates": ndarray where the n^th element is the number of system updates for the n^th seed 
    "Optima": ndarray where the n^th column is the optimum from the n^th seed
    
    """
    seeds, updates, optima = [], [], []
    start = time.clock()
    for repeat in it.count():

        # Check termination criteria
        if stop_time is not None and time.clock() >= stop_time: break
        if max_repeats is not None and repeat >= max_repeats: break

        # get random initial seed anywhere in range
        v = sampler()
        seeds.append(v)

        # iterate trajectory a random number of steps
        num_updates = np.random.randint(max_updates+1)
        for u in range(num_updates):
            v = v + f(v)
        updates.append(num_updates)

        # run minimization
        result = so.minimize(qg, v.flatten(), method='trust-ncg', jac=True, hess=H)
        optimum = result.x.reshape(v.shape)
        optima.append(optimum)

    # Format output
    return {
        "Seeds": np.concatenate(seeds, axis=1),
        "Updates": np.array(updates),
        "Optima": np.concatenate(optima, axis=1),
    }

def fiber_solver(
    f,
    ef,
    Df,
    compute_step_amount,
    v=None,
    c=None,
    z=None,
    N=None,
    terminate=None,
    logfile=None,
    stop_time=None,
    max_traverse_steps=None,
    max_step_size=None,
    max_solve_iterations=None,
    local_abs_min=True,
    within_fiber=True,
    ):
    """
    Root location using directional fibers.
    If local_abs_min is True, includes local alpha minima as candidate roots.
    If within_fiber is True, candidates are refined within the fiber
    All other parameters are as described in directional_fibers.traverse_fiber().
    Returns solution, a dictionary with keys
        "Fiber trace": the result of traverse_fiber()
        "Fixed points": an array with one candidate root per column
        "Refinements": a list of local traverse_fiber results, one per fixed point
        "Fixed index": an array of fixed point candidate indices in the fiber
    """

    # Traverse fiber
    fiber_result = tv.traverse_fiber(
        f,
        Df,
        ef,
        compute_step_amount,
        v=v,
        c=c,
        z=z,
        N=N,
        terminate=terminate,
        logfile=logfile,
        stop_time=stop_time,
        max_traverse_steps=max_traverse_steps,
        max_step_size=max_step_size,
        max_solve_iterations=max_solve_iterations,
    )
    
    # Keep final direction vector if random default (in theory shouldn't matter)
    c = fiber_result.c

    # Extract candidate fixed points:
    # endpoints, alpha sign change, local |alpha| minimum
    # immediate neighbors for close pairs of fixed points and added redundancy
    X = np.concatenate(fiber_result.points, axis=1)
    a = X[-1,:]
    fixed_index = np.zeros(len(a), dtype=bool)
    # endpoints
    fixed_index[[0, -1]] = True
    # sign changes
    fixed_index[:-1] |= np.sign(a[:-1]) != np.sign(a[1:])
    # local minima of alpha magnitude
    if local_abs_min:
        fixed_index[1:-1] |= (np.fabs(a[1:-1]) <= np.fabs(a[2:])) & (np.fabs(a[1:-1]) <= np.fabs(a[:-2]))
    # extra redundancy with neighbors (don't combine |= with numpy views)
    fixed_index[:-1] = np.logical_or(fixed_index[:-1], fixed_index[1:])
    fixed_index[1:] = np.logical_or(fixed_index[1:], fixed_index[:-1])

    # Set up within-fiber Newton-Raphson step computation
    def compute_refine_step_amount(trace):
        refine_step_amount = -trace.x[-1,0]/trace.z[-1,0]
        fiber_step_amount, fiber_step_data = compute_step_amount(trace)
        step_amount = np.sign(refine_step_amount)*min(
            np.fabs(refine_step_amount), fiber_step_amount)
        step_data = (refine_step_amount, fiber_step_amount, fiber_step_data)
        return step_amount, step_data
    if terminate is None: terminate = lambda x: False
    refine_terminate = lambda trace: fx.is_fixed(trace.x[:-1,:], f, ef)[0] or terminate(trace)

    # Refine each candidate root
    X = X[:, fixed_index]
    refinement_results = []
    fixed_points = []
    for i in range(X.shape[1]):

        candidate = X[:-1,[i]].copy()

        if within_fiber:
            # Run within-fiber Newton-Raphson at each candidate
            refinement_result = tv.traverse_fiber(
                f,
                Df,
                ef,
                compute_refine_step_amount,
                v=candidate,
                c=c,
                terminate=refine_terminate,
                logfile=logfile,
                stop_time=stop_time,
                max_traverse_steps=2**5, # few steps needed for Newton-Raphson
                max_step_size=max_step_size,
                max_solve_iterations=max_solve_iterations,
            )
            refinement_results.append(refinement_result)
            candidate = refinement_result.points[-1][:-1,:].copy()
            
        fixed_points.append(candidate)

    
    # Return output
    solution = {
        "Fiber trace": fiber_result,
        "Fixed points": np.concatenate(fixed_points,axis=1),
        "Refinements": refinement_results,
        "Fixed index": np.flatnonzero(fixed_index),
    }
    return solution

