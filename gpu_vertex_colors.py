#!/usr/bin/env python3
"""
GPU-accelerated vertex coloring for Mandelbulb meshes using CuPy RawKernel.
This moves the CPU-bound per-vertex orbit computation to the GPU.
"""

import cupy as cp
import numpy as np

# CUDA kernel for orbit computation and coloring
ORBIT_COLOR_KERNEL = r'''
extern "C" __global__
void orbit_color(
    const float* __restrict__ vx,
    const float* __restrict__ vy,
    const float* __restrict__ vz,
    unsigned char* __restrict__ rgb,
    int n,
    float power, float bailout, int max_iter,
    int color_mode, float orbitR,
    int pi_mode, float pi_base, float pi_alpha, float pi_mu,
    int norm_mode, float norm_k, float norm_r0, float norm_sigma
){
    int i = blockDim.x * blockIdx.x + threadIdx.x;
    if (i >= n) return;

    float3 p = make_float3(vx[i], vy[i], vz[i]);
    float3 z = p;
    float  dr = 1.0f;
    float  r_euclid  = 0.0f;
    float  trapPlane = 1e9f;
    float  trapShell = 1e9f;
    float3 lastZ = z;
    int iters = 0;
    float pi_a = pi_base;

    for (int k=0; k<256; ++k){
        if (k >= max_iter) { iters = k; break; }
        
        r_euclid = sqrtf(z.x*z.x + z.y*z.y + z.z*z.z);
        trapPlane = fminf(trapPlane, fabsf(z.y));
        trapShell = fminf(trapShell, fabsf(r_euclid - orbitR));

        if (r_euclid > bailout) { iters = k; break; }

        // Adaptive norm
        float r, dr_a_dr;
        if (norm_mode != 0) {
            // tanh warp: r_a = r * (1 + k * tanh((r - r0)/sigma))
            float t = tanhf((r_euclid - norm_r0) / fmaxf(1e-8f, norm_sigma));
            r = r_euclid * (1.0f + norm_k * t);
            float dt_dr = (1.0f - t*t) / fmaxf(1e-8f, norm_sigma);
            dr_a_dr = (1.0f + norm_k * t) + r_euclid * norm_k * dt_dr;
            dr_a_dr = fmaxf(dr_a_dr, 1e-6f);
        } else {
            r = r_euclid;
            dr_a_dr = 1.0f;
        }

        // Spherical coords
        float theta = (r_euclid > 0.f) ? acosf(fmaxf(fminf(z.z / r_euclid, 1.f), -1.f)) : 0.f;
        float phi   = atan2f(z.y, z.x);

        // Adaptive pi
        if (pi_mode != 0) {
            pi_a = pi_a - pi_alpha * r - pi_mu * (pi_a - pi_base);
        }

        // Power map with chain rule for derivative
        float rp = powf(fmaxf(r, 1e-9f), power);
        dr = dr * power * powf(fmaxf(r, 1e-9f), power - 1.0f) * dr_a_dr + 1.0f;

        float thetap = theta * power;
        float phip   = phi   * power;

        float st = sinf(thetap), ct = cosf(thetap);
        float cp = cosf(phip),   sp = sinf(phip);

        z = make_float3(rp*st*cp + p.x, rp*st*sp + p.y, rp*ct + p.z);
        lastZ = z;
        iters = k + 1;
    }

    float rr = fmaxf(r_euclid, 1e-8f);
    float nu = (float)iters + 1.f - logf(logf(rr)) / logf(fmaxf(power, 1.001f));

    // Color modes
    float3 col = make_float3(0.5f, 0.5f, 0.5f);

    if (color_mode == 0) {
        // Smooth NI (cosine palette)
        float t = nu * 0.08f;
        float3 a = make_float3(0.5f, 0.5f, 0.5f);
        float3 b = make_float3(0.5f, 0.5f, 0.5f);
        float3 c = make_float3(1.0f, 1.0f, 1.0f);
        float3 d = make_float3(0.0f, 0.33f, 0.67f);
        col.x = a.x + b.x * cosf(6.28318f * (c.x * t + d.x));
        col.y = a.y + b.y * cosf(6.28318f * (c.y * t + d.y));
        col.z = a.z + b.z * cosf(6.28318f * (c.z * t + d.z));
    }
    else if (color_mode == 1) {
        // Orbit traps
        float a = __expf(-8.f * trapPlane);
        float b = __expf(-6.f * trapShell);
        float tt = fminf(fmaxf(a + 0.5f * b, 0.f), 1.f);
        float3 lo = make_float3(0.1f, 0.2f, 0.5f);
        float3 hi = make_float3(0.9f, 0.9f, 0.2f);
        col = make_float3(
            lo.x * (1 - tt) + hi.x * tt,
            lo.y * (1 - tt) + hi.y * tt,
            lo.z * (1 - tt) + hi.z * tt
        );
        float ni = fmodf(nu * 0.1f, 1.f);
        col.x *= (0.85f + 0.30f * ni);
        col.y *= (0.85f + 0.30f * ni);
        col.z *= (0.85f + 0.30f * ni);
    }
    else {
        // Angular/Phase
        float rlast = sqrtf(lastZ.x*lastZ.x + lastZ.y*lastZ.y + lastZ.z*lastZ.z);
        float phi_l = atan2f(lastZ.y, lastZ.x);
        float theta_l = (rlast > 0.f) ? acosf(fmaxf(fminf(lastZ.z / rlast, 1.f), -1.f)) : 0.f;
        float h = fmodf(phi_l / 6.28318f + 1.f, 1.f);
        float s = fminf(fmaxf(theta_l / 3.14159f, 0.f), 1.f);
        float v = 0.9f;
        
        // HSV to RGB
        float c = v * s;
        float x = c * (1.f - fabsf(fmodf(h * 6.f, 2.f) - 1.f));
        float m = v - c;
        float3 rgb_hsv;
        if      (h < 1.f/6.f) rgb_hsv = make_float3(c, x, 0);
        else if (h < 2.f/6.f) rgb_hsv = make_float3(x, c, 0);
        else if (h < 3.f/6.f) rgb_hsv = make_float3(0, c, x);
        else if (h < 4.f/6.f) rgb_hsv = make_float3(0, x, c);
        else if (h < 5.f/6.f) rgb_hsv = make_float3(x, 0, c);
        else                   rgb_hsv = make_float3(c, 0, x);
        col = make_float3(rgb_hsv.x + m, rgb_hsv.y + m, rgb_hsv.z + m);
        
        float ni = fmodf(nu * 0.15f, 1.f);
        col.x *= (0.85f + 0.25f * ni);
        col.y *= (0.85f + 0.25f * ni);
        col.z *= (0.85f + 0.25f * ni);
    }

    rgb[3*i+0] = (unsigned char)(fminf(fmaxf(col.x * 255.f, 0.f), 255.f));
    rgb[3*i+1] = (unsigned char)(fminf(fmaxf(col.y * 255.f, 0.f), 255.f));
    rgb[3*i+2] = (unsigned char)(fminf(fmaxf(col.z * 255.f, 0.f), 255.f));
}
'''

def compute_vertex_colors_gpu(
    verts_xyz: np.ndarray,
    power: float = 8.0,
    bailout: float = 8.0,
    max_iter: int = 14,
    color_mode: int = 1,
    orbit_shell: float = 1.0,
    pi_mode: int = 0,
    pi_base: float = np.pi,
    pi_alpha: float = 0.0,
    pi_mu: float = 0.05,
    norm_mode: int = 0,
    norm_k: float = 0.12,
    norm_r0: float = 0.9,
    norm_sigma: float = 0.35
) -> np.ndarray:
    """
    Compute per-vertex colors on GPU.
    
    Args:
        verts_xyz: Nx3 array of vertex positions (world coordinates)
        power: Mandelbulb power
        bailout: Escape radius
        max_iter: Max iterations
        color_mode: 0=smooth NI, 1=orbit trap, 2=angular
        orbit_shell: Shell radius for orbit trap
        pi_mode: 0=fixed, 1=adaptive
        pi_base: Base π value
        pi_alpha: Adaptive π alpha parameter
        pi_mu: Adaptive π mu parameter
        norm_mode: 0=Euclidean, 1=adaptive
        norm_k, norm_r0, norm_sigma: Adaptive norm parameters
        
    Returns:
        Nx3 uint8 array of RGB colors
    """
    n = len(verts_xyz)
    if n == 0:
        return np.zeros((0, 3), dtype=np.uint8)
    
    # Transfer vertices to GPU
    vx = cp.asarray(verts_xyz[:, 0].astype(np.float32))
    vy = cp.asarray(verts_xyz[:, 1].astype(np.float32))
    vz = cp.asarray(verts_xyz[:, 2].astype(np.float32))
    
    rgb = cp.empty((n, 3), dtype=cp.uint8)
    
    # Compile kernel
    mod = cp.RawModule(code=ORBIT_COLOR_KERNEL, options=('-use_fast_math',))
    kern = mod.get_function('orbit_color')
    
    # Launch kernel
    threads_per_block = 256
    blocks = (n + threads_per_block - 1) // threads_per_block
    
    kern(
        (blocks,), (threads_per_block,),
        (vx, vy, vz, rgb, np.int32(n),
         np.float32(power), np.float32(bailout), np.int32(max_iter),
         np.int32(color_mode), np.float32(orbit_shell),
         np.int32(pi_mode), np.float32(pi_base), np.float32(pi_alpha), np.float32(pi_mu),
         np.int32(norm_mode), np.float32(norm_k), np.float32(norm_r0), np.float32(norm_sigma))
    )
    
    return cp.asnumpy(rgb)
