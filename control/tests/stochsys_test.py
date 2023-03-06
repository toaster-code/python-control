# stochsys_test.py - test stochastic system operations
# RMM, 16 Mar 2022

import numpy as np
import pytest
from control.tests.conftest import asmatarrayout

import control as ct
import control.optimal as opt
from control import lqe, dlqe, rss, drss, tf, ss, ControlArgument, slycot_check
from math import log, pi

# Utility function to check LQE answer
def check_LQE(L, P, poles, G, QN, RN):
    P_expected = asmatarrayout(np.sqrt(G @ QN @ G @ RN))
    L_expected = asmatarrayout(P_expected / RN)
    poles_expected = -np.squeeze(np.asarray(L_expected))
    np.testing.assert_almost_equal(P, P_expected)
    np.testing.assert_almost_equal(L, L_expected)
    np.testing.assert_almost_equal(poles, poles_expected)

# Utility function to check discrete LQE solutions
def check_DLQE(L, P, poles, G, QN, RN):
    P_expected = asmatarrayout(G.dot(QN).dot(G))
    L_expected = asmatarrayout(0)
    poles_expected = -np.squeeze(np.asarray(L_expected))
    np.testing.assert_almost_equal(P, P_expected)
    np.testing.assert_almost_equal(L, L_expected)
    np.testing.assert_almost_equal(poles, poles_expected)

@pytest.mark.parametrize("method", [None, 'slycot', 'scipy'])
def test_LQE(matarrayin, method):
    if method == 'slycot' and not slycot_check():
        return

    A, G, C, QN, RN = (matarrayin([[X]]) for X in [0., .1, 1., 10., 2.])
    L, P, poles = lqe(A, G, C, QN, RN, method=method)
    check_LQE(L, P, poles, G, QN, RN)

@pytest.mark.parametrize("cdlqe", [lqe, dlqe])
def test_lqe_call_format(cdlqe):
    # Create a random state space system for testing
    sys = rss(4, 3, 2)
    sys.dt = None           # treat as either continuous or discrete time

    # Covariance matrices
    Q = np.eye(sys.ninputs)
    R = np.eye(sys.noutputs)
    N = np.zeros((sys.ninputs, sys.noutputs))

    # Standard calling format
    Lref, Pref, Eref = cdlqe(sys.A, sys.B, sys.C, Q, R)

    # Call with system instead of matricees
    L, P, E = cdlqe(sys, Q, R)
    np.testing.assert_almost_equal(Lref, L)
    np.testing.assert_almost_equal(Pref, P)
    np.testing.assert_almost_equal(Eref, E)

    # Make sure we get an error if we specify N
    with pytest.raises(ct.ControlNotImplemented):
        L, P, E = cdlqe(sys, Q, R, N)

    # Inconsistent system dimensions
    with pytest.raises(ct.ControlDimension, match="Incompatible"):
        L, P, E = cdlqe(sys.A, sys.C, sys.B, Q, R)

    # Incorrect covariance matrix dimensions
    with pytest.raises(ct.ControlDimension, match="Incompatible"):
        L, P, E = cdlqe(sys.A, sys.B, sys.C, R, Q)

    # Too few input arguments
    with pytest.raises(ct.ControlArgument, match="not enough input"):
        L, P, E = cdlqe(sys.A, sys.C)

    # First argument is the wrong type (use SISO for non-slycot tests)
    sys_tf = tf(rss(3, 1, 1))
    sys_tf.dt = None        # treat as either continuous or discrete time
    with pytest.raises(ct.ControlArgument, match="LTI system must be"):
        L, P, E = cdlqe(sys_tf, Q, R)

@pytest.mark.parametrize("method", [None, 'slycot', 'scipy'])
def test_DLQE(matarrayin, method):
    if method == 'slycot' and not slycot_check():
        return

    A, G, C, QN, RN = (matarrayin([[X]]) for X in [0., .1, 1., 10., 2.])
    L, P, poles = dlqe(A, G, C, QN, RN, method=method)
    check_DLQE(L, P, poles, G, QN, RN)

def test_lqe_discrete():
    """Test overloading of lqe operator for discrete time systems"""
    csys = ct.rss(2, 1, 1)
    dsys = ct.drss(2, 1, 1)
    Q = np.eye(1)
    R = np.eye(1)

    # Calling with a system versus explicit A, B should be the sam
    K_csys, S_csys, E_csys = ct.lqe(csys, Q, R)
    K_expl, S_expl, E_expl = ct.lqe(csys.A, csys.B, csys.C, Q, R)
    np.testing.assert_almost_equal(K_csys, K_expl)
    np.testing.assert_almost_equal(S_csys, S_expl)
    np.testing.assert_almost_equal(E_csys, E_expl)

    # Calling lqe() with a discrete time system should call dlqe()
    K_lqe, S_lqe, E_lqe = ct.lqe(dsys, Q, R)
    K_dlqe, S_dlqe, E_dlqe = ct.dlqe(dsys, Q, R)
    np.testing.assert_almost_equal(K_lqe, K_dlqe)
    np.testing.assert_almost_equal(S_lqe, S_dlqe)
    np.testing.assert_almost_equal(E_lqe, E_dlqe)

    # Calling lqe() with no timebase should call lqe()
    asys = ct.ss(csys.A, csys.B, csys.C, csys.D, dt=None)
    K_asys, S_asys, E_asys = ct.lqe(asys, Q, R)
    K_expl, S_expl, E_expl = ct.lqe(csys.A, csys.B, csys.C, Q, R)
    np.testing.assert_almost_equal(K_asys, K_expl)
    np.testing.assert_almost_equal(S_asys, S_expl)
    np.testing.assert_almost_equal(E_asys, E_expl)

    # Calling dlqe() with a continuous time system should raise an error
    with pytest.raises(ControlArgument, match="called with a continuous"):
        K, S, E = ct.dlqe(csys, Q, R)

def test_estimator_iosys():
    sys = ct.drss(4, 2, 2, strictly_proper=True)

    Q, R = np.eye(sys.nstates), np.eye(sys.ninputs)
    K, _, _ = ct.dlqr(sys, Q, R)

    P0 = np.eye(sys.nstates)
    QN = np.eye(sys.ninputs)
    RN = np.eye(sys.noutputs)
    estim = ct.create_estimator_iosystem(sys, QN, RN, P0)

    ctrl, clsys = ct.create_statefbk_iosystem(sys, K, estimator=estim)

    # Extract the elements of the estimator
    est = estim.linearize(0, 0)
    Be1 = est.B[:sys.nstates, :sys.noutputs]
    Be2 = est.B[:sys.nstates, sys.noutputs:]
    A_clchk = np.block([
        [sys.A, -sys.B @ K],
        [Be1 @ sys.C, est.A[:sys.nstates, :sys.nstates] - Be2 @ K]
    ])
    B_clchk = np.block([
        [sys.B @ K, sys.B],
        [Be2 @ K, Be2]
    ])
    C_clchk = np.block([
        [sys.C, np.zeros((sys.noutputs, sys.nstates))],
        [np.zeros_like(K), -K]
    ])
    D_clchk = np.block([
        [np.zeros((sys.noutputs, sys.nstates + sys.ninputs))],
        [K, np.eye(sys.ninputs)]
    ])

    # Check to make sure everything matches
    cls = clsys.linearize(0, 0)
    nstates = sys.nstates
    np.testing.assert_almost_equal(cls.A[:2*nstates, :2*nstates], A_clchk)
    np.testing.assert_almost_equal(cls.B[:2*nstates, :], B_clchk)
    np.testing.assert_almost_equal(cls.C[:, :2*nstates], C_clchk)
    np.testing.assert_almost_equal(cls.D, D_clchk)


@pytest.mark.parametrize("sys_args", [
    ([[-1]], [[1]], [[1]], 0),                          # scalar system
    ([[-1, 0.1], [0, -2]], [[0], [1]], [[1, 0]], 0),    # SISO, 2 state
    ([[-1, 0.1], [0, -2]], [[1, 0], [0, 1]], [[1, 0]], 0),    # 2i, 1o, 2s
    ([[-1, 0.1, 0.1], [0, -2, 0], [0.1, 0, -3]],        # 2i, 2o, 3s
     [[1, 0], [0, 0.1], [0, 1]],
     [[1, 0, 0.1], [0, 1, 0.1]], 0),
])
def test_estimator_iosys_ctime(sys_args):
    # Define the system we want to test
    sys = ct.ss(*sys_args)
    T = 10 * log(1e-2) / np.max(sys.poles().real)
    assert T > 0

    # Create nonlinear version of the system to match integration methods
    nl_sys = ct.NonlinearIOSystem(
        lambda t, x, u, params : sys.A @ x + sys.B @ u,
        lambda t, x, u, params : sys.C @ x + sys.D @ u,
        inputs=sys.ninputs, outputs=sys.noutputs, states=sys.nstates)

    # Define an initial condition, inputs (small, to avoid integration errors)
    timepts = np.linspace(0, T, 500)
    U = 2e-2 * np.array([np.sin(timepts + i*pi/3) for i in range(sys.ninputs)])
    X0 = np.ones(sys.nstates)

    # Set up the parameters for the filter
    P0 = np.eye(sys.nstates)
    QN = np.eye(sys.ninputs)
    RN = np.eye(sys.noutputs)

    # Construct the estimator
    estim = ct.create_estimator_iosystem(sys, QN, RN)

    # Compute the system response and the optimal covariance
    sys_resp = ct.input_output_response(nl_sys, timepts, U, X0)
    _, Pf, _ = ct.lqe(sys, QN, RN)
    Pf = np.array(Pf)           # convert from matrix, if needed

    # Make sure that we converge to the optimal estimate
    estim_resp = ct.input_output_response(
        estim, timepts, [sys_resp.outputs, U], [0*X0, P0])
    np.testing.assert_allclose(
        estim_resp.states[0:sys.nstates, -1], sys_resp.states[:, -1],
        atol=1e-6, rtol=1e-3)
    np.testing.assert_allclose(
        estim_resp.states[sys.nstates:, -1], Pf.reshape(-1),
        atol=1e-6, rtol=1e-3)

    # Make sure that optimal estimate is an eq pt
    ss_resp = ct.input_output_response(
        estim, timepts, [sys_resp.outputs, U], [X0, Pf])
    np.testing.assert_allclose(
        ss_resp.states[sys.nstates:],
        np.outer(Pf.reshape(-1), np.ones_like(timepts)),
        atol=1e-4, rtol=1e-2)
    np.testing.assert_allclose(
        ss_resp.states[0:sys.nstates], sys_resp.states,
        atol=1e-4, rtol=1e-2)


def test_estimator_errors():
    sys = ct.drss(4, 2, 2, strictly_proper=True)
    P0 = np.eye(sys.nstates)
    QN = np.eye(sys.ninputs)
    RN = np.eye(sys.noutputs)

    with pytest.raises(ct.ControlArgument, match=".* system must be a linear"):
        sys_tf = ct.tf([1], [1, 1], dt=True)
        estim = ct.create_estimator_iosystem(sys_tf, QN, RN)

    with pytest.raises(ValueError, match="output must be full state"):
        C = np.eye(2, 4)
        estim = ct.create_estimator_iosystem(sys, QN, RN, C=C)

    with pytest.raises(ValueError, match="output is the wrong size"):
        sys_fs = ct.drss(4, 4, 2, strictly_proper=True)
        sys_fs.C = np.eye(4)
        C = np.eye(1, 4)
        estim = ct.create_estimator_iosystem(sys_fs, QN, RN, C=C)


def test_white_noise():
    # Scalar white noise signal
    T = np.linspace(0, 1000, 1000)
    R = 0.5
    V = ct.white_noise(T, R)
    assert abs(np.mean(V)) < 0.1                # can occassionally fail
    assert abs(np.cov(V) - 0.5) < 0.1           # can occassionally fail

    # Vector white noise signal
    R = [[0.5, 0], [0, 0.1]]
    V = ct.white_noise(T, R)
    assert abs(np.mean(V)) < 0.1                # can occassionally fail
    assert np.all(abs(np.cov(V) - R) < 0.1)     # can occassionally fail

    # Make sure time scaling works properly
    T = T / 10
    V = ct.white_noise(T, R)
    assert abs(np.mean(V)) < np.sqrt(10)        # can occassionally fail
    assert np.all(abs(np.cov(V) - R) < 10)      # can occassionally fail

    # Make sure discrete time works properly
    V = ct.white_noise(T, R, dt=T[1] - T[0])
    assert abs(np.mean(V)) < 0.1                # can occassionally fail
    assert np.all(abs(np.cov(V) - R) < 0.1)     # can occassionally fail

    # Test error conditions
    with pytest.raises(ValueError, match="T must be 1D"):
        V = ct.white_noise(R, R)

    with pytest.raises(ValueError, match="Q must be square"):
        R = np.outer(np.eye(2, 3), np.ones_like(T))
        V = ct.white_noise(T, R)

    with pytest.raises(ValueError, match="Time values must be equally"):
        T = np.logspace(0, 2, 100)
        R = [[0.5, 0], [0, 0.1]]
        V = ct.white_noise(T, R)


def test_correlation():
    # Create an uncorrelated random sigmal
    T = np.linspace(0, 1000, 1000)
    R = 0.5
    V = ct.white_noise(T, R)

    # Compute the correlation
    tau, Rtau = ct.correlation(T, V)

    # Make sure the correlation makes sense
    zero_index = np.where(tau == 0)
    np.testing.assert_almost_equal(Rtau[zero_index], np.cov(V), decimal=2)
    for i, t in enumerate(tau):
        if i == zero_index:
            continue
    assert abs(Rtau[i]) < 0.01

    # Try passing a second argument
    tau, Rneg = ct.correlation(T, V, -V)
    np.testing.assert_equal(Rtau, -Rneg)

    # Test error conditions
    with pytest.raises(ValueError, match="Time vector T must be 1D"):
        tau, Rtau = ct.correlation(V, V)

    with pytest.raises(ValueError, match="X and Y must be 2D"):
        tau, Rtau = ct.correlation(T, np.zeros((3, T.size, 2)))

    with pytest.raises(ValueError, match="X and Y must have same length as T"):
        tau, Rtau = ct.correlation(T, V[:, 0:-1])

    with pytest.raises(ValueError, match="Time values must be equally"):
        T = np.logspace(0, 2, T.size)
        tau, Rtau = ct.correlation(T, V)

@pytest.mark.parametrize('dt', [0, 1])
def test_oep(dt):
    # Define the system to test, with additional input
    csys = ct.ss(
        [[-0.5, 1, 0, 0], [0, -1, 1, 0], [0, 0, -2, 1], [0, 0, 0, -3]], # A
        [[0, 0.1], [0, 0.1], [0, 0.1], [1, 0.1]],                       # B
        [[1, 0, 0, 0], [0, 0, 1, 0]],                                   # C
        0, dt=0)
    dsys = ct.c2d(csys, dt)
    sys = csys if dt == 0 else dsys

    # Create disturbances and noise (fixed, to avoid random errors)
    Rv = 0.1 * np.eye(1)                # scalar disturbance
    Rw = 0.01 * np.eye(sys.noutputs)
    timepts = np.arange(0, 10.1, 1)
    V = np.array(
        [0 if t % 2 == 1 else 1 if t % 4 == 0 else -1 for t in timepts]
    ).reshape(1, -1) * 0.1
    W = np.vstack([np.sin(2*timepts), np.cos(3*timepts)]) * 1e-3

    # Generate system data
    U = np.sin(timepts)

    # No disturbances
    res0 = ct.input_output_response(sys, timepts, [U, V*0])
    Y0 = res0.outputs

    # With disturbances and noise
    res1 = ct.input_output_response(sys, timepts, [U, V])
    Y1 = res1.outputs + W

    #
    # Internal testing to make sure all our functions are OK
    #

    # Set up optimal estimation function using Gaussian likelihoods for cost
    traj_cost = opt.gaussian_likelihood_cost(sys, Rv, Rw)
    init_cost = lambda xhat, x: (xhat - x) @ (xhat - x)
    oep = opt.OptimalEstimationProblem(
        sys, timepts, traj_cost, terminal_cost=init_cost)

    # _cost_function
    oep.compute_estimate(res0.outputs, U, X0=0)
    assert oep._cost_function(np.hstack(
        [res0.states.reshape(-1), V.reshape(-1) * 0])) == 0
    assert oep._cost_function(np.hstack(
        [res0.states.reshape(-1), V.reshape(-1)])) != 0
    if sys.isdtime():
        # Collocation contstraint should be satisified for discrete time
        np.testing.assert_allclose(oep._collocation_constraint(
            np.hstack([res0.states.reshape(-1), V.reshape(-1) * 0])), 0)

    # _compute_states_inputs: states and inputs with no noise
    oep.compute_estimate(Y0, U)
    xhat, u, v, w = oep._compute_states_inputs(
        np.hstack([res0.states.reshape(-1), V.reshape(-1) * 0]))
    np.testing.assert_allclose(xhat, res0.states)
    np.testing.assert_allclose(u, U.reshape(1, -1))
    np.testing.assert_allclose(v, 0)
    np.testing.assert_allclose(w, 0)

    # _compute_states_inputs: states and inputs with no noise
    oep.compute_estimate(Y1, U)
    xhat, u, v, w = oep._compute_states_inputs(
        np.hstack([res1.states.reshape(-1), V.reshape(-1)]))
    np.testing.assert_allclose(xhat, res1.states)
    np.testing.assert_allclose(u, U.reshape(1, -1))
    np.testing.assert_allclose(v, V)
    np.testing.assert_allclose(w, W)

    #
    # oep.compute_estimate testing
    #

    # Noise free and disturbance free
    nonoise_cost = opt.gaussian_likelihood_cost(sys, Rv, Rw/1e6)
    oep0 = opt.OptimalEstimationProblem(
        sys, timepts, nonoise_cost, terminal_cost=init_cost)
    est0 = oep0.compute_estimate(Y0, U)
    if sys.isdtime():
         # Full state estimate should be near perfect
        np.testing.assert_allclose(
            est0.states[:, -1], res0.states[:, -1], atol=1e-3, rtol=1e-3)
        np.testing.assert_allclose(est0.inputs, 0, atol=1e-2, rtol=1e-3)
        np.testing.assert_allclose(est0.outputs, 0, atol=1e-2, rtol=1e-3)
    else:
        # Estimate at end of trajectory should be very close
        assert est0.success
        np.testing.assert_allclose(
            est0.states[:, -1], res0.states[:, -1], atol=1e-2, rtol=1e-2)

    # Noise free, but with disturbances and good initial guess
    oep1 = opt.OptimalEstimationProblem(
        sys, timepts, nonoise_cost, terminal_cost=init_cost)
    est1 = oep1.compute_estimate(
        res1.outputs, U, initial_guess=(res1.states, V), X0=0)
    np.testing.assert_allclose(
          est1.states[:, -1], res1.states[:, -1], atol=1e-2, rtol=1e-2)
    if sys.isdtime():
        # For discrete time, estimated disturbance and noise should be close
        np.testing.assert_allclose(
            est1.inputs[:-1], V[:-1], atol=1e-2, rtol=1e-2)
        np.testing.assert_allclose(est1.outputs, 0, atol=1e-2, rtol=1e-2)

    # Noise and disturbances (the standard case)
    est2 = oep.compute_estimate(Y1, U)         # back to original OEP
    assert est2.success
    np.testing.assert_allclose(
        est2.states[:, -1], res1.states[:, -1], atol=1e-1, rtol=1e-2)

    #
    # Disturbance constraints
    #

    V3 = np.clip(V, 0.5, 1)
    traj_constraint = opt.disturbance_range_constraint(sys, 0.5, 1)
    oep3 = opt.OptimalEstimationProblem(
        sys, timepts, traj_cost, terminal_cost=init_cost,
        trajectory_constraints=traj_constraint)

    res3 = ct.input_output_response(sys, timepts, [U, V3])
    Y3 = res3.outputs + W

    # Make sure the constraint screws up the estimation problem
    with pytest.raises(AssertionError):
        est3 = oep.compute_estimate(Y3, U)
        np.testing.assert_allclose(
            est3.states[:, -1], res3.states[:, -1], atol=1e-1, rtol=1e-2)

    # Make sure estimation is correct with constraint in place
    est3 = oep3.compute_estimate(Y3, U)
    assert est3.success
    np.testing.assert_allclose(
        est3.states[:, -1], res3.states[:, -1], atol=1e-1, rtol=1e-2)


def test_mhe():
    # Define the system to test, with additional input
    csys = ct.ss(
        [[-0.5, 1, 0, 0], [0, -1, 1, 0], [0, 0, -2, 1], [0, 0, 0, -3]], # A
        [[0, 0.1], [0, 0.1], [0, 0.1], [1, 0.1]],                       # B
        [[1, 0, 0, 0], [0, 0, 1, 0]],                                   # C
        0, dt=0)
    dt = 0.1
    sys = ct.c2d(csys, dt)

    # Create disturbances and noise (fixed, to avoid random errors)
    Rv = 0.1 * np.eye(1)                # scalar disturbance
    Rw = 1e-6 * np.eye(sys.noutputs)
    P0 = 0.1 * np.eye(sys.nstates)

    timepts = np.arange(0, 10*dt, dt)
    mhe_timepts = np.arange(0, 5*dt, dt)
    V = np.array(
        [0 if i % 2 == 1 else 1 if i % 4 == 0 else -1
         for i, t in enumerate(timepts)]).reshape(1, -1) * 0.1
    W = np.sin(timepts / dt) * 1e-3

    # Create a moving horizon estimator
    traj_cost = opt.gaussian_likelihood_cost(sys, Rv, Rw)
    init_cost = lambda xhat, x: (xhat - x) @ P0 @ (xhat - x)
    oep = opt.OptimalEstimationProblem(
        sys, mhe_timepts, traj_cost, terminal_cost=init_cost)
    mhe = oep.create_mhe_iosystem(1)

    # Generate system data
    U = 10 * np.sin(timepts / (4*dt))
    inputs = np.vstack([U, V])
    resp = ct.input_output_response(sys, timepts, inputs)

    # Run the estimator
    estp = ct.input_output_response(
        mhe, timepts, [resp.outputs, resp.inputs[0:1]])

    # Make sure the estimated state is close to the actual state
    np.testing.assert_allclose(estp.outputs, resp.states, atol=1e-2, rtol=1e-4)
