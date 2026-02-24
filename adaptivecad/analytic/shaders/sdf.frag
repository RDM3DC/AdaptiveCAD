#version 330 core
out vec4 FragColor;

#define MAX_PRIMS 48 // keep in sync with aacore.sdf.MAX_PRIMS

uniform int   u_count;
uniform int   u_kind[MAX_PRIMS];
uniform int   u_op[MAX_PRIMS];
uniform float u_beta[MAX_PRIMS];
uniform vec3  u_color[MAX_PRIMS];
uniform vec4  u_params[MAX_PRIMS]; // sphere:(r,0,0,0) box:(sx,sy,sz,0) capsule:(r,h,0,0) torus:(R,r,0,0)
uniform mat4  u_xform[MAX_PRIMS];
uniform mat4  u_xform_inv[MAX_PRIMS]; // precomputed inverse (CPU)
uniform vec4  u_mod[MAX_PRIMS];  // x=shell, y=round, z=twist, w=taper
uniform vec4  u_mod2[MAX_PRIMS]; // xyz=elongate, w=mirror_axes bitmask

uniform vec2 u_res;
uniform vec3 u_cam_pos;
uniform mat3 u_cam_rot;
uniform vec3 u_bg;   // background color
uniform vec3 u_env;  // environment light direction (length may encode intensity)
uniform int  u_debug;      // 0 beauty,1 normals,2 id,3 depth,4 thickness
uniform int  u_selected;   // selected primitive index (-1 none)
uniform int  u_fractal_mode;       // 0 smooth escape, 1 orbit trap, 2 angular
uniform float u_fractal_orbit_shell; // orbit trap shell radius in fractal space
uniform float u_fractal_ni_scale;  // normalized iteration palette scale

const int KIND_NONE=0, KIND_SPHERE=1, KIND_BOX=2, KIND_CAPSULE=3, KIND_TORUS=4, KIND_MOBIUS=5, KIND_SUPERELLIPSOID=6, KIND_QUASICRYSTAL=7, KIND_TORUS4D=8, KIND_MANDELBULB=9, KIND_KLEIN=10, KIND_MENGER=11, KIND_HYPERBOLIC=12, KIND_GYROID=13, KIND_TREFOIL=14, KIND_HELICOID=15, KIND_ORBITAL=16;
const int OP_SOLID=0, OP_SUB=1, OP_INT=2;

const float PI = 3.14159265359;
const float TAU = 6.28318530718;

float pia_scale(float r, float beta){ return r * (1.0 + 0.125 * beta * r * r); }
float sd_sphere(vec3 p, float r){ return length(p) - r; }
float sd_box(vec3 p, vec3 b){ vec3 q = abs(p)-b; return length(max(q,0.0)) + min(max(q.x,max(q.y,q.z)),0.0); }
float sd_capsule_y(vec3 p, float r, float h){ vec3 a=vec3(0,-0.5*h,0); vec3 b=vec3(0,0.5*h,0); vec3 pa=p-a, ba=b-a; float t=clamp(dot(pa,ba)/dot(ba,ba),0.0,1.0); return length(pa-ba*t)-r; }
float sd_torus_y(vec3 p, float R, float r){ float qx=length(p.xz)-R; return length(vec2(qx,p.y))-r; }
float lpn(vec3 p, float power){
    power = max(1.0, power);
    vec3 ap = abs(p);
    return pow(pow(ap.x,power) + pow(ap.y,power) + pow(ap.z,power), 1.0/power);
}
float sd_superellipsoid(vec3 p, float r, float power){ return lpn(p, power) - r; }

vec3 palette(float t, vec3 a, vec3 b, vec3 c, vec3 d){
    return a + b * cos(6.28318530718 * (c * t + d));
}

// 4D torus (duocylinder) distance function
float sd_torus4d(vec3 p, float R1, float R2, float r, float w_slice) {
    // In 4D: x²+y² and z²+w² form two perpendicular circles
    // For 3D visualization, we treat the input z as the 4th dimension w
    float circle1_radius = length(p.xy);
    float circle2_radius = length(vec2(p.z, w_slice));
    
    // Distance to the 4D torus surface
    float d1 = circle1_radius - R1;
    float d2 = circle2_radius - R2;
    return length(vec2(d1, d2)) - r;
}

struct MandelbulbOrbit {
    float trapPlane;
    float trapShell;
    float r;
    float nu;
    float dr;
    vec3  lastZ;
    int   iter;
};

MandelbulbOrbit mandelbulb_iter(vec3 p, float power, float bailout, float max_iter, float orbitShell){
    MandelbulbOrbit ob;
    ob.trapPlane = 1e9;
    ob.trapShell = 1e9;
    ob.r = 0.0;
    ob.nu = 0.0;
    ob.dr = 1.0;
    ob.lastZ = p;
    ob.iter = 0;

    vec3 z = p;
    float dr = 1.0;
    float r = 0.0;

    int maxIt = int(max_iter);
    for(int i = 0; i < maxIt; ++i){
        r = length(z);
        if(r > bailout){
            ob.iter = i;
            break;
        }

        float r_safe = max(r, 1e-6);
        ob.trapPlane = min(ob.trapPlane, abs(z.y));
        if(orbitShell > 0.0){
            ob.trapShell = min(ob.trapShell, abs(r_safe - orbitShell));
        }

        float theta = acos(clamp(z.z / r_safe, -1.0, 1.0));
        float phi   = atan(z.y, z.x);

        float zr = pow(r_safe, power - 1.0);
        dr = dr * power * zr + 1.0;
        float thetap = theta * power;
        float phip   = phi * power;
        float rp = zr * r_safe;

        vec3 newZ = rp * vec3(sin(thetap) * cos(phip),
                              sin(thetap) * sin(phip),
                              cos(thetap));
        z = newZ + p;
        ob.lastZ = z;
        ob.iter = i + 1;
    }

    ob.r = r;
    ob.dr = dr;
    float rr = max(ob.r, 1e-6);
    float log_base = max(power, 1.001);
    if(rr > 1.0){
        ob.nu = float(ob.iter) + 1.0 - log(log(rr)) / log(log_base);
    } else {
        ob.nu = float(ob.iter);
    }
    return ob;
}

float mandelbulb_distance(vec3 p, float power, float bailout, float max_iter){
    MandelbulbOrbit ob = mandelbulb_iter(p, power, bailout, max_iter, u_fractal_orbit_shell);
    if(ob.r < bailout){
        return 0.0;
    }
    return 0.5 * log(max(ob.r, 1e-6)) * ob.r / max(ob.dr, 1e-6);
}

float sd_mandelbulb(vec3 p, float power, float bailout, float max_iter) {
    return mandelbulb_distance(p, power, bailout, max_iter);
}

vec3 mandelbulb_color(vec3 p, float power, float bailout, float max_iter){
    MandelbulbOrbit ob = mandelbulb_iter(p, power, bailout, max_iter, u_fractal_orbit_shell);
    vec3 A = vec3(0.50);
    vec3 B = vec3(0.50);
    vec3 C = vec3(1.00);
    vec3 D = vec3(0.00, 0.33, 0.67);

    if(u_fractal_mode == 0){
    float t = ob.nu * u_fractal_ni_scale;
    return palette(t, A, B, C, D);
    } else if(u_fractal_mode == 1){
        float a = exp(-8.0 * ob.trapPlane);
        float b = exp(-6.0 * ob.trapShell);
        float t = clamp(a + 0.5 * b, 0.0, 1.0);
        vec3 base = mix(vec3(0.1, 0.2, 0.5), vec3(0.9, 0.9, 0.2), t);
        float ni = fract(ob.nu * max(u_fractal_ni_scale * 1.25, 0.001));
        return base * (0.85 + 0.3 * ni);
    } else {
        vec3 z = ob.lastZ;
        float r_safe = max(length(z), 1e-6);
        float phi = atan(z.y, z.x);
        float theta = acos(clamp(z.z / r_safe, -1.0, 1.0));
        float h = fract(phi / (6.28318530718));
        float s = clamp(theta / 3.14159265359, 0.0, 1.0);
        float v = 0.9;
        float c = v * s;
        float x = c * (1.0 - abs(mod(h * 6.0, 2.0) - 1.0));
        vec3 rgb;
        if(h < 1.0/6.0) rgb = vec3(c, x, 0.0);
        else if(h < 2.0/6.0) rgb = vec3(x, c, 0.0);
        else if(h < 3.0/6.0) rgb = vec3(0.0, c, x);
        else if(h < 4.0/6.0) rgb = vec3(0.0, x, c);
        else if(h < 5.0/6.0) rgb = vec3(x, 0.0, c);
        else rgb = vec3(c, 0.0, x);
        rgb += (v - c);
        float accent = fract(ob.nu * max(u_fractal_ni_scale * 1.875, 0.001));
        return rgb * (0.85 + 0.25 * accent);
    }
}

// Klein bottle 4D->3D projection
float sd_klein_bottle(vec3 p, float a, float n, float t_offset) {
    // Convert to cylindrical coordinates
    float r = length(p.xy);
    float theta = atan(p.y, p.x);
    
    // Klein bottle surface approximation with 4D rotation
    float u = theta + t_offset;
    float v = p.z / a;
    
    // Simplified Klein bottle equations
    float cos_u = cos(u), sin_u = sin(u);
    float cos_v = cos(v), sin_v = sin(v);
    
    // Target surface points
    float target_r = a * (2.0 + cos_u) * (1.0 + 0.5 * cos_v);
    float target_z = a * sin_u * (1.0 + 0.5 * cos_v) + a * 0.5 * sin_v;
    
    // Distance to Klein bottle surface
    float dr = r - target_r;
    float dz = p.z - target_z;
    
    return length(vec2(dr, dz)) - 0.1; // Small thickness
}

// Menger sponge fractal - infinite detail CSG showcase
float sd_menger_sponge(vec3 p, float iterations, float size) {
    // Start with a box
    float d = sd_box(p, vec3(size));
    
    float s = size;
    vec3 pos = p;
    
    for(int i = 0; i < int(iterations); i++) {
        // Scale for this iteration
        s /= 3.0;
        
        // Create the cross-shaped holes pattern
        vec3 a = mod(pos*3.0, 3.0) - 1.5;
        
        // X-axis hole
        float hole_x = sd_box(a, vec3(2.0, s*0.33, s*0.33));
        // Y-axis hole  
        float hole_y = sd_box(a, vec3(s*0.33, 2.0, s*0.33));
        // Z-axis hole
        float hole_z = sd_box(a, vec3(s*0.33, s*0.33, 2.0));
        
        // Combine holes (union)
        float holes = min(hole_x, min(hole_y, hole_z));
        
        // Subtract holes from main shape
        d = max(d, -holes);
        
        // Scale position for next iteration
        pos *= 3.0;
    }
    
    return d;
}

// Hyperbolic {order,symmetry} tiling in Poincaré disk
float sd_hyperbolic_tiling(vec3 p, float scale, float order, float symmetry) {
    // Transform to 2D complex plane
    vec2 z = p.xy / scale;
    float r = length(z);
    
    // Boundary of hyperbolic disk
    if (r > 0.98) {
        return (r - 0.98) * scale;
    }
    
    // Hyperbolic distance from origin
    float hyperbolic_r = (r < 1e-6) ? 0.0 : atanh(min(r, 0.999));
    
    // Angle in complex plane
    float angle = (r > 1e-6) ? atan(z.y, z.x) : 0.0;
    
    // Apply rotational symmetry
    float sector_angle = 2.0 * 3.14159265 / order;
    float normalized_angle = mod(angle + sector_angle * 0.5, sector_angle) - sector_angle * 0.5;
    
    // Distance to sector boundaries
    float boundary_dist = abs(normalized_angle) - sector_angle * 0.5;
    
    // Concentric hyperbolic rings
    float edge_spacing = 0.8;
    float ring_number = floor(hyperbolic_r / edge_spacing);
    float dist_to_ring = abs(hyperbolic_r - ring_number * edge_spacing) - 0.05;
    
    // Angular features
    float angular_dist = abs(boundary_dist) * hyperbolic_r - 0.02;
    
    // Hyperbolic metric correction
    float metric_factor = 1.0 / (1.0 - r*r + 1e-6);
    
    // Combine distances
    float dist = min(dist_to_ring, angular_dist) * metric_factor;
    
    // 3D height modulation
    float z_height = p.z / scale;
    float height_modulation = 0.1 * cos(hyperbolic_r * 10.0) * cos(normalized_angle * order);
    
    return (dist + abs(z_height - height_modulation) - 0.1) * scale;
}

// Gyroid TPMS shell SDF (approximate)
float sd_gyroid(vec3 p, float scale, float tau, float thickness){
    vec3 ps = p * scale;
    float x=ps.x, y=ps.y, z=ps.z;
    float sx=sin(x), cx=cos(x);
    float sy=sin(y), cy=cos(y);
    float sz=sin(z), cz=cos(z);
    float f = sx*cy + sy*cz + sz*cx - tau;
    vec3 g = vec3(cx*cy - sz*sx, cz*cy - sx*sy, cx*cz - sy*sz);
    float mag = length(g) + 1e-6;
    float sdf = abs(f)/mag;
    // account for scaling so world-distance remains consistent
    sdf = sdf / max(1e-6, scale);
    return sdf - thickness;
}

// Trefoil knot tube (sampling-based)
vec3 trefoil_pos(float t){
    float c3 = cos(3.0*t), s3 = sin(3.0*t);
    float c2 = cos(2.0*t), s2 = sin(2.0*t);
    float r = 2.0 + c3;
    return vec3(r*c2, r*s2, s3);
}
float sd_trefoil_knot(vec3 p, float scale, float tube, float samples){
    vec3 q = p / max(1e-6, scale);
    int N1 = int(max(24.0, samples*0.5));
    float best = 1e9; float tbest = 0.0;
    for(int i=0;i<N1;i++){
        float t = 6.28318530718 * (float(i)/float(max(1,N1)));
        vec3 c = trefoil_pos(t);
        float d = length(q - c);
        if(d < best){ best = d; tbest = t; }
    }
    int N2 = int(max(24.0, samples));
    float window = 6.28318530718 / float(N2);
    for(int j=0;j<N2;j++){
        float t = (tbest - 0.5*window) + (float(j)/max(1.0, float(N2-1))) * window;
        if(t < 0.0) t += 6.28318530718;
        if(t >= 6.28318530718) t -= 6.28318530718;
        vec3 c = trefoil_pos(t);
        float d = length(q - c);
        if(d < best) best = d;
    }
    return best * scale - tube;
}

// Quasi-crystal value and conservative bound
float qc_value(vec3 p, float scale){
    // 7 directions via Fibonacci sphere
    float f = 0.0; float n = 7.0; float ga = 2.39996322973;
    for(int i=0;i<7;i++){
        float a = ga * float(i);
        float z = 1.0 - 2.0*(float(i)+0.5)/n;
        float r = sqrt(max(1e-6, 1.0 - z*z));
        vec3 k = vec3(cos(a)*r, sin(a)*r, z);
        f += cos(scale * dot(k, p));
    }
    return f;
}

// approximate Möbius distance (sampling-based)
float sd_mobius(vec3 p, float R, float w){
    float best = 1e9;
    for(int i=0;i<64;i++){
        float u = 6.28318530718 * (float(i) / 64.0);
        float c = cos(u); float s = sin(u);
        float c2 = cos(0.5*u); float s2 = sin(0.5*u);
        vec3 A = vec3(R*c, R*s, 0.0);
        vec3 B = vec3(c2*c, c2*s, s2);
        float bb = dot(B,B) + 1e-6;
        vec3 v = p - A;
        float vstar = dot(v,B) / bb;
        float halfw = 0.5 * w;
        vstar = clamp(vstar, -halfw, halfw);
        vec3 S = A + vstar * B;
        float d = length(p - S);
        if(d < best) best = d;
    }
    return best;
}

float wrap_pi(float a){
    return mod(a + PI, TAU) - PI;
}

// Thickened helicoid surface, limited to an annulus and finite turns.
// params: rInner, rOuter, pitch (height per turn), turns ; thickness from beta
float sd_helicoid_ribbon(vec3 p, float rInner, float rOuter, float pitch, float turns, float thickness){
    float r = length(p.xy);
    float r_safe = max(r, 1e-6);
    float k = pitch / TAU;
    if(abs(k) < 1e-6) return 1e9;

    float theta = atan(p.y, p.x); // [-pi, pi]
    float u = p.z / k;
    float dtheta = wrap_pi(u - theta);

    // chord distance to the nearest point on the circle at same z
    float d_surface = 2.0 * r_safe * sin(0.5 * abs(dtheta));
    float d = d_surface - max(thickness, 0.0005);

    float rin = min(rInner, rOuter);
    float rout = max(rInner, rOuter);
    d = max(d, rin - r);
    d = max(d, r - rout);

    float height = abs(pitch) * max(turns, 0.0);
    float z0 = -0.5 * height;
    float z1 =  0.5 * height;
    d = max(d, z0 - p.z);
    d = max(d, p.z - z1);
    return d;
}

float gen_laguerre(int k, float alpha, float x){
    if(k <= 0) return 1.0;
    if(k == 1) return 1.0 + alpha - x;
    float Lkm2 = 1.0;
    float Lkm1 = 1.0 + alpha - x;
    for(int n = 1; n < k; ++n){
        float Ln1 = ((2.0*float(n) + 1.0 + alpha - x) * Lkm1 - (float(n) + alpha) * Lkm2) / (float(n) + 1.0);
        Lkm2 = Lkm1;
        Lkm1 = Ln1;
    }
    return Lkm1;
}

float real_sph_harm(int l, int m, float theta, float phi){
    float ct = cos(theta);
    float st = sin(theta);
    if(l == 0){
        return 0.2820947918;
    }
    if(l == 1){
        if(m == 0) return 0.4886025119 * ct;
        if(m == 1) return 0.4886025119 * st * cos(phi);
        if(m == -1) return 0.4886025119 * st * sin(phi);
        return 0.0;
    }
    if(l == 2){
        if(m == 0) return 0.3153915653 * (3.0*ct*ct - 1.0);
        if(m == 1) return 1.0925484306 * st * ct * cos(phi);
        if(m == -1) return 1.0925484306 * st * ct * sin(phi);
        if(m == 2) return 0.5462742153 * st * st * cos(2.0*phi);
        if(m == -2) return 0.5462742153 * st * st * sin(2.0*phi);
        return 0.0;
    }
    if(l == 3){
        if(m == 0) return 0.3731763326 * (5.0*ct*ct*ct - 3.0*ct);
        if(m == 1) return 0.4570457995 * st * (5.0*ct*ct - 1.0) * cos(phi);
        if(m == -1) return 0.4570457995 * st * (5.0*ct*ct - 1.0) * sin(phi);
        if(m == 2) return 1.4453057213 * st * st * ct * cos(2.0*phi);
        if(m == -2) return 1.4453057213 * st * st * ct * sin(2.0*phi);
        if(m == 3) return 0.5900435899 * st * st * st * cos(3.0*phi);
        if(m == -3) return 0.5900435899 * st * st * st * sin(3.0*phi);
        return 0.0;
    }
    return 0.0;
}

float hydrogenic_density(vec3 p, int n, int l, int m){
    if(n < 1) return 0.0;
    if(l < 0 || l >= n) return 0.0;
    if(abs(m) > l) return 0.0;

    float r = length(p);
    float rs = max(r, 1e-6);
    float theta = acos(clamp(p.z / rs, -1.0, 1.0));
    float phi = atan(p.y, p.x);

    float rho = 2.0 * rs / max(float(n), 1.0);
    int k = n - l - 1;
    float alpha = 2.0 * float(l) + 1.0;
    float L = gen_laguerre(k, alpha, rho);
    float R = exp(-0.5 * rho) * pow(rho, float(l)) * L;
    float Y = real_sph_harm(l, m, theta, phi);
    float psi = R * Y;
    return psi * psi;
}

float sd_hydrogenic_orbital(vec3 p, int n, int l, int m, float iso, float thickness){
    float r = length(p);
    float eps = 0.001 * (1.0 + 0.25 * r);
    vec3 ex = vec3(eps, 0.0, 0.0);
    vec3 ey = vec3(0.0, eps, 0.0);
    vec3 ez = vec3(0.0, 0.0, eps);

    float f0 = hydrogenic_density(p, n, l, m) - iso;
    float gx = (hydrogenic_density(p + ex, n, l, m) - hydrogenic_density(p - ex, n, l, m)) / (2.0 * eps);
    float gy = (hydrogenic_density(p + ey, n, l, m) - hydrogenic_density(p - ey, n, l, m)) / (2.0 * eps);
    float gz = (hydrogenic_density(p + ez, n, l, m) - hydrogenic_density(p - ez, n, l, m)) / (2.0 * eps);
    // grad(density-iso) == grad(density)
    float g = max(length(vec3(gx, gy, gz)), 1e-6);
    return abs(f0) / g - max(thickness, 0.0005);
}

float map_scene(vec3 pw, out vec3 outColor, out int outId){
    float d = 1e9; vec3 col = vec3(0.1); int hitId = -1;
    for(int i=0;i<u_count;i++){
        mat4 Mi = u_xform_inv[i];
        vec3 pl = (Mi * vec4(pw,1.0)).xyz;

        // --- Pre-SDF domain modifiers ---
        // Mirror
        int mflags = int(u_mod2[i].w + 0.5);
        if((mflags & 1) != 0) pl.x = abs(pl.x);
        if((mflags & 2) != 0) pl.y = abs(pl.y);
        if((mflags & 4) != 0) pl.z = abs(pl.z);
        // Elongate
        vec3 elong = u_mod2[i].xyz;
        if(elong.x > 0.0 || elong.y > 0.0 || elong.z > 0.0){
            vec3 q = pl - clamp(pl, -elong, elong);
            pl = q;
        }
        // Twist (around Y axis)
        float twistK = u_mod[i].z;
        if(abs(twistK) > 1e-6){
            float ca = cos(twistK * pl.y);
            float sa = sin(twistK * pl.y);
            pl = vec3(ca*pl.x - sa*pl.z, pl.y, sa*pl.x + ca*pl.z);
        }
        // Bend (around Y, curving X into a circular arc)
        float bendK = 0.0; // reserved, currently unused in u_mod — future slot
        // Taper (scale XZ by linear function of Y)
        float taperK = u_mod[i].w;
        if(abs(taperK) > 1e-6){
            float tScale = max(1.0 + taperK * pl.y, 0.01);
            pl.xz /= tScale;
        }

        float di = 1e9;
        if(u_kind[i]==KIND_SPHERE){ float r = pia_scale(u_params[i].x, u_beta[i]); di = sd_sphere(pl,r); }
        else if(u_kind[i]==KIND_BOX){ di = sd_box(pl, u_params[i].xyz); }
        else if(u_kind[i]==KIND_CAPSULE){ float r = pia_scale(u_params[i].x, u_beta[i]); di = sd_capsule_y(pl, r, u_params[i].y); }
    else if(u_kind[i]==KIND_TORUS){ float R=u_params[i].x; float r=pia_scale(u_params[i].y, u_beta[i]); di=sd_torus_y(pl,R,r); }
    else if(u_kind[i]==KIND_MOBIUS){ float R=u_params[i].x; float w=u_params[i].y; di=sd_mobius(pl,R,w); }
        else if(u_kind[i]==KIND_SUPERELLIPSOID){ float r=u_params[i].x; float pwr=max(1.0,u_params[i].y); di = sd_superellipsoid(pl, r, pwr); }
        else if(u_kind[i]==KIND_QUASICRYSTAL){
            float sc=u_params[i].x; float iso=u_params[i].y; float th=max(0.0005,u_params[i].z);
            float v = qc_value(pl, sc);
            // |grad f| <= n*scale where n=7
            float K = 7.0*abs(sc);
            di = (abs(v - iso)/max(K,1e-4)) - th;
        }
        else if(u_kind[i]==KIND_TORUS4D){
            float R1=u_params[i].x; float R2=u_params[i].y; float r=u_params[i].z; float w_slice=u_params[i].w;
            di = sd_torus4d(pl, R1, R2, r, w_slice);
        }
        else if(u_kind[i]==KIND_MANDELBULB){
            float power=u_params[i].x; float bailout=u_params[i].y; float max_iter=u_params[i].z; float scale=u_params[i].w;
            di = sd_mandelbulb(pl * scale, power, bailout, max_iter) / scale;
        }
        else if(u_kind[i]==KIND_KLEIN){
            float scale=u_params[i].x; float n=u_params[i].y; float t_offset=u_params[i].z;
            di = sd_klein_bottle(pl, scale, n, t_offset);
        }
        else if(u_kind[i]==KIND_MENGER){
            float iterations=u_params[i].x; float size=u_params[i].y;
            di = sd_menger_sponge(pl, iterations, size);
        }
        else if(u_kind[i]==KIND_HYPERBOLIC){
            float scale=u_params[i].x; float order=u_params[i].y; float symmetry=u_params[i].z;
            di = sd_hyperbolic_tiling(pl, scale, order, symmetry);
        }
        else if(u_kind[i]==KIND_GYROID){
            float scale=u_params[i].x; float tau=u_params[i].y; float thickness=u_params[i].z;
            di = sd_gyroid(pl, scale, tau, thickness);
        }
        else if(u_kind[i]==KIND_TREFOIL){
            float scale=u_params[i].x; float tube=u_params[i].y; float samples=u_params[i].z;
            di = sd_trefoil_knot(pl, scale, tube, samples);
        }
        else if(u_kind[i]==KIND_HELICOID){
            float rInner=u_params[i].x; float rOuter=u_params[i].y; float pitch=u_params[i].z; float turns=u_params[i].w;
            float thickness = u_beta[i];
            di = sd_helicoid_ribbon(pl, rInner, rOuter, pitch, turns, thickness);
        }
        else if(u_kind[i]==KIND_ORBITAL){
            int n = int(round(u_params[i].x));
            int l = int(round(u_params[i].y));
            int m = int(round(u_params[i].z));
            float iso = u_params[i].w;
            float thickness = u_beta[i];
            di = sd_hydrogenic_orbital(pl, n, l, m, iso, thickness);
        }
        // --- Post-SDF modifiers ---
        // Round: shrink the iso-surface inward
        float roundR = u_mod[i].y;
        if(roundR > 1e-6) di -= roundR;
        // Shell: hollow out the shape
        float shellT = u_mod[i].x;
        if(shellT > 1e-6) di = abs(di) - shellT;

        if(u_op[i]==OP_SUB){
            float nd = max(d, -di);
            if(nd < d + 1e-4){ col = u_color[i]; hitId=i; }
            d = nd;
        }
        else if(u_op[i]==OP_INT){
            float nd = max(d, di);
            if(di > d){ col = u_color[i]; hitId=i; }
            d = nd;
        }
        else {
            if(di < d){ d=di; col=u_color[i]; hitId=i; }
        }
    }
    outColor = col; outId = hitId; return d;
}

// Central difference gradient for distance field visualization
vec3 gradient_central_diff(vec3 p) {
    float eps = 0.001;
    vec3 dummy_color;
    int dummy_id;
    float gx = map_scene(p + vec3(eps, 0, 0), dummy_color, dummy_id) - map_scene(p - vec3(eps, 0, 0), dummy_color, dummy_id);
    float gy = map_scene(p + vec3(0, eps, 0), dummy_color, dummy_id) - map_scene(p - vec3(0, eps, 0), dummy_color, dummy_id);
    float gz = map_scene(p + vec3(0, 0, eps), dummy_color, dummy_id) - map_scene(p - vec3(0, 0, eps), dummy_color, dummy_id);
    return vec3(gx, gy, gz) / (2.0 * eps);
}

vec3 calc_normal(vec3 p){
    float e = 1e-3; vec2 h = vec2(1.0,-1.0)*0.5773; vec3 c; int _id;
    return normalize( h.xyy*map_scene(p + h.xyy*e,c,_id) +
                      h.yyx*map_scene(p + h.yyx*e,c,_id) +
                      h.yxy*map_scene(p + h.yxy*e,c,_id) +
                      h.xxx*map_scene(p + h.xxx*e,c,_id) );
}

void main(){
    vec2 uv = (gl_FragCoord.xy / u_res) * 2.0 - 1.0; uv.x *= u_res.x/u_res.y;
    float fov = radians(45.0);
    vec3 rd = normalize(u_cam_rot * vec3(uv.x, uv.y, -1.0 / tan(0.5*fov)));
    vec3 ro = u_cam_pos;
    float t=0.0; bool hit=false; vec3 p,n; vec3 col=vec3(0.1); int pid=-1; int cid;
    for(int i=0;i<256;i++){
        vec3 c; float d = map_scene(ro + rd*t, c, cid);
        if(d < 0.001){ hit=true; p=ro+rd*t; col=c; n=calc_normal(p); break; }
        t += max(d, 0.002); if(t>200.0) break; }
    if(!hit){ FragColor=vec4(u_bg,1); return; }
    // Re-evaluate id at hit point (cheap) to capture pid
    vec3 _c2; pid = -1; float _d2 = map_scene(p, _c2, pid);
    vec3 surfColor = col;
    if(pid >= 0 && u_kind[pid] == KIND_MANDELBULB){
        vec4 mparams = u_params[pid];
        float scale = max(1e-6, mparams.w);
        vec3 pl = (u_xform_inv[pid] * vec4(p, 1.0)).xyz * scale;
        surfColor = mandelbulb_color(pl, mparams.x, mparams.y, mparams.z);
    }

    vec3 L = normalize(u_env); float ndl=max(dot(n,L),0.0);
    vec3 base = mix(surfColor*0.5, surfColor, 0.5+0.5*ndl);

    // --- Selection highlight helper: gold tint + rim (applied in all visual modes) ---
    bool is_sel = (u_selected >= 0 && pid == u_selected);

    if(u_debug==1){ // normals
        vec3 c = n*0.5+0.5;
        if(is_sel){ float rim = pow(1.0-max(dot(n,-rd),0.0),2.0);
            c = mix(vec3(1.0,0.85,0.25), c, 0.25); c = clamp(c+rim*0.5,0.0,1.0); }
        FragColor = vec4(c,1.0); return; }
    if(u_debug==2){ // id encode (pid+1 so -1 -> 0) — no tinting
        int enc = (pid < 0) ? 0 : (pid+1);
        int r =  enc       & 255;
        int g = (enc >> 8) & 255;
        int b = (enc >>16) & 255;
        FragColor = vec4(r/255.0, g/255.0, b/255.0, 1.0); return; }
    if(u_debug==3){ // depth
        float depth = clamp(t/200.0, 0.0, 1.0);
        vec3 c = vec3(depth);
        if(is_sel){ float rim = pow(1.0-max(dot(n,-rd),0.0),2.0);
            c = mix(vec3(1.0,0.85,0.25), c, 0.25); c = clamp(c+rim*0.5,0.0,1.0); }
        FragColor = vec4(c,1.0); return; }
    if(u_debug==4){ // thickness placeholder
        float th = pow(1.0 - abs(dot(n, rd)), 2.0);
        vec3 c = vec3(th);
        if(is_sel){ float rim = pow(1.0-max(dot(n,-rd),0.0),2.0);
            c = mix(vec3(1.0,0.85,0.25), c, 0.25); c = clamp(c+rim*0.5,0.0,1.0); }
        FragColor = vec4(c,1.0); return; }
    if(u_debug==5){ // adaptive heatmap - distance field gradient
        vec3 p_hit = p + t * rd;
        float hval = length(gradient_central_diff(p_hit));
        vec3 heat_color;
        hval = clamp(hval * 2.0, 0.0, 3.0);
        if(hval < 1.0) {
            heat_color = mix(vec3(0.0, 0.0, 1.0), vec3(0.0, 1.0, 0.0), hval);
        } else if(hval < 2.0) {
            heat_color = mix(vec3(0.0, 1.0, 0.0), vec3(1.0, 1.0, 0.0), hval-1.0);
        } else {
            heat_color = mix(vec3(1.0, 1.0, 0.0), vec3(1.0, 0.0, 0.0), hval-2.0);
        }
        if(is_sel){ float rim = pow(1.0-max(dot(n,-rd),0.0),2.0);
            heat_color = mix(vec3(1.0,0.85,0.25), heat_color, 0.25); heat_color = clamp(heat_color+rim*0.5,0.0,1.0); }
        FragColor = vec4(heat_color, 1.0); return; }

    // Beauty mode (u_debug==0) + selection highlight
    if(is_sel){
        float rim = pow(1.0 - max(dot(n,-rd),0.0), 2.0);
        vec3 gold = vec3(1.0,0.85,0.25);
        base = mix(gold, base, 0.25);
        base += rim*0.5;
        base = clamp(base, 0.0, 1.0);
    }
    FragColor = vec4(base,1.0);
}
