"""Krzywe bez bpy (PCHIP, splajn naturalny, Catmull-Rom, równe odcinki) – wspólne dla Blendera i zwykłego Pythona."""
import math

import numpy as np


# ---------------------------------------------------------------- krzywe

def pchip_slopes(xk, yk):
    xk = np.asarray(xk, float)
    yk = np.asarray(yk, float)
    n = len(xk)
    h = np.diff(xk)
    d = np.diff(yk) / h
    m = np.zeros(n)
    if n == 2:
        m[:] = d[0]
        return m
    for k in range(1, n - 1):
        if d[k - 1] * d[k] <= 0:
            m[k] = 0.0
        else:
            w1 = 2 * h[k] + h[k - 1]
            w2 = h[k] + 2 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])

    def end(h0, h1, d0, d1):
        v = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
        if np.sign(v) != np.sign(d0):
            v = 0.0
        elif np.sign(d0) != np.sign(d1) and abs(v) > abs(3 * d0):
            v = 3 * d0
        return v

    m[0] = end(h[0], h[1], d[0], d[1])
    m[-1] = end(h[-1], h[-2], d[-1], d[-2])
    return m


def pchip(xk, yk, x, m=None):
    """Monotoniczna interpolacja Hermite'a (bez przerzutów); x poza zakresem – przycięte."""
    xk = np.asarray(xk, float)
    yk = np.asarray(yk, float)
    if m is None:
        m = pchip_slopes(xk, yk)
    xa = np.clip(np.asarray(x, float), xk[0], xk[-1])
    i = np.clip(np.searchsorted(xk, xa) - 1, 0, len(xk) - 2)
    h = xk[i + 1] - xk[i]
    t = (xa - xk[i]) / h
    t2, t3 = t * t, t * t * t
    return ((2 * t3 - 3 * t2 + 1) * yk[i] + (t3 - 2 * t2 + t) * h * m[i] + (-2 * t3 + 3 * t2) * yk[i + 1]
            + (t3 - t2) * h * m[i + 1])


def spline_nat(xk, yk):
    """Współczynniki naturalnego splajnu sześciennego (gładkość C2) → funkcja f(x)."""
    xk = np.asarray(xk, float)
    yk = np.asarray(yk, float)
    n = len(xk)
    h = np.diff(xk)
    A = np.zeros((n, n))
    r = np.zeros(n)
    A[0, 0] = A[-1, -1] = 1
    for i in range(1, n - 1):
        A[i, i - 1] = h[i - 1]
        A[i, i] = 2 * (h[i - 1] + h[i])
        A[i, i + 1] = h[i]
        r[i] = 3 * ((yk[i + 1] - yk[i]) / h[i] - (yk[i] - yk[i - 1]) / h[i - 1])
    c = np.linalg.solve(A, r)
    b = (yk[1:] - yk[:-1]) / h - h * (2 * c[:-1] + c[1:]) / 3
    d = (c[1:] - c[:-1]) / (3 * h)

    def f(x):
        xa = np.clip(np.asarray(x, float), xk[0], xk[-1])
        i = np.clip(np.searchsorted(xk, xa) - 1, 0, n - 2)
        t = xa - xk[i]
        return yk[i] + b[i] * t + c[i] * t * t + d[i] * t ** 3
    return f


def catmull(pts, n_per=8, closed=False):
    """Krzywa Catmulla-Roma (centripetalna) przez punkty (lista krotek dowolnego wymiaru) → gęsta lista."""
    P_ = [np.asarray(p, float) for p in pts]
    if closed:
        P_ = [P_[-1]] + P_ + [P_[0], P_[1]]
    else:
        P_ = [2 * P_[0] - P_[1]] + P_ + [2 * P_[-1] - P_[-2]]
    out = []
    for i in range(1, len(P_) - 2):
        p0, p1, p2, p3 = P_[i - 1], P_[i], P_[i + 1], P_[i + 2]

        def tj(ti, a, b):
            return ti + max(np.linalg.norm(b - a), 1e-9) ** 0.5
        t0 = 0.0
        t1 = tj(t0, p0, p1)
        t2 = tj(t1, p1, p2)
        t3 = tj(t2, p2, p3)
        for k in range(n_per):
            t = t1 + (t2 - t1) * k / n_per
            a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
            b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
            out.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
    if not closed:
        out.append(P_[-2])
    return [tuple(p) for p in out]


def resample(pts, step=None, n=None):
    """Łamana → równe odcinki (krok w metrach albo liczba punktów)."""
    a = np.asarray(pts, float)
    seg = np.linalg.norm(np.diff(a, axis=0), axis=1)
    L = np.concatenate([[0], np.cumsum(seg)])
    if n is None:
        n = max(2, int(math.ceil(L[-1] / step)) + 1)
    t = np.linspace(0, L[-1], n)
    cols = [np.interp(t, L, a[:, k]) for k in range(a.shape[1])]
    return [tuple(float(c[i]) for c in cols) for i in range(n)]


def polyline_len(pts):
    a = np.asarray(pts, float)
    return float(np.linalg.norm(np.diff(a, axis=0), axis=1).sum())
