#version 330 core

#ifdef GL_ES
precision highp float;
#endif

out vec4 fragColor;

uniform vec2  uResolution;
uniform float uTime;

uniform vec3  uCamPos;
uniform vec3  uCamTarget;
uniform vec3  uCamUp;
uniform float uFov;

uniform float uPower;
uniform float uBailout;
uniform int   uMaxIter;
uniform int   uMaxSteps;
uniform float uEps;
uniform float uMaxDist;

uniform int   uColorMode;
uniform float uOrbitShellR;
uniform vec3  uLightDir;
uniform float uNiScale;

const float PI = 3.141592653589793;
const float TAU = 6.283185307179586;

vec3 palette(float t, vec3 a, vec3 b, vec3 c, vec3 d)
{
    return a + b * cos(TAU * (c * t + d));
}

struct Orbit {
    float trapPlane;
    float trapShell;
    float r;
    float nu;
    vec3  lastZ;
    int   iter;
};

float mandelbulbDE(vec3 p, out Orbit ob)
{
    vec3 z = p;
    float dr = 1.0;
    float r = 0.0;

    ob.trapPlane = 1e9;
    ob.trapShell = 1e9;
    ob.lastZ = z;
    ob.iter = 0;

    for (int i = 0; i < 200; ++i)
    {
        if (i >= uMaxIter)
        {
            ob.iter = i;
            break;
        }

        r = length(z);

        if (r > uBailout)
        {
            ob.iter = i;
            break;
        }

        float rSafe = max(r, 1e-8);
        ob.trapPlane = min(ob.trapPlane, abs(z.y));
        ob.trapShell = min(ob.trapShell, abs(rSafe - uOrbitShellR));

        float theta = acos(clamp(z.z / rSafe, -1.0, 1.0));
        float phi = atan(z.y, z.x);

        float zr = pow(rSafe, uPower - 1.0);
        dr = dr * uPower * zr + 1.0;
        float rp = zr * rSafe;

        float thetap = theta * uPower;
        float phip = phi * uPower;

        vec3 newZ = rp * vec3(sin(thetap) * cos(phip),
                              sin(thetap) * sin(phip),
                              cos(thetap));
        z = newZ + p;
        ob.lastZ = z;
        ob.iter = i + 1;
    }

    float rr = max(r, 1e-8);
    float logBase = max(uPower, 1.001);
    if (rr > 1.0)
    {
        ob.nu = float(ob.iter) + 1.0 - log(log(rr)) / log(logBase);
    }
    else
    {
        ob.nu = float(ob.iter);
    }
    ob.r = r;

    if (r <= uBailout)
    {
        return 0.0;
    }
    return 0.5 * log(rr) * rr / max(dr, 1e-6);
}

float mapDE(vec3 p, out Orbit ob)
{
    return mandelbulbDE(p, ob);
}

vec3 estimateNormal(vec3 p)
{
    Orbit dummy;
    float e = uEps * 2.0;
    vec2 h = vec2(1.0, -1.0) * 0.5773;

    float dx1 = mapDE(p + vec3(h.x, h.y, h.y) * e, dummy);
    float dx2 = mapDE(p - vec3(h.x, h.y, h.y) * e, dummy);
    float dy1 = mapDE(p + vec3(h.y, h.y, h.x) * e, dummy);
    float dy2 = mapDE(p - vec3(h.y, h.y, h.x) * e, dummy);
    float dz1 = mapDE(p + vec3(h.y, h.x, h.y) * e, dummy);
    float dz2 = mapDE(p - vec3(h.y, h.x, h.y) * e, dummy);
    float dw1 = mapDE(p + vec3(h.x, h.x, h.x) * e, dummy);
    float dw2 = mapDE(p - vec3(h.x, h.x, h.x) * e, dummy);

    vec3 n = h.xyy * (dx1 - dx2) +
             h.yyx * (dy1 - dy2) +
             h.yxy * (dz1 - dz2) +
             h.xxx * (dw1 - dw2);

    return normalize(n);
}

float ao(vec3 p, vec3 n)
{
    Orbit dummy;
    float scale = 1.0;
    float occ = 0.0;

    for (int i = 1; i <= 5; ++i)
    {
        float h = uEps * float(i) * 2.0;
        float d = mapDE(p + n * h, dummy);
        occ += (h - d) * scale;
        scale *= 0.6;
    }

    return clamp(1.0 - 2.0 * occ, 0.0, 1.0);
}

vec3 colorField(const Orbit ob)
{
    vec3 A = vec3(0.50);
    vec3 B = vec3(0.50);
    vec3 C = vec3(1.00);
    vec3 D = vec3(0.00, 0.33, 0.67);

    if (uColorMode == 0)
    {
        float t = ob.nu * uNiScale;
        return palette(t, A, B, C, D);
    }
    else if (uColorMode == 1)
    {
        float a = exp(-8.0 * ob.trapPlane);
        float b = exp(-6.0 * ob.trapShell);
        float t = clamp(a + 0.5 * b, 0.0, 1.0);
        vec3 base = mix(vec3(0.1, 0.2, 0.5), vec3(0.9, 0.9, 0.2), t);
        float ni = fract(ob.nu * max(uNiScale * 1.25, 0.001));
        return base * (0.85 + 0.3 * ni);
    }
    else
    {
        vec3 z = ob.lastZ;
        float r = max(length(z), 1e-6);
        float phi = atan(z.y, z.x);
        float theta = acos(clamp(z.z / r, -1.0, 1.0));
        float h = fract(phi / (TAU));
        float s = clamp(theta / PI, 0.0, 1.0);
        float v = 0.9;
        float c = v * s;
        float x = c * (1.0 - abs(mod(h * 6.0, 2.0) - 1.0));
        vec3 rgb;
        if (h < 1.0 / 6.0) rgb = vec3(c, x, 0.0);
        else if (h < 2.0 / 6.0) rgb = vec3(x, c, 0.0);
        else if (h < 3.0 / 6.0) rgb = vec3(0.0, c, x);
        else if (h < 4.0 / 6.0) rgb = vec3(0.0, x, c);
        else if (h < 5.0 / 6.0) rgb = vec3(x, 0.0, c);
        else rgb = vec3(c, 0.0, x);
        rgb += (v - c);
        float accent = fract(ob.nu * max(uNiScale * 1.875, 0.001));
        return rgb * (0.85 + 0.25 * accent);
    }
}

void buildCamera(vec3 ro, vec3 ta, vec3 up, out vec3 cw, out vec3 cu, out vec3 cv)
{
    cw = normalize(ta - ro);
    cu = normalize(cross(cw, up));
    cv = cross(cu, cw);
}

void main()
{
    vec2 uv = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;
    vec3 cw; vec3 cu; vec3 cv;
    buildCamera(uCamPos, uCamTarget, uCamUp, cw, cu, cv);
    float f = 1.0 / tan(0.5 * uFov);
    vec3 rd = normalize(cw * f + cu * uv.x + cv * uv.y);

    float t = 0.0;
    Orbit ob;
    bool hit = false;

    for (int i = 0; i < 1024 && i < uMaxSteps; ++i)
    {
        vec3 p = uCamPos + rd * t;
        float d = mapDE(p, ob);
        if (d < uEps)
        {
            hit = true;
            break;
        }
        t += d;
        if (t > uMaxDist)
        {
            break;
        }
    }

    vec3 col = vec3(0.0);

    if (hit)
    {
        vec3 p = uCamPos + rd * t;
        vec3 n = estimateNormal(p);
        float ndl = max(dot(n, normalize(uLightDir)), 0.0);
        float amb = 0.35 * ao(p, n);
        vec3 albedo = colorField(ob);
        col = albedo * (amb + 1.2 * ndl);
        float rim = pow(1.0 - max(dot(n, -rd), 0.0), 3.0);
        col += 0.2 * rim * vec3(0.8, 0.9, 1.0);
    }
    else
    {
        float tbg = 0.5 + 0.5 * rd.y;
        col = mix(vec3(0.05, 0.06, 0.08), vec3(0.12, 0.15, 0.2), tbg);
    }

    col = col / (1.0 + col);
    col = pow(col, vec3(1.0 / 2.2));
    fragColor = vec4(col, 1.0);
}
