import numpy as np

def newmark_elastic_sdof(accel_ms2, dt, T, zeta, m=1.0):
    """
    Elastic SDOF time-history integration using Newmark Average Acceleration.
    gamma=0.5, beta=0.25 — unconditionally stable.
    Using the correct Incremental Formulation.

    Args:
        accel_ms2 (np.array): Effective ground acceleration (m/s^2).
                              For modal superposition, pass Gamma_n * accel_ground.
        dt        (float):    Time step (s).
        T         (float):    Natural period of the SDOF (s).
        zeta      (float):    Damping ratio (e.g. 0.05).
        m         (float):    Mass (default 1.0 for unit-mass modal SDOF).

    Returns:
        u     (np.array): Relative displacement history (m).
        v     (np.array): Relative velocity history (m/s).
        a_rel (np.array): Relative acceleration history (m/s^2).
    """
    n = len(accel_ms2)

    gamma = 0.5
    beta  = 0.25

    k = (2.0 * np.pi / T) ** 2 * m
    c = 2.0 * zeta * np.sqrt(k * m)

    u     = np.zeros(n)
    v     = np.zeros(n)
    a_rel = np.zeros(n)

    a_rel[0] = -accel_ms2[0]

    a1    = (1.0 / (beta * dt**2)) * m + (gamma / (beta * dt)) * c
    a2    = (1.0 / (beta * dt))    * m + (gamma / beta)        * c  
    a3    = (0.5 / beta)           * m + dt * (gamma / (2.0 * beta) - 1.0) * c 

    k_eff = k + a1

    for i in range(n - 1):
                                         
        dp_eff = (-m * accel_ms2[i+1] - (-m * accel_ms2[i])) + a2 * v[i] + a3 * a_rel[i]

        du = dp_eff / k_eff
        
        dv = (gamma / (beta * dt)) * du - (gamma / beta) * v[i]\
             - dt * (gamma / (2.0 * beta) - 1.0) * a_rel[i]
             
        da = (1.0 / (beta * dt**2)) * du - (1.0 / (beta * dt)) * v[i]\
             - (0.5 / beta) * a_rel[i] 

        u[i+1]     = u[i]     + du
        v[i+1]     = v[i]     + dv
        a_rel[i+1] = a_rel[i] + da

    return u, v, a_rel
